from celery import shared_task, chain
from celery.utils.log import get_task_logger
import subprocess
import os
import time
from recordings.models import Recording, RecordingFile
from .models import ProcessingJob, ProcessingStep
from analysis.models import Transcription, TranscriptionSegment, AIAnalysis
from django.utils import timezone
from django.conf import settings
import boto3
from botocore.exceptions import ClientError

logger = get_task_logger(__name__)


def get_s3_client():
    """Initialize and return S3 client for MinIO"""
    return boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )


def download_from_s3(s3_key, local_path):
    """Download file from MinIO to local path"""
    s3_client = get_s3_client()
    s3_client.download_file(settings.AWS_STORAGE_BUCKET_NAME, s3_key, local_path)
    logger.info(f"Downloaded {s3_key} to {local_path}")


def upload_to_s3(local_path, s3_key):
    """Upload file from local path to MinIO"""
    s3_client = get_s3_client()
    with open(local_path, 'rb') as f:
        s3_client.upload_fileobj(f, settings.AWS_STORAGE_BUCKET_NAME, s3_key)
    logger.info(f"Uploaded {local_path} to {s3_key}")
    return s3_key


@shared_task(bind=True, max_retries=3)
def process_recording_pipeline(self, recording_id):
    """
    Main processing pipeline orchestrator
    Chains all processing steps together
    """
    try:
        recording = Recording.objects.get(id=recording_id)
        recording.status = 'processing'
        recording.save()

        # Create processing job
        job = ProcessingJob.objects.create(
            recording=recording,
            celery_task_id=self.request.id,
            status='running',
            started_at=timezone.now()
        )

        logger.info(f"Started processing pipeline for recording {recording_id}")

        # Chain tasks: conversion → extraction → transcription → analysis
        workflow = chain(
            convert_webm_to_mp4.s(recording_id),
            extract_audio_from_video.s(recording_id),
            transcribe_audio.s(recording_id),
            analyze_transcription.s(recording_id)
        )

        workflow.apply_async()

        return f"Processing pipeline started for {recording_id}"

    except Exception as exc:
        logger.error(f"Pipeline failed for {recording_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=2)
def convert_webm_to_mp4(self, recording_id):
    """
    Convert WebM to MP4 using FFmpeg
    """
    step = None
    try:
        recording = Recording.objects.get(id=recording_id)
        job = recording.processing_job

        # Create processing step
        step = ProcessingStep.objects.create(
            job=job,
            step_name='video_conversion',
            status='running',
            started_at=timezone.now()
        )

        logger.info(f"Starting video conversion for {recording_id}")

        # Get WebM file from MinIO
        webm_file = recording.files.get(file_type='original_webm')
        webm_path = f"/tmp/{recording_id}_original.webm"
        download_from_s3(webm_file.s3_key, webm_path)

        # Convert with FFmpeg
        mp4_path = f"/tmp/{recording_id}_converted.mp4"
        ffmpeg_command = [
            'ffmpeg',
            '-i', webm_path,
            '-c:v', 'libx264',  # H.264 codec
            '-preset', 'medium',
            '-crf', '23',  # Quality (lower = better, 23 is good)
            '-c:a', 'aac',  # AAC audio
            '-b:a', '128k',
            '-y',  # Overwrite output file
            mp4_path
        ]

        result = subprocess.run(
            ffmpeg_command,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes max
        )

        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")

        # Upload to MinIO
        s3_key = f"recordings/{recording_id}/converted.mp4"
        upload_to_s3(mp4_path, s3_key)

        # Save file reference
        RecordingFile.objects.create(
            recording=recording,
            file_type='converted_mp4',
            s3_key=s3_key,
            s3_bucket=settings.AWS_STORAGE_BUCKET_NAME,
            file_size_bytes=os.path.getsize(mp4_path)
        )

        # Update step
        step.status = 'completed'
        step.completed_at = timezone.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        step.output_file = s3_key
        step.save()

        # Cleanup
        os.remove(webm_path)
        os.remove(mp4_path)

        logger.info(f"Video conversion completed for {recording_id}")
        return recording_id

    except Exception as exc:
        logger.error(f"Video conversion failed for {recording_id}: {exc}")
        if step:
            step.status = 'failed'
            step.error_message = str(exc)
            step.save()
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=2)
def extract_audio_from_video(self, recording_id):
    """
    Extract audio track for transcription (WAV format for Deepgram)
    """
    step = None
    try:
        recording = Recording.objects.get(id=recording_id)
        job = recording.processing_job

        # Create processing step
        step = ProcessingStep.objects.create(
            job=job,
            step_name='audio_extraction',
            status='running',
            started_at=timezone.now()
        )

        logger.info(f"Starting audio extraction for {recording_id}")

        # Get original WebM file (has audio already)
        webm_file = recording.files.get(file_type='original_webm')
        webm_path = f"/tmp/{recording_id}_original.webm"
        download_from_s3(webm_file.s3_key, webm_path)

        # Extract audio as WAV
        audio_path = f"/tmp/{recording_id}_audio.wav"
        ffmpeg_command = [
            'ffmpeg',
            '-i', webm_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # WAV format
            '-ar', '16000',  # 16kHz sample rate (good for speech)
            '-ac', '1',  # Mono (Deepgram works best with mono)
            '-y',
            audio_path
        ]

        result = subprocess.run(
            ffmpeg_command,
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode != 0:
            raise Exception(f"Audio extraction failed: {result.stderr}")

        # Upload to MinIO
        s3_key = f"recordings/{recording_id}/audio.wav"
        upload_to_s3(audio_path, s3_key)

        # Save file reference
        RecordingFile.objects.create(
            recording=recording,
            file_type='audio_extract',
            s3_key=s3_key,
            s3_bucket=settings.AWS_STORAGE_BUCKET_NAME,
            file_size_bytes=os.path.getsize(audio_path)
        )

        # Update step
        step.status = 'completed'
        step.completed_at = timezone.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        step.output_file = s3_key
        step.save()

        # Cleanup
        os.remove(webm_path)
        os.remove(audio_path)

        logger.info(f"Audio extraction completed for {recording_id}")
        return recording_id

    except Exception as exc:
        logger.error(f"Audio extraction failed for {recording_id}: {exc}")
        if step:
            step.status = 'failed'
            step.error_message = str(exc)
            step.save()
        raise self.retry(exc=exc, countdown=120)


@shared_task(bind=True, max_retries=3)
def transcribe_audio(self, recording_id):
    """
    Send audio to Deepgram API for transcription with speaker diarization
    """
    step = None
    try:
        recording = Recording.objects.get(id=recording_id)
        job = recording.processing_job

        # Create processing step
        step = ProcessingStep.objects.create(
            job=job,
            step_name='speech_to_text',
            status='running',
            started_at=timezone.now()
        )

        logger.info(f"Starting transcription for {recording_id}")

        # Check if Deepgram API key is configured
        if not settings.DEEPGRAM_API_KEY:
            raise Exception("DEEPGRAM_API_KEY not configured")

        from deepgram import DeepgramClient, PrerecordedOptions, FileSource

        # Download audio file
        audio_file = recording.files.get(file_type='audio_extract')
        audio_path = f"/tmp/{recording_id}_audio.wav"
        download_from_s3(audio_file.s3_key, audio_path)

        # Initialize Deepgram client
        deepgram = DeepgramClient(api_key=settings.DEEPGRAM_API_KEY)

        # Read audio file
        with open(audio_path, 'rb') as audio:
            buffer_data = audio.read()

        payload: FileSource = {
            "buffer": buffer_data,
        }

        # Configure options
        options = PrerecordedOptions(
            model="nova-2",
            language="en",
            smart_format=True,
            punctuate=True,
            diarize=True,  # Enable speaker diarization
            utterances=True,  # Get utterances with speaker info
            paragraphs=True,
        )

        # Transcribe
        start_time = time.time()
        response = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        processing_time = time.time() - start_time

        # Extract results
        result = response.results.channels[0].alternatives[0]

        # Create Transcription
        transcription = Transcription.objects.create(
            recording=recording,
            full_text=result.transcript,
            confidence_score=result.confidence,
            language_detected=response.metadata.language if hasattr(response.metadata, 'language') else 'en',
            num_speakers=len(set(u.speaker for u in result.utterances)) if result.utterances else 0,
            audio_duration_seconds=response.metadata.duration,
            processing_time_seconds=processing_time,
            deepgram_response=response.to_dict()
        )

        # Create segments from utterances
        if result.utterances:
            for utterance in result.utterances:
                TranscriptionSegment.objects.create(
                    transcription=transcription,
                    start_time_seconds=utterance.start,
                    end_time_seconds=utterance.end,
                    text=utterance.transcript,
                    confidence_score=utterance.confidence,
                    speaker_id=utterance.speaker,
                    speaker_label=f"Speaker {utterance.speaker}",
                    words=[
                        {
                            'word': w.word,
                            'start': w.start,
                            'end': w.end,
                            'confidence': w.confidence
                        }
                        for w in utterance.words
                    ] if utterance.words else []
                )

        # Update step
        step.status = 'completed'
        step.completed_at = timezone.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        step.metadata = {'num_speakers': transcription.num_speakers}
        step.save()

        # Cleanup
        os.remove(audio_path)

        logger.info(f"Transcription completed for {recording_id}")
        return recording_id

    except Exception as exc:
        logger.error(f"Transcription failed for {recording_id}: {exc}")
        if step:
            step.status = 'failed'
            step.error_message = str(exc)
            step.save()
        raise self.retry(exc=exc, countdown=180)


@shared_task(bind=True, max_retries=3)
def analyze_transcription(self, recording_id):
    """
    Send transcription to Gemini for AI analysis
    Generates: summary, action items, key points, sentiment analysis
    """
    step = None
    try:
        recording = Recording.objects.get(id=recording_id)
        job = recording.processing_job
        transcription = recording.transcription

        # Create processing step
        step = ProcessingStep.objects.create(
            job=job,
            step_name='ai_analysis',
            status='running',
            started_at=timezone.now()
        )

        logger.info(f"Starting AI analysis for {recording_id}")

        # Check if Gemini API key is configured
        if not settings.GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not configured")

        import google.generativeai as genai

        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Prepare transcript with speaker info
        formatted_transcript = format_transcript_with_speakers(transcription)

        # 1. Generate Summary
        summary_result = generate_summary(model, formatted_transcript)
        AIAnalysis.objects.create(
            recording=recording,
            analysis_type='summary',
            result_data=summary_result['data'],
            result_text=summary_result['text'],
            model_version='gemini-1.5-flash',
            tokens_used=summary_result.get('tokens', 0),
            processing_time_seconds=summary_result['time'],
            gemini_response=summary_result.get('response', {})
        )

        # 2. Extract Action Items
        action_items_result = extract_action_items(model, formatted_transcript)
        AIAnalysis.objects.create(
            recording=recording,
            analysis_type='action_items',
            result_data=action_items_result['data'],
            result_text=action_items_result['text'],
            model_version='gemini-1.5-flash',
            tokens_used=action_items_result.get('tokens', 0),
            processing_time_seconds=action_items_result['time'],
            gemini_response=action_items_result.get('response', {})
        )

        # 3. Extract Key Points
        key_points_result = extract_key_points(model, formatted_transcript)
        AIAnalysis.objects.create(
            recording=recording,
            analysis_type='key_points',
            result_data=key_points_result['data'],
            result_text=key_points_result['text'],
            model_version='gemini-1.5-flash',
            tokens_used=key_points_result.get('tokens', 0),
            processing_time_seconds=key_points_result['time'],
            gemini_response=key_points_result.get('response', {})
        )

        # 4. Sentiment Analysis
        sentiment_result = analyze_sentiment(model, formatted_transcript)
        AIAnalysis.objects.create(
            recording=recording,
            analysis_type='sentiment',
            result_data=sentiment_result['data'],
            result_text=sentiment_result['text'],
            model_version='gemini-1.5-flash',
            tokens_used=sentiment_result.get('tokens', 0),
            processing_time_seconds=sentiment_result['time'],
            gemini_response=sentiment_result.get('response', {})
        )

        # Update step
        step.status = 'completed'
        step.completed_at = timezone.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        step.save()

        # Mark recording as completed
        recording.status = 'completed'
        recording.completed_at = timezone.now()
        recording.save()

        # Mark job as completed
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.progress_percentage = 100
        job.save()

        logger.info(f"AI analysis completed for {recording_id}")
        return recording_id

    except Exception as exc:
        logger.error(f"AI analysis failed for {recording_id}: {exc}")
        if step:
            step.status = 'failed'
            step.error_message = str(exc)
            step.save()

        # Mark recording as failed
        recording.status = 'failed'
        recording.error_message = str(exc)
        recording.save()

        raise self.retry(exc=exc, countdown=180)


# Helper functions for AI analysis

def format_transcript_with_speakers(transcription):
    """Format transcript with speaker labels for better AI analysis"""
    segments = transcription.segments.all()
    formatted_lines = []

    for segment in segments:
        speaker = segment.speaker_label or "Unknown Speaker"
        formatted_lines.append(f"{speaker}: {segment.text}")

    return "\n".join(formatted_lines)


def generate_summary(model, transcript):
    """Generate a concise summary using Gemini"""
    start_time = time.time()

    prompt = f"""Please provide a concise summary of the following conversation or recording.
Focus on the main topics discussed, key decisions made, and overall purpose of the conversation.
Keep the summary to 2-3 paragraphs.

Transcript:
{transcript}

Summary:"""

    response = model.generate_content(prompt)
    processing_time = time.time() - start_time

    summary_text = response.text

    return {
        'data': {
            'summary': summary_text,
            'word_count': len(summary_text.split())
        },
        'text': summary_text,
        'time': processing_time,
        'tokens': response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
        'response': {}
    }


def extract_action_items(model, transcript):
    """Extract action items with timestamps"""
    start_time = time.time()

    prompt = f"""Analyze the following conversation and extract all action items, tasks, and to-dos mentioned.
For each action item, provide:
- The action/task description
- Priority level (high/medium/low)
- Who it's assigned to (if mentioned)

Format as a numbered list.

Transcript:
{transcript}

Action Items:"""

    response = model.generate_content(prompt)
    processing_time = time.time() - start_time

    items_text = response.text

    # Parse action items (simple parsing - can be enhanced)
    items = []
    for line in items_text.split('\n'):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith('-') or line.startswith('*')):
            items.append(line)

    return {
        'data': {
            'items': items,
            'total_count': len(items)
        },
        'text': items_text,
        'time': processing_time,
        'tokens': response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
        'response': {}
    }


