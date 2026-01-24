from django.db import models
from django.contrib.auth.models import User
import uuid
import secrets


class Recording(models.Model):
    """Main recording metadata"""
    QUALITY_CHOICES = [
        ('480p', '480p'),
        ('720p', '720p'),
        ('1080p', '1080p'),
        ('4k', '4K'),
    ]

    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recordings', null=True, blank=True)

    # Recording metadata from extension
    title = models.CharField(max_length=255, blank=True)
    quality = models.CharField(max_length=10, choices=QUALITY_CHOICES)
    fps = models.IntegerField(default=30)
    duration_seconds = models.FloatField(null=True, blank=True)

    # Audio settings
    has_system_audio = models.BooleanField(default=False)
    has_microphone = models.BooleanField(default=False)

    # File info
    original_filename = models.CharField(max_length=500)
    file_size_bytes = models.BigIntegerField()
    mime_type = models.CharField(max_length=100, default='video/webm')
    codec = models.CharField(max_length=50, blank=True)

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    error_message = models.TextField(blank=True)

    # Processing tracking (consolidated from ProcessingJob)
    celery_task_id = models.CharField(max_length=255, blank=True)
    processing_progress = models.IntegerField(default=0, help_text='Processing progress percentage (0-100)')
    processing_started_at = models.DateTimeField(null=True, blank=True)

    # Sharing (for future use)
    is_public = models.BooleanField(default=False, help_text='Allow public access via share link')
    public_share_token = models.CharField(max_length=32, unique=True, null=True, blank=True, db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['celery_task_id']),
        ]

    def __str__(self):
        return f"{self.title or self.original_filename} ({self.id})"

    def generate_share_token(self):
        """Generate a unique share token for public access"""
        if not self.public_share_token:
            self.public_share_token = secrets.token_urlsafe(24)
            self.save(update_fields=['public_share_token'])
        return self.public_share_token


class RecordingFile(models.Model):
    """File storage references for different formats"""
    FILE_TYPE_CHOICES = [
        ('original_webm', 'Original WebM'),
        ('converted_mp4', 'Converted MP4'),
        ('audio_extract', 'Extracted Audio'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, related_name='files')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recording_files', null=True, blank=True)

    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    s3_key = models.CharField(max_length=500)
    s3_bucket = models.CharField(max_length=100)
    file_size_bytes = models.BigIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['recording', 'file_type']]
        indexes = [
            models.Index(fields=['recording', 'file_type']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.recording.id} - {self.file_type}"


class RecordingAnalysis(models.Model):
    """Consolidated transcription and AI analysis results"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.OneToOneField(Recording, on_delete=models.CASCADE, related_name='analysis')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recording_analyses', null=True, blank=True)

    # ===== TRANSCRIPTION FIELDS (from Transcription model) =====
    transcription_text = models.TextField(blank=True, help_text='Full transcript text')
    transcription_confidence = models.FloatField(null=True, blank=True, help_text='Overall confidence score (0-1)')
    transcription_language = models.CharField(max_length=10, default='en', help_text='Detected language code')
    transcription_num_speakers = models.IntegerField(default=0, help_text='Number of speakers detected')
    transcription_audio_duration = models.FloatField(null=True, blank=True, help_text='Audio duration in seconds')
    transcription_processing_time = models.FloatField(null=True, blank=True, help_text='Processing time in seconds')
    
    # Transcription segments (consolidated from TranscriptionSegment model)
    transcription_segments = models.JSONField(default=list, blank=True, help_text='Array of segment objects with speaker, timing, text')
    # Format: [{"start": 0.5, "end": 3.2, "text": "...", "confidence": 0.95, "speaker_id": 0, "speaker_label": "Speaker 1", "words": [...]}]
    
    # Raw Deepgram response (for debugging/reprocessing)
    deepgram_response = models.JSONField(default=dict, blank=True)

    # ===== SUMMARY FIELDS (from AIAnalysis type='summary') =====
    summary_text = models.TextField(blank=True, help_text='Human-readable summary')
    summary_data = models.JSONField(default=dict, blank=True, help_text='Structured summary data')
    summary_tokens = models.IntegerField(null=True, blank=True, help_text='Tokens used for summary')
    summary_processing_time = models.FloatField(null=True, blank=True, help_text='Summary generation time in seconds')
    summary_model_version = models.CharField(max_length=50, blank=True)
    summary_response = models.JSONField(default=dict, blank=True, help_text='Raw Gemini response for summary')

    # ===== ACTION ITEMS FIELDS (from AIAnalysis type='action_items') =====
    action_items_text = models.TextField(blank=True, help_text='Human-readable action items')
    action_items_data = models.JSONField(default=dict, blank=True, help_text='Structured action items')
    # Format: {"items": [{"text": "...", "priority": "high", "assignee": null, "due_date": null}]}
    action_items_tokens = models.IntegerField(null=True, blank=True)
    action_items_processing_time = models.FloatField(null=True, blank=True)
    action_items_model_version = models.CharField(max_length=50, blank=True)
    action_items_response = models.JSONField(default=dict, blank=True)

    # ===== KEY POINTS FIELDS (from AIAnalysis type='key_points') =====
    key_points_text = models.TextField(blank=True, help_text='Human-readable key points')
    key_points_data = models.JSONField(default=dict, blank=True, help_text='Structured key points')
    # Format: {"points": [{"text": "...", "importance": "high", "category": "decision"}]}
    key_points_tokens = models.IntegerField(null=True, blank=True)
    key_points_processing_time = models.FloatField(null=True, blank=True)
    key_points_model_version = models.CharField(max_length=50, blank=True)
    key_points_response = models.JSONField(default=dict, blank=True)

    # ===== SENTIMENT FIELDS (from AIAnalysis type='sentiment') =====
    sentiment_text = models.TextField(blank=True, help_text='Human-readable sentiment analysis')
    sentiment_data = models.JSONField(default=dict, blank=True, help_text='Structured sentiment data')
    # Format: {"overall": "positive", "score": 0.75, "emotions": ["confident", "enthusiastic"], "tone": "professional"}
    sentiment_tokens = models.IntegerField(null=True, blank=True)
    sentiment_processing_time = models.FloatField(null=True, blank=True)
    sentiment_model_version = models.CharField(max_length=50, blank=True)
    sentiment_response = models.JSONField(default=dict, blank=True)

    # ===== SHARED METADATA =====
    total_tokens_used = models.IntegerField(default=0, help_text='Total tokens across all analyses')
    total_processing_time = models.FloatField(default=0.0, help_text='Total processing time in seconds')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['recording']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Analysis for {self.recording.id}"

    def update_totals(self):
        """Recalculate total tokens and processing time"""
        self.total_tokens_used = sum(filter(None, [
            self.summary_tokens,
            self.action_items_tokens,
            self.key_points_tokens,
            self.sentiment_tokens,
        ]))
        self.total_processing_time = sum(filter(None, [
            self.transcription_processing_time or 0,
            self.summary_processing_time or 0,
            self.action_items_processing_time or 0,
            self.key_points_processing_time or 0,
            self.sentiment_processing_time or 0,
        ]))
        self.save(update_fields=['total_tokens_used', 'total_processing_time', 'updated_at'])
