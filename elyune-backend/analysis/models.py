from django.db import models
import uuid


class Transcription(models.Model):
    """Speech-to-text transcription with diarization"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.OneToOneField('recordings.Recording', on_delete=models.CASCADE, related_name='transcription')

    # Full transcript
    full_text = models.TextField()

    # Deepgram metadata
    confidence_score = models.FloatField()
    language_detected = models.CharField(max_length=10, default='en')

    # Speaker diarization
    num_speakers = models.IntegerField(default=0)

    # Processing info
    audio_duration_seconds = models.FloatField()
    processing_time_seconds = models.FloatField()

    # Raw API response (for debugging/reprocessing)
    deepgram_response = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transcription for {self.recording.id}"


class TranscriptionSegment(models.Model):
    """Individual utterances with speaker info and timestamps"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcription = models.ForeignKey(Transcription, on_delete=models.CASCADE, related_name='segments')

    # Timing
    start_time_seconds = models.FloatField()
    end_time_seconds = models.FloatField()

    # Content
    text = models.TextField()
    confidence_score = models.FloatField()

    # Speaker diarization
    speaker_id = models.IntegerField(null=True, blank=True)
    speaker_label = models.CharField(max_length=50, blank=True)

    # Word-level timing (optional)
    words = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time_seconds']
        indexes = [
            models.Index(fields=['transcription', 'start_time_seconds']),
            models.Index(fields=['speaker_id']),
        ]

    def __str__(self):
        return f"Segment at {self.start_time_seconds}s"


class AIAnalysis(models.Model):
    """Gemini AI analysis results"""
    ANALYSIS_TYPE_CHOICES = [
        ('summary', 'Summary'),
        ('action_items', 'Action Items'),
        ('key_points', 'Key Points'),
        ('sentiment', 'Sentiment Analysis'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey('recordings.Recording', on_delete=models.CASCADE, related_name='ai_analyses')

    analysis_type = models.CharField(max_length=20, choices=ANALYSIS_TYPE_CHOICES)

    # Results (structured)
    result_data = models.JSONField(default=dict)
    # Example for action_items: {"items": [{"text": "...", "priority": "high", "assignee": null}]}
    # Example for summary: {"summary": "...", "word_count": 150}

    # Text output (human-readable)
    result_text = models.TextField()

    # Gemini metadata
    model_version = models.CharField(max_length=50)
    tokens_used = models.IntegerField(default=0)
    processing_time_seconds = models.FloatField()

    # Raw API response
    gemini_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['recording', 'analysis_type']]
        indexes = [
            models.Index(fields=['recording', 'analysis_type']),
        ]

    def __str__(self):
        return f"{self.analysis_type} for {self.recording.id}"