def extract_key_points(model, transcript):
    """Extract key points and highlights"""
    start_time = time.time()

    prompt = f"""Analyze the following conversation and identify the most important key points and highlights.
Focus on:
- Main topics discussed
- Important decisions or conclusions
- Notable quotes or statements
- Critical information shared

Format as a bulleted list (5-10 key points).

Transcript:
{transcript}

Key Points:"""

    response = model.generate_content(prompt)
    processing_time = time.time() - start_time

    key_points_text = response.text

    # Parse key points
    points = []
    for line in key_points_text.split('\n'):
        line = line.strip()
        if line and (line.startswith('-') or line.startswith('*') or line.startswith('•')):
            points.append(line)

    return {
        'data': {
            'points': points,
            'total_count': len(points)
        },
        'text': key_points_text,
        'time': processing_time,
        'tokens': response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
        'response': {}
    }


def analyze_sentiment(model, transcript):
    """Analyze sentiment and tone of the conversation"""
    start_time = time.time()

    prompt = f"""Analyze the sentiment and tone of the following conversation.
Provide:
- Overall sentiment (positive/neutral/negative)
- Tone characteristics (professional, casual, tense, collaborative, etc.)
- Emotional indicators
- Notable shifts in sentiment or tone

Transcript:
{transcript}

Sentiment Analysis:"""

    response = model.generate_content(prompt)
    processing_time = time.time() - start_time

    sentiment_text = response.text

    return {
        'data': {
            'analysis': sentiment_text
        },
        'text': sentiment_text,
        'time': processing_time,
        'tokens': response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
        'response': {}
    }
