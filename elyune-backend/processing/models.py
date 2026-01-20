from django.db import models
import uuid


class ProcessingJob(models.Model):
    """Track overall processing pipeline status"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.OneToOneField('recordings.Recording', on_delete=models.CASCADE, related_name='processing_job')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    current_step = models.CharField(max_length=50, blank=True)
    progress_percentage = models.IntegerField(default=0)

    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, blank=True)

    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['celery_task_id']),
        ]

    def __str__(self):
        return f"Job {self.id} - {self.status}"


class ProcessingStep(models.Model):
    """Individual processing step tracking"""
    STEP_CHOICES = [
        ('video_conversion', 'Video Conversion'),
        ('audio_extraction', 'Audio Extraction'),
        ('speech_to_text', 'Speech to Text'),
        ('ai_analysis', 'AI Analysis'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(ProcessingJob, on_delete=models.CASCADE, related_name='steps')

    step_name = models.CharField(max_length=50, choices=STEP_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Step details
    input_file = models.CharField(max_length=500, blank=True)
    output_file = models.CharField(max_length=500, blank=True)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    # Error handling
    error_message = models.TextField(blank=True)
    error_traceback = models.TextField(blank=True)

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['job', 'step_name']]
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['job', 'step_name']),
        ]

    def __str__(self):
        return f"{self.job.id} - {self.step_name} ({self.status})"
