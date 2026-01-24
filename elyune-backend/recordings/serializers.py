from rest_framework import serializers
from .models import Recording, RecordingFile, RecordingAnalysis
import boto3
from django.conf import settings
from botocore.exceptions import ClientError


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
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = [
            'id', 'user', 'title', 'quality', 'fps', 'duration_seconds',
            'has_system_audio', 'has_microphone', 'original_filename',
            'file_size_bytes', 'mime_type', 'codec', 'status',
            'error_message', 'processing_progress', 'processing_started_at',
            'files', 'analysis', 'video_url', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'error_message', 'processing_progress',
            'processing_started_at', 'video_url', 'created_at', 'updated_at', 'completed_at'
        ]

    def get_video_url(self, obj):
        """
        Generate presigned URL for the MP4 video file.
        Returns None if video is not available yet.
        Uses prefetched files to avoid extra query.
        """
        try:
            # Use prefetched files to avoid extra query
            # obj.files is already loaded via prefetch_related in viewset
            mp4_file = None
            for file in obj.files.all():
                if file.file_type == 'converted_mp4':
                    mp4_file = file
                    break
            
            if not mp4_file:
                return None
            
            # Initialize S3 client with public endpoint for browser access
            s3_client_public = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_PUBLIC_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=boto3.session.Config(signature_version='s3v4')
            )
            
            # Generate presigned URL for GET operation (1 hour expiry)
            presigned_url = s3_client_public.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': mp4_file.s3_bucket,
                    'Key': mp4_file.s3_key,
                },
                ExpiresIn=3600  # 1 hour
            )
            
            return presigned_url
            
        except (ClientError, Exception) as e:
            # Log error but don't fail the entire serialization
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate presigned URL for recording {obj.id}: {e}")
            return None


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
