from rest_framework import serializers
from .models import Recording, RecordingFile, RecordingAnalysis


class RecordingFileSerializer(serializers.ModelSerializer):
    """Serializer for RecordingFile model"""
    class Meta:
        model = RecordingFile
        fields = ['id', 'file_type', 's3_key', 's3_bucket', 'file_size_bytes', 'created_at']
        read_only_fields = ['id', 'created_at']


class RecordingAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for RecordingAnalysis model"""
    class Meta:
        model = RecordingAnalysis
        fields = [
            # Transcription fields
            'transcription_text',
            'transcription_confidence',
            'transcription_language',
            'transcription_num_speakers',
            'transcription_audio_duration',
            'transcription_processing_time',
            'transcription_segments',
            
            # Summary fields
            'summary_text',
            'summary_data',
            'summary_tokens',
            'summary_processing_time',
            'summary_model_version',
            
            # Action items fields
            'action_items_text',
            'action_items_data',
            'action_items_tokens',
            'action_items_processing_time',
            'action_items_model_version',
            
            # Key points fields
            'key_points_text',
            'key_points_data',
            'key_points_tokens',
            'key_points_processing_time',
            'key_points_model_version',
            
            # Sentiment fields
            'sentiment_text',
            'sentiment_data',
            'sentiment_tokens',
            'sentiment_processing_time',
            'sentiment_model_version',
            
            # Metadata
            'total_tokens_used',
            'total_processing_time',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class RecordingSerializer(serializers.ModelSerializer):
    """Serializer for Recording model with full analysis"""
    files = RecordingFileSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    analysis = RecordingAnalysisSerializer(read_only=True)

    class Meta:
        model = Recording
        fields = [
            'id', 'user', 'title', 'quality', 'fps', 'duration_seconds',
            'has_system_audio', 'has_microphone', 'original_filename',
            'file_size_bytes', 'mime_type', 'codec', 'status',
            'error_message', 'processing_progress', 'processing_started_at',
            'files', 'analysis', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'error_message', 'processing_progress',
            'processing_started_at', 'created_at', 'updated_at', 'completed_at'
        ]


class RecordingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing recordings"""
    duration = serializers.FloatField(source='duration_seconds', read_only=True)
    has_audio = serializers.SerializerMethodField()
    analysis = serializers.SerializerMethodField()
    
    class Meta:
        model = Recording
        fields = [
            'id', 'title', 'quality', 'duration', 'status',
            'processing_progress', 'original_filename', 'file_size_bytes', 
            'has_audio', 'error_message', 'created_at', 'analysis'
        ]
        read_only_fields = fields
    
    def get_has_audio(self, obj):
        """Return True if recording has any audio (system or microphone)"""
        return obj.has_system_audio or obj.has_microphone
    
    def get_analysis(self, obj):
        """Return minimal analysis preview for list view"""
        try:
            analysis = obj.analysis
            if analysis:
                return {
                    'transcription_num_speakers': analysis.transcription_num_speakers,
                    'has_summary': bool(analysis.summary_text),
                    'has_action_items': bool(analysis.action_items_text),
                    'has_key_points': bool(analysis.key_points_text),
                }
        except Exception:
            pass
        return None


class RecordingUploadRequestSerializer(serializers.Serializer):
    """Serializer for upload request"""
    filename = serializers.CharField(max_length=500)
    file_size = serializers.IntegerField(min_value=1)
    quality = serializers.ChoiceField(choices=['480p', '720p', '1080p', '4k'], default='1080p')
    fps = serializers.IntegerField(default=30, min_value=1, max_value=120)
    has_system_audio = serializers.BooleanField(default=False)
    has_microphone = serializers.BooleanField(default=False)
    codec = serializers.CharField(max_length=50, required=False, allow_blank=True)


class RecordingUploadCompleteSerializer(serializers.Serializer):
    """Serializer for upload completion notification"""
    s3_key = serializers.CharField(max_length=500)
