from django.contrib import admin
from django.utils.html import format_html
from .models import Recording, RecordingFile, RecordingAnalysis

class RecordingFileInline(admin.TabularInline):
    model = RecordingFile
    extra = 0
    readonly_fields = ('id', 'file_type', 's3_key', 's3_bucket', 'file_size_bytes', 'created_at')
    can_delete = False


class RecordingAnalysisInline(admin.StackedInline):
    """Inline display of analysis data for a recording"""
    model = RecordingAnalysis
    extra = 0
    can_delete = False
    readonly_fields = (
        'id', 'created_at',
        'transcription_summary',
        'ai_analysis_summary',
        'processing_stats'
    )
    fields = (
        'id', 'created_at',
        'transcription_summary',
        'ai_analysis_summary', 
        'processing_stats'
    )
    
    def transcription_summary(self, obj):
        """Display transcription overview"""
        if not obj or not obj.transcription_text:
            return "No transcription available"
        
        text_preview = obj.transcription_text[:200] + "..." if len(obj.transcription_text) > 200 else obj.transcription_text
        
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">'
            '<strong>Language:</strong> {} | <strong>Speakers:</strong> {} | <strong>Confidence:</strong> {:.2%}<br>'
            '<strong>Duration:</strong> {:.1f}s | <strong>Segments:</strong> {}<br><br>'
            '<strong>Text Preview:</strong><br>{}'
            '</div>',
            obj.transcription_language or 'Unknown',
            obj.transcription_num_speakers or 0,
            obj.transcription_confidence or 0,
            obj.transcription_audio_duration or 0,
            len(obj.transcription_segments) if obj.transcription_segments else 0,
            text_preview
        )
    transcription_summary.short_description = 'Transcription'
    
    def ai_analysis_summary(self, obj):
        """Display AI analysis overview"""
        if not obj:
            return "No analysis available"
        
        parts = []
        
        if obj.summary_text:
            parts.append(f'<strong>Summary:</strong> {obj.summary_text[:150]}...')
        
        if obj.action_items_text:
            parts.append(f'<strong>Action Items:</strong><br>{obj.action_items_text[:200]}...')
        
        if obj.key_points_text:
            parts.append(f'<strong>Key Points:</strong><br>{obj.key_points_text[:200]}...')
        
        if obj.sentiment_text:
            parts.append(f'<strong>Sentiment:</strong> {obj.sentiment_text[:100]}...')
        
        if not parts:
            return "No AI analysis available"
        
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">{}</div>',
            '<br><br>'.join(parts)
        )
    ai_analysis_summary.short_description = 'AI Analysis'
    
    def processing_stats(self, obj):
        """Display processing statistics"""
        if not obj:
            return "No stats available"
        
        return format_html(
            '<div style="background: #e3f2fd; padding: 10px; border-radius: 5px;">'
            '<strong>Total Tokens Used:</strong> {:,}<br>'
            '<strong>Total Processing Time:</strong> {:.2f}s<br><br>'
            '<strong>Breakdown:</strong><br>'
            '• Transcription: {:.2f}s<br>'
            '• Summary: {:.2f}s ({} tokens)<br>'
            '• Action Items: {:.2f}s ({} tokens)<br>'
            '• Key Points: {:.2f}s ({} tokens)<br>'
            '• Sentiment: {:.2f}s ({} tokens)'
            '</div>',
            obj.total_tokens_used or 0,
            obj.total_processing_time or 0,
            obj.transcription_processing_time or 0,
            obj.summary_processing_time or 0, obj.summary_tokens or 0,
            obj.action_items_processing_time or 0, obj.action_items_tokens or 0,
            obj.key_points_processing_time or 0, obj.key_points_tokens or 0,
            obj.sentiment_processing_time or 0, obj.sentiment_tokens or 0
        )
    processing_stats.short_description = 'Processing Stats'


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_or_filename', 'user', 'status', 'processing_progress', 'quality', 'duration_fmt', 'created_at')
    list_filter = ('status', 'quality', 'created_at', 'has_microphone', 'has_system_audio')
    search_fields = ('title', 'original_filename', 'user__username', 'id', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'completed_at', 'celery_task_id', 'processing_started_at')
    inlines = [RecordingFileInline, RecordingAnalysisInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'user', 'title', 'original_filename', 'status', 'error_message')
        }),
        ('Recording Details', {
            'fields': ('quality', 'fps', 'duration_seconds', 'file_size_bytes', 'mime_type', 'codec',
                      'has_system_audio', 'has_microphone')
        }),
        ('Processing', {
            'fields': ('processing_progress', 'processing_started_at', 'celery_task_id')
        }),
        ('Sharing', {
            'fields': ('is_public', 'public_share_token'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        })
    )
    
    def title_or_filename(self, obj):
        return obj.title or obj.original_filename
    title_or_filename.short_description = 'Title / Filename'

    def duration_fmt(self, obj):
        if obj.duration_seconds:
            mins, secs = divmod(int(obj.duration_seconds), 60)
            return f"{mins}:{secs:02d}"
        return "-"
    duration_fmt.short_description = 'Duration'

