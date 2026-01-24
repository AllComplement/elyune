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

        # Create or update processing job
        job, created = ProcessingJob.objects.update_or_create(
            recording=recording,
            defaults={
                'celery_task_id': self.request.id,
                'status': 'running',
                'started_at': timezone.now(),
                'completed_at': None,
                'error_message': ''
            }
        )

        logger.info(f"Started processing pipeline for recording {recording_id}")

        # Chain tasks: conversion → extraction → transcription → analysis
        # Note: subsequent tasks receive the return value (recording_id) from the previous task
        workflow = chain(
            convert_webm_to_mp4.s(recording_id),
            extract_audio_from_video.s(),
            transcribe_audio.s(),
            analyze_transcription.s()
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

        # Create or update processing step
        step, _ = ProcessingStep.objects.update_or_create(
            job=job,
            step_name='video_conversion',
            defaults={
                'status': 'running',
                'started_at': timezone.now(),
                'error_message': ''
            }
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

        # Save file reference (idempotent)
        RecordingFile.objects.update_or_create(
            recording=recording,
            file_type='converted_mp4',
            defaults={
                's3_key': s3_key,
                's3_bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'file_size_bytes': os.path.getsize(mp4_path)
            }
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

        # Create or update processing step
        step, _ = ProcessingStep.objects.update_or_create(
            job=job,
            step_name='audio_extraction',
            defaults={
                'status': 'running',
                'started_at': timezone.now(),
                'error_message': ''
            }
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

        # Save file reference (idempotent)
        RecordingFile.objects.update_or_create(
            recording=recording,
            file_type='audio_extract',
            defaults={
                's3_key': s3_key,
                's3_bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'file_size_bytes': os.path.getsize(audio_path)
            }
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

        # Create or update processing step
        step, _ = ProcessingStep.objects.update_or_create(
            job=job,
            step_name='speech_to_text',
            defaults={
                'status': 'running',
                'started_at': timezone.now(),
                'error_message': ''
            }
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
        utterances = response.results.utterances if hasattr(response.results, 'utterances') else []

        # Create or update Transcription
        transcription, created = Transcription.objects.update_or_create(
            recording=recording,
            defaults={
                'full_text': result.transcript,
                'confidence_score': result.confidence,
                'language_detected': response.metadata.language if hasattr(response.metadata, 'language') else 'en',
                'num_speakers': len(set(u.speaker for u in utterances)) if utterances else 0,
                'audio_duration_seconds': response.metadata.duration,
                'processing_time_seconds': processing_time,
                'deepgram_response': response.to_dict()
            }
        )

        # Clear existing segments if updating (to ensure clean slate for segments)
        if not created:
            transcription.segments.all().delete()

        # Create segments from utterances
        if utterances:
            for utterance in utterances:
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


# Parallel AI Analysis Sub-Tasks (for concurrent execution)

@shared_task(bind=True, max_retries=3)
def generate_and_save_summary(self, recording_id, formatted_transcript, model_name):
    """Generate summary analysis (parallel sub-task)"""
    import random
    from time import sleep
    
    try:
        recording = Recording.objects.get(id=recording_id)
        
        # Initialize Gemini (each task needs its own instance)
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        
        logger.info(f"[Summary] Starting for {recording_id}")
        
        # Generate analysis
        summary_result = generate_summary(model, formatted_transcript)
        
        # Save to database (idempotent)
        AIAnalysis.objects.update_or_create(
            recording=recording,
            analysis_type='summary',
            defaults={
                'result_data': summary_result['data'],
                'result_text': summary_result['text'],
                'model_version': model_name,
                'tokens_used': summary_result.get('tokens', 0),
                'processing_time_seconds': summary_result['time'],
                'gemini_response': summary_result.get('response', {})
            }
        )
        
        logger.info(f"[Summary] Completed for {recording_id} in {summary_result['time']:.2f}s")
        return {'type': 'summary', 'status': 'success', 'time': summary_result['time']}
        
    except Exception as exc:
        logger.error(f"[Summary] Failed for {recording_id}: {exc}")
        
        # Check for rate limiting
        error_str = str(exc).lower()
        if '429' in error_str or 'rate limit' in error_str or 'quota' in error_str:
            # Exponential backoff for rate limits
            wait_time = min((2 ** self.request.retries) + random.uniform(0, 1), 60)
            logger.warning(f"[Summary] Rate limited, waiting {wait_time:.2f}s before retry...")
            sleep(wait_time)
            raise self.retry(exc=exc, countdown=int(wait_time))
        
        # Store partial failure
        try:
            recording = Recording.objects.get(id=recording_id)
            AIAnalysis.objects.update_or_create(
                recording=recording,
                analysis_type='summary',
                defaults={'result_text': f'Failed: {str(exc)[:500]}'}
            )
        except Exception:
            pass
        
        return {'type': 'summary', 'status': 'failed', 'error': str(exc)[:200]}


@shared_task(bind=True, max_retries=3)
def generate_and_save_action_items(self, recording_id, formatted_transcript, model_name):
    """Extract action items analysis (parallel sub-task)"""
    import random
    from time import sleep
    
    try:
        recording = Recording.objects.get(id=recording_id)
        
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        
        logger.info(f"[ActionItems] Starting for {recording_id}")
        
        action_items_result = extract_action_items(model, formatted_transcript)
        
        AIAnalysis.objects.update_or_create(
            recording=recording,
            analysis_type='action_items',
            defaults={
                'result_data': action_items_result['data'],
                'result_text': action_items_result['text'],
                'model_version': model_name,
                'tokens_used': action_items_result.get('tokens', 0),
                'processing_time_seconds': action_items_result['time'],
                'gemini_response': action_items_result.get('response', {})
            }
        )
        
        logger.info(f"[ActionItems] Completed for {recording_id} in {action_items_result['time']:.2f}s")
        return {'type': 'action_items', 'status': 'success', 'time': action_items_result['time']}
        
    except Exception as exc:
        logger.error(f"[ActionItems] Failed for {recording_id}: {exc}")
        
        error_str = str(exc).lower()
        if '429' in error_str or 'rate limit' in error_str or 'quota' in error_str:
            wait_time = min((2 ** self.request.retries) + random.uniform(0, 1), 60)
            logger.warning(f"[ActionItems] Rate limited, waiting {wait_time:.2f}s before retry...")
            sleep(wait_time)
            raise self.retry(exc=exc, countdown=int(wait_time))
        
        try:
            recording = Recording.objects.get(id=recording_id)
            AIAnalysis.objects.update_or_create(
                recording=recording,
                analysis_type='action_items',
                defaults={'result_text': f'Failed: {str(exc)[:500]}'}
            )
        except Exception:
            pass
        
        return {'type': 'action_items', 'status': 'failed', 'error': str(exc)[:200]}


@shared_task(bind=True, max_retries=3)
def generate_and_save_key_points(self, recording_id, formatted_transcript, model_name):
    """Extract key points analysis (parallel sub-task)"""
    import random
    from time import sleep
    
    try:
        recording = Recording.objects.get(id=recording_id)
        
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        
        logger.info(f"[KeyPoints] Starting for {recording_id}")
        
        key_points_result = extract_key_points(model, formatted_transcript)
        
        AIAnalysis.objects.update_or_create(
            recording=recording,
            analysis_type='key_points',
            defaults={
                'result_data': key_points_result['data'],
                'result_text': key_points_result['text'],
                'model_version': model_name,
                'tokens_used': key_points_result.get('tokens', 0),
                'processing_time_seconds': key_points_result['time'],
                'gemini_response': key_points_result.get('response', {})
            }
        )
        
        logger.info(f"[KeyPoints] Completed for {recording_id} in {key_points_result['time']:.2f}s")
        return {'type': 'key_points', 'status': 'success', 'time': key_points_result['time']}
        
    except Exception as exc:
        logger.error(f"[KeyPoints] Failed for {recording_id}: {exc}")
        
        error_str = str(exc).lower()
        if '429' in error_str or 'rate limit' in error_str or 'quota' in error_str:
            wait_time = min((2 ** self.request.retries) + random.uniform(0, 1), 60)
            logger.warning(f"[KeyPoints] Rate limited, waiting {wait_time:.2f}s before retry...")
            sleep(wait_time)
            raise self.retry(exc=exc, countdown=int(wait_time))
        
        try:
            recording = Recording.objects.get(id=recording_id)
            AIAnalysis.objects.update_or_create(
                recording=recording,
                analysis_type='key_points',
                defaults={'result_text': f'Failed: {str(exc)[:500]}'}
            )
        except Exception:
            pass
        
        return {'type': 'key_points', 'status': 'failed', 'error': str(exc)[:200]}


@shared_task(bind=True, max_retries=3)
def generate_and_save_sentiment(self, recording_id, formatted_transcript, model_name):
    """Analyze sentiment (parallel sub-task)"""
    import random
    from time import sleep
    
    try:
        recording = Recording.objects.get(id=recording_id)
        
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        
        logger.info(f"[Sentiment] Starting for {recording_id}")
        
        sentiment_result = analyze_sentiment(model, formatted_transcript)
        
        AIAnalysis.objects.update_or_create(
            recording=recording,
            analysis_type='sentiment',
            defaults={
                'result_data': sentiment_result['data'],
                'result_text': sentiment_result['text'],
                'model_version': model_name,
                'tokens_used': sentiment_result.get('tokens', 0),
                'processing_time_seconds': sentiment_result['time'],
                'gemini_response': sentiment_result.get('response', {})
            }
        )
        
        logger.info(f"[Sentiment] Completed for {recording_id} in {sentiment_result['time']:.2f}s")
        return {'type': 'sentiment', 'status': 'success', 'time': sentiment_result['time']}
        
    except Exception as exc:
        logger.error(f"[Sentiment] Failed for {recording_id}: {exc}")
        
        error_str = str(exc).lower()
        if '429' in error_str or 'rate limit' in error_str or 'quota' in error_str:
            wait_time = min((2 ** self.request.retries) + random.uniform(0, 1), 60)
            logger.warning(f"[Sentiment] Rate limited, waiting {wait_time:.2f}s before retry...")
            sleep(wait_time)
            raise self.retry(exc=exc, countdown=int(wait_time))
        
        try:
            recording = Recording.objects.get(id=recording_id)
            AIAnalysis.objects.update_or_create(
                recording=recording,
                analysis_type='sentiment',
                defaults={'result_text': f'Failed: {str(exc)[:500]}'}
            )
        except Exception:
            pass
        
        return {'type': 'sentiment', 'status': 'failed', 'error': str(exc)[:200]}


@shared_task(bind=True, max_retries=1)
def finalize_parallel_analysis(self, results, recording_id):
    """
    Callback task to finalize parallel analysis results
    This is called after all 4 parallel tasks complete
    """
    try:
        recording = Recording.objects.get(id=recording_id)
        job = recording.processing_job
        step = ProcessingStep.objects.get(job=job, step_name='ai_analysis')
        
        # Analyze results
        failed_analyses = [r for r in results if r['status'] == 'failed']
        successful_analyses = [r for r in results if r['status'] == 'success']
        
        # Calculate total time (max of all parallel tasks)
        total_time = max([r.get('time', 0) for r in successful_analyses], default=0)
        
        logger.info(f"Parallel analysis complete: {len(successful_analyses)}/4 succeeded in {total_time:.2f}s")
        
        # Update step based on results
        if len(failed_analyses) == 4:
            # All failed - mark as failed
            step.status = 'failed'
            step.error_message = 'All AI analyses failed: ' + '; '.join([f"{f['type']}: {f.get('error', 'unknown')}" for f in failed_analyses])
            recording.status = 'failed'
            recording.error_message = step.error_message
            logger.error(f"All analyses failed for {recording_id}")
        elif failed_analyses:
            # Partial failure - mark as completed with warning
            failed_types = [f['type'] for f in failed_analyses]
            step.status = 'completed'
            step.error_message = f'{len(failed_analyses)}/4 analyses failed: {", ".join(failed_types)}'
            recording.status = 'completed'
            recording.completed_at = timezone.now()
            logger.warning(f"Partial success for {recording_id}: {failed_types} failed")
        else:
            # All succeeded
            step.status = 'completed'
            recording.status = 'completed'
            recording.completed_at = timezone.now()
            logger.info(f"All analyses succeeded for {recording_id}")
        
        step.completed_at = timezone.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        step.save()
        recording.save()

        # Mark job as completed (even with partial failures)
        if recording.status == 'completed':
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.progress_percentage = 100
            job.save()

        return recording_id
        
    except Exception as exc:
        logger.error(f"Failed to finalize parallel analysis for {recording_id}: {exc}")
        raise


@shared_task(bind=True, max_retries=2)
def analyze_transcription(self, recording_id):
    """
    Orchestrate parallel AI analysis using Celery groups with callback
    Generates: summary, action items, key points, sentiment analysis
    """
    step = None
    try:
        recording = Recording.objects.get(id=recording_id)
        job = recording.processing_job
        transcription = recording.transcription

        # Create or update processing step
        step, _ = ProcessingStep.objects.update_or_create(
            job=job,
            step_name='ai_analysis',
            defaults={
                'status': 'running',
                'started_at': timezone.now(),
                'error_message': ''
            }
        )

        logger.info(f"Starting parallel AI analysis for {recording_id}")

        # Check if Gemini API key is configured
        if not settings.GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not configured")

        import google.generativeai as genai
        from celery import chord

        # Configure Gemini and determine model
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model_name = 'gemini-2.5-flash'
        try:
            test_model = genai.GenerativeModel(model_name)
            test_model.generate_content("test")
        except Exception as e:
            logger.warning(f"Failed to use {model_name}, falling back to gemini-2.0-flash: {e}")
            model_name = 'gemini-2.0-flash'

        # Prepare transcript with speaker info
        formatted_transcript = format_transcript_with_speakers(transcription)

        # Launch all 4 analyses in parallel using Celery chord (group + callback)
        logger.info(f"Launching 4 parallel analysis tasks for {recording_id}")
        
        # Use chord: run tasks in parallel, then call callback with results
        callback = finalize_parallel_analysis.s(str(recording_id))
        parallel_workflow = chord([
            generate_and_save_summary.s(str(recording_id), formatted_transcript, model_name),
            generate_and_save_action_items.s(str(recording_id), formatted_transcript, model_name),
            generate_and_save_key_points.s(str(recording_id), formatted_transcript, model_name),
            generate_and_save_sentiment.s(str(recording_id), formatted_transcript, model_name),
        ])(callback)
        
        logger.info(f"Parallel tasks launched for {recording_id}, callback will finalize")
        return recording_id

    except Exception as exc:
        logger.error(f"AI analysis orchestration failed for {recording_id}: {exc}")
        if step:
            step.status = 'failed'
            step.error_message = str(exc)
            step.save()

        # Mark recording as failed
        if 'recording' in locals():
            recording.status = 'failed'
            recording.error_message = str(exc)
            recording.save()

        raise self.retry(exc=exc, countdown=120)


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
