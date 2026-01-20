from rest_framework import serializers
from .models import Recording, RecordingFile


class RecordingFileSerializer(serializers.ModelSerializer):
    """Serializer for RecordingFile model"""
    class Meta:
        model = RecordingFile
        fields = ['id', 'file_type', 's3_key', 's3_bucket', 'file_size_bytes', 'created_at']
        read_only_fields = ['id', 'created_at']


class RecordingSerializer(serializers.ModelSerializer):
    """Serializer for Recording model"""
    files = RecordingFileSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Recording
        fields = [
            'id', 'user', 'title', 'quality', 'fps', 'duration_seconds',
            'has_system_audio', 'has_microphone', 'original_filename',
            'file_size_bytes', 'mime_type', 'codec', 'status',
            'error_message', 'files', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'error_message', 'created_at',
            'updated_at', 'completed_at'
        ]


class RecordingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing recordings"""
    class Meta:
        model = Recording
        fields = [
            'id', 'title', 'quality', 'duration_seconds', 'status',
            'original_filename', 'file_size_bytes', 'created_at'
        ]
        read_only_fields = fields


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