@admin.register(RecordingFile)
class RecordingFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'recording_link', 'user', 'file_type', 'file_size_mb', 'created_at')
    list_filter = ('file_type', 'created_at')
    search_fields = ('recording__id', 's3_key', 'user__username')
    readonly_fields = ('id', 'created_at')

    def recording_link(self, obj):
        return obj.recording
    recording_link.short_description = 'Recording'

    def file_size_mb(self, obj):
        return f"{obj.file_size_bytes / (1024*1024):.2f} MB"
    file_size_mb.short_description = 'Size'


@admin.register(RecordingAnalysis)
class RecordingAnalysisAdmin(admin.ModelAdmin):
    """Admin for viewing consolidated analysis data"""
    list_display = ('id', 'recording', 'user', 'has_transcription', 'has_summary', 'total_tokens_used', 'created_at')
    list_filter = ('transcription_language', 'created_at')
    search_fields = ('recording__id', 'recording__title', 'transcription_text', 'summary_text')
    readonly_fields = ('id', 'created_at', 'updated_at', 'processing_summary')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'recording', 'user', 'created_at', 'updated_at')
        }),
        ('Transcription', {
            'fields': (
                'transcription_text', 'transcription_confidence', 'transcription_language',
                'transcription_num_speakers', 'transcription_audio_duration', 'transcription_processing_time',
                'transcription_segments', 'deepgram_response'
            )
        }),
        ('Summary Analysis', {
            'fields': (
                'summary_text', 'summary_data', 'summary_tokens', 
                'summary_processing_time', 'summary_model_version', 'summary_response'
            ),
            'classes': ('collapse',)
        }),
        ('Action Items', {
            'fields': (
                'action_items_text', 'action_items_data', 'action_items_tokens',
                'action_items_processing_time', 'action_items_model_version', 'action_items_response'
            ),
            'classes': ('collapse',)
        }),
        ('Key Points', {
            'fields': (
                'key_points_text', 'key_points_data', 'key_points_tokens',
                'key_points_processing_time', 'key_points_model_version', 'key_points_response'
            ),
            'classes': ('collapse',)
        }),
        ('Sentiment', {
            'fields': (
                'sentiment_text', 'sentiment_data', 'sentiment_tokens',
                'sentiment_processing_time', 'sentiment_model_version', 'sentiment_response'
            ),
            'classes': ('collapse',)
        }),
        ('Processing Summary', {
            'fields': ('processing_summary',)
        })
    )
    
    def has_transcription(self, obj):
        return bool(obj.transcription_text)
    has_transcription.boolean = True
    has_transcription.short_description = 'Transcription'
    
    def has_summary(self, obj):
        return bool(obj.summary_text)
    has_summary.boolean = True
    has_summary.short_description = 'Summary'
    
    def processing_summary(self, obj):
        """Display processing statistics summary"""
        return format_html(
            '<div style="background: #e8f5e9; padding: 15px; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Processing Statistics</h3>'
            '<strong>Total Tokens:</strong> {:,}<br>'
            '<strong>Total Time:</strong> {:.2f} seconds<br><br>'
            '<table style="width: 100%; border-collapse: collapse;">'
            '<tr style="background: #c8e6c9;"><th>Step</th><th>Time (s)</th><th>Tokens</th><th>Model</th></tr>'
            '<tr><td>Transcription</td><td>{:.2f}</td><td>-</td><td>Deepgram</td></tr>'
            '<tr><td>Summary</td><td>{:.2f}</td><td>{}</td><td>{}</td></tr>'
            '<tr><td>Action Items</td><td>{:.2f}</td><td>{}</td><td>{}</td></tr>'
            '<tr><td>Key Points</td><td>{:.2f}</td><td>{}</td><td>{}</td></tr>'
            '<tr><td>Sentiment</td><td>{:.2f}</td><td>{}</td><td>{}</td></tr>'
            '</table>'
            '</div>',
            obj.total_tokens_used or 0,
            obj.total_processing_time or 0,
            obj.transcription_processing_time or 0,
            obj.summary_processing_time or 0, obj.summary_tokens or 0, obj.summary_model_version or '-',
            obj.action_items_processing_time or 0, obj.action_items_tokens or 0, obj.action_items_model_version or '-',
            obj.key_points_processing_time or 0, obj.key_points_tokens or 0, obj.key_points_model_version or '-',
            obj.sentiment_processing_time or 0, obj.sentiment_tokens or 0, obj.sentiment_model_version or '-'
        )
    processing_summary.short_description = 'Processing Summary'
