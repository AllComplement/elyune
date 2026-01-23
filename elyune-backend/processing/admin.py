from django.contrib import admin
from .models import ProcessingJob, ProcessingStep

class ProcessingStepInline(admin.TabularInline):
    model = ProcessingStep
    extra = 0
    readonly_fields = ('step_name', 'status', 'started_at', 'completed_at', 'duration_seconds', 'error_message')
    can_delete = False
    ordering = ('created_at',)

@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'recording_link', 'status', 'current_step', 'progress_percentage', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('recording__id', 'celery_task_id', 'error_message')
    readonly_fields = ('id', 'created_at', 'started_at', 'completed_at')
    inlines = [ProcessingStepInline]

    def recording_link(self, obj):
        return obj.recording
    recording_link.short_description = 'Recording'

@admin.register(ProcessingStep)
class ProcessingStepAdmin(admin.ModelAdmin):
    list_display = ('id', 'job_link', 'step_name', 'status', 'duration_seconds', 'created_at')
    list_filter = ('step_name', 'status', 'created_at')
    search_fields = ('job__id', 'job__recording__id', 'error_message')
    readonly_fields = ('id', 'created_at', 'started_at', 'completed_at', 'metadata')

    def job_link(self, obj):
        return obj.job
    job_link.short_description = 'Job'
