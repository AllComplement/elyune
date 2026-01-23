from django.contrib import admin
from .models import Transcription, TranscriptionSegment, AIAnalysis

class TranscriptionSegmentInline(admin.TabularInline):
    model = TranscriptionSegment
    extra = 0
    readonly_fields = ('start_time_seconds', 'end_time_seconds', 'speaker_label', 'text', 'confidence_score')
    can_delete = False
    ordering = ('start_time_seconds',)

@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'recording', 'confidence_score', 'language_detected', 'num_speakers', 'created_at')
    list_filter = ('language_detected', 'created_at')
    search_fields = ('recording__id', 'full_text')
    readonly_fields = ('id', 'created_at', 'deepgram_response')
    inlines = [TranscriptionSegmentInline]

@admin.register(TranscriptionSegment)
class TranscriptionSegmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'transcription', 'time_range', 'speaker_label', 'text_preview')
    list_filter = ('speaker_label',)
    search_fields = ('text', 'transcription__recording__id')
    readonly_fields = ('id', 'created_at', 'words')

    def time_range(self, obj):
        return f"{obj.start_time_seconds:.1f}s - {obj.end_time_seconds:.1f}s"
    time_range.short_description = 'Time'

    def text_preview(self, obj):
        return (obj.text[:75] + '..') if len(obj.text) > 75 else obj.text
    text_preview.short_description = 'Text'

@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'recording', 'analysis_type', 'model_version', 'tokens_used', 'created_at')
    list_filter = ('analysis_type', 'model_version', 'created_at')
    search_fields = ('recording__id', 'result_text')
    readonly_fields = ('id', 'created_at', 'gemini_response', 'result_data')
