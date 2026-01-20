from django.db import models
from django.contrib.auth.models import User
import uuid


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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recordings')

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

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.title or self.original_filename} ({self.id})"


class RecordingFile(models.Model):
    """File storage references for different formats"""
    FILE_TYPE_CHOICES = [
        ('original_webm', 'Original WebM'),
        ('converted_mp4', 'Converted MP4'),
        ('audio_extract', 'Extracted Audio'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(Recording, on_delete=models.CASCADE, related_name='files')

    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    s3_key = models.CharField(max_length=500)
    s3_bucket = models.CharField(max_length=100)
    file_size_bytes = models.BigIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['recording', 'file_type']]
        indexes = [
            models.Index(fields=['recording', 'file_type']),
        ]

    def __str__(self):
        return f"{self.recording.id} - {self.file_type}"
