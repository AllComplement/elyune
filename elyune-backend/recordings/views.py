from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Recording, RecordingFile
from .serializers import (
    RecordingSerializer,
    RecordingListSerializer,
    RecordingUploadRequestSerializer,
    RecordingUploadCompleteSerializer
)
import boto3
from django.conf import settings
from botocore.exceptions import ClientError


class RecordingViewSet(viewsets.ModelViewSet):
    """ViewSet for Recording model"""
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        Allow anonymous access for:
        - request_upload: Create recording and get upload URL
        - upload_complete: Trigger processing after upload
        
        Require authentication for:
        - list: View user's recordings
        - retrieve: View specific recording details
        - update/delete: Modify recordings
        """
        if self.action in ['request_upload', 'upload_complete']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return RecordingListSerializer
        return RecordingSerializer

    def get_queryset(self):
        """
        Users can only see their own recordings.
        Anonymous users cannot list recordings.
        
        Query optimization:
        - select_related('analysis'): JOIN RecordingAnalysis (1-to-1) in single query
        - prefetch_related('files'): Efficiently fetch all RecordingFiles in one query
        
        This reduces queries from ~7+ to ~3 per recording detail request.
        """
        if not self.request.user.is_authenticated:
            return Recording.objects.none()
            
        return Recording.objects.select_related(
            'analysis'
        ).prefetch_related(
            'files'
        ).filter(user=self.request.user)

    def perform_create(self, serializer):
        """Auto-assign user when creating recording"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='request-upload')
    def request_upload(self, request):
        """
        Generate presigned URL for direct S3 upload

        Request body:
        {
            "filename": "recording.webm",
            "file_size": 10485760,
            "quality": "1080p",
            "fps": 30,
            "has_system_audio": true,
            "has_microphone": false,
            "codec": "vp9"
        }

        Response:
        {
            "recording_id": "uuid",
            "upload_url": "https://minio:9000/...",
            "s3_key": "recordings/uuid/filename.webm"
        }
        """
        serializer = RecordingUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Create recording record
        # Allow null user for anonymous recordings
        recording = Recording.objects.create(
            user=request.user if request.user.is_authenticated else None,
            original_filename=data['filename'],
            file_size_bytes=data['file_size'],
            quality=data['quality'],
            fps=data.get('fps', 30),
            has_system_audio=data.get('has_system_audio', False),
            has_microphone=data.get('has_microphone', False),
            codec=data.get('codec', ''),
            status='uploading'
        )

        # Generate S3 key
        s3_key = f"recordings/{recording.id}/{data['filename']}"

        try:
            # Initialize S3 client for MinIO (Public Endpoint for Signing)
            # We must use the public endpoint for signing so the signature matches
            # the URL the browser will use.
            s3_client_public = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_PUBLIC_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=boto3.session.Config(signature_version='s3v4')
            )

            # Generate presigned URL for PUT operation
            # We exclude ContentType from the signature params to allow the browser
            # flexibility (e.g. if it adds charset or if headers are slightly different)
            # The Content-Type header will still be sent by the browser, but not verified against signature.
            presigned_url = s3_client_public.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': s3_key,
                },
                ExpiresIn=3600  # 1 hour
            )

            return Response({
                'recording_id': str(recording.id),
                'upload_url': presigned_url,
                's3_key': s3_key
            }, status=status.HTTP_201_CREATED)

        except ClientError as e:
            recording.status = 'failed'
            recording.error_message = f"Failed to generate upload URL: {str(e)}"
            recording.save()
            return Response(
                {'error': 'Failed to generate upload URL'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='upload-complete')
    def upload_complete(self, request, pk=None):
        """
        Notify backend that upload is complete, trigger processing

        Request body:
        {
            "s3_key": "recordings/uuid/filename.webm"
        }

        Response:
        {
            "status": "processing started",
            "recording": {...}
        }
        """
        recording = self.get_object()

        serializer = RecordingUploadCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Update recording status
        recording.status = 'uploaded'
        recording.save()

        # Create RecordingFile entry
        RecordingFile.objects.create(
            recording=recording,
            user=request.user if request.user.is_authenticated else None,
            file_type='original_webm',
            s3_key=serializer.validated_data['s3_key'],
            s3_bucket=settings.AWS_STORAGE_BUCKET_NAME,
            file_size_bytes=recording.file_size_bytes
        )

        # Trigger processing pipeline
        from recordings.tasks import process_recording_pipeline
        process_recording_pipeline.delay(str(recording.id))

        return Response({
            'status': 'processing started',
            'recording': RecordingSerializer(recording).data
        }, status=status.HTTP_200_OK)
