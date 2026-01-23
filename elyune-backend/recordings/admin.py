from django.contrib import admin
from .models import Recording, RecordingFile

class RecordingFileInline(admin.TabularInline):
    model = RecordingFile
    extra = 0
    readonly_fields = ('id', 'file_type', 's3_key', 's3_bucket', 'file_size_bytes', 'created_at')
    can_delete = False

@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title_or_filename', 'user', 'status', 'quality', 'duration_fmt', 'created_at')
    list_filter = ('status', 'quality', 'created_at', 'has_microphone', 'has_system_audio')
    search_fields = ('title', 'original_filename', 'user__username', 'id', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'completed_at')
    inlines = [RecordingFileInline]
    
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
    list_display = ('id', 'recording_link', 'file_type', 'file_size_mb', 'created_at')
    list_filter = ('file_type', 'created_at')
    search_fields = ('recording__id', 's3_key')
    readonly_fields = ('id', 'created_at')

    def recording_link(self, obj):
        return obj.recording
    recording_link.short_description = 'Recording'

    def file_size_mb(self, obj):
        return f"{obj.file_size_bytes / (1024*1024):.2f} MB"
    file_size_mb.short_description = 'Size'
