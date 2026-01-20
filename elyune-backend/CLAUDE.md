# Elyune Backend - Recording Processing System

## Overview

Backend system for processing Chrome extension screen recordings with automated transcription and AI analysis pipeline.

## Architecture

### System Flow
1. **Upload**: Extension uploads WebM recordings to MinIO via presigned URLs
2. **Processing**: Celery pipeline converts WebM→MP4, extracts audio
3. **Transcription**: Deepgram API for speech-to-text with speaker diarization
4. **Analysis**: Gemini API generates summary, action items, key points, and sentiment analysis

### Technology Stack
- **Framework**: Django 6.0.1 + Django REST Framework
- **Database**: PostgreSQL 16
- **Storage**: MinIO (S3-compatible)
- **Task Queue**: Celery 5.4.0 + Redis 7
- **Processing**: FFmpeg for video/audio conversion
- **APIs**: Deepgram (transcription), Google Gemini (AI analysis)
- **Auth**: JWT (djangorestframework-simplejwt)

## Django Apps

### 1. `recordings`
Manages file uploads, storage, and metadata
- Presigned URL generation for direct S3 uploads
- Recording metadata tracking
- Multi-format file storage (WebM, MP4, audio)

### 2. `processing`
Async processing pipeline with Celery
- ProcessingJob orchestration
- ProcessingStep tracking
- FFmpeg video/audio processing
- Retry logic with exponential backoff

### 3. `analysis`
AI analysis results storage
- Transcription with speaker diarization
- TranscriptionSegment with timestamps
- AIAnalysis (4 types: summary, action items, key points, sentiment)

## API Endpoints

### Authentication
```
POST /api/token/              # Get JWT token (login)
POST /api/token/refresh/      # Refresh JWT token
```

### Recordings
```
POST   /api/v1/recordings/request-upload/     # Request presigned URL
POST   /api/v1/recordings/{id}/upload-complete/  # Notify upload complete
GET    /api/v1/recordings/                    # List user recordings
GET    /api/v1/recordings/{id}/               # Get recording details
PATCH  /api/v1/recordings/{id}/               # Update recording
DELETE /api/v1/recordings/{id}/               # Delete recording
```

## Environment Variables

Required in `.env`:
```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
POSTGRES_DB=elyune_db
POSTGRES_USER=elyune_user
POSTGRES_PASSWORD=secure_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

# MinIO (S3-compatible)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=media
AWS_S3_ENDPOINT_URL=http://minio:9000

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# External APIs
DEEPGRAM_API_KEY=your_deepgram_api_key
GEMINI_API_KEY=your_gemini_api_key

# JWT
JWT_SECRET_KEY=your_jwt_secret_key

# Processing
MAX_UPLOAD_SIZE_MB=2048
FFMPEG_PATH=/usr/bin/ffmpeg
```

## Docker Services

### Services
- **web**: Django application (port 8000)
- **db**: PostgreSQL database (port 5432)
- **redis**: Message broker for Celery (port 6379)
- **celery_worker**: Async task worker
- **flower**: Celery monitoring UI (port 5555)
- **minio**: S3-compatible object storage (ports 9000-9001)

### Starting Services
```bash
# Build and start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Setup Instructions

### 1. Environment Setup
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
# DEEPGRAM_API_KEY, GEMINI_API_KEY, JWT_SECRET_KEY
```

### 2. Build and Start
```bash
# Build Docker images (requires 4-6GB memory allocated to Docker)
docker-compose build

# Start all services
docker-compose up -d
```

### 3. Database Setup
```bash
# Run migrations
docker-compose exec web python3 manage.py migrate

# Create superuser
docker-compose exec web python3 manage.py createsuperuser
```

### 4. MinIO Bucket Setup
```bash
# Access MinIO console: http://localhost:9001
# Login: minioadmin / minioadmin
# Create bucket named "media"
```

## Processing Pipeline

### Celery Task Chain
```python
convert_webm_to_mp4
    ↓
extract_audio_from_video
    ↓
transcribe_audio (Deepgram)
    ↓
analyze_transcription (Gemini)
```

### Task Details

**1. convert_webm_to_mp4**
- Downloads WebM from MinIO
- Converts to MP4 using FFmpeg (libx264, AAC audio)
- Uploads MP4 back to MinIO

**2. extract_audio_from_video**
- Extracts audio as WAV (16kHz mono)
- Optimized for speech recognition
- Uploads to MinIO

**3. transcribe_audio**
- Sends audio to Deepgram API
- Features: speaker diarization, smart formatting, punctuation
- Stores full transcription + segments with timestamps

**4. analyze_transcription**
- Sends transcription to Gemini API
- Generates 4 analysis types:
  - Summary (concise overview)
  - Action Items (tasks with timestamps)
  - Key Points (main topics)
  - Sentiment Analysis (tone/emotion)

## Monitoring

### Celery Tasks (Flower)
```
http://localhost:5555
```
- View active tasks
- Monitor task success/failure
- Inspect task arguments and results

### Django Admin
```
http://localhost:8000/admin/
```
- Manage users
- View recordings, processing jobs, analyses
- Debug processing status

### MinIO Console
```
http://localhost:9001
```
- Browse uploaded files
- Check storage usage
- Manage buckets and access policies

## Development

### Running Migrations
```bash
# Create migrations
docker-compose exec web python3 manage.py makemigrations

# Apply migrations
docker-compose exec web python3 manage.py migrate
```

### Accessing Django Shell
```bash
docker-compose exec web python3 manage.py shell
```

### Viewing Celery Logs
```bash
docker-compose logs -f celery_worker
```

### Database Shell
```bash
docker-compose exec web python3 manage.py dbshell
```

## Testing Upload Flow

### 1. Get JWT Token
```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

### 2. Request Upload URL
```bash
curl -X POST http://localhost:8000/api/v1/recordings/request-upload/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test-recording.webm",
    "file_size": 10485760,
    "quality": "1080p",
    "fps": 30,
    "has_system_audio": true,
    "has_microphone": false
  }'
```

### 3. Upload File to Presigned URL
```bash
curl -X PUT "PRESIGNED_URL_FROM_RESPONSE" \
  -H "Content-Type: video/webm" \
  --data-binary @test-recording.webm
```

### 4. Notify Upload Complete
```bash
curl -X POST http://localhost:8000/api/v1/recordings/RECORDING_ID/upload-complete/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"s3_key": "S3_KEY_FROM_RESPONSE"}'
```

### 5. Monitor Processing
- Check Flower UI: http://localhost:5555
- Check recording status via API
- View logs: `docker-compose logs -f celery_worker`

## File Structure

```
elyune-backend/
├── config/                 # Django project settings
│   ├── settings.py        # Main configuration
│   ├── urls.py            # URL routing
│   ├── celery.py          # Celery configuration
│   └── wsgi.py            # WSGI entry point
├── recordings/            # Recordings app
│   ├── models.py          # Recording, RecordingFile models
│   ├── views.py           # API endpoints
│   ├── serializers.py     # DRF serializers
│   └── urls.py            # App URL routing
├── processing/            # Processing app
│   ├── models.py          # ProcessingJob, ProcessingStep
│   └── tasks.py           # Celery tasks (400+ lines)
├── analysis/              # Analysis app
│   └── models.py          # Transcription, AIAnalysis models
├── docker-compose.yml     # Multi-service orchestration
├── Dockerfile             # Production image build
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
└── CLAUDE.md             # This file
```

## Troubleshooting

### Services Won't Start
```bash
# Check logs for specific service
docker-compose logs web
docker-compose logs celery_worker

# Rebuild images
docker-compose build --no-cache

# Verify Docker memory allocation (need 4-6GB)
```

### Celery Tasks Not Running
```bash
# Check Redis connection
docker-compose exec redis redis-cli ping

# Check Celery worker logs
docker-compose logs -f celery_worker

# Restart Celery worker
docker-compose restart celery_worker
```

### Upload Fails
```bash
# Check MinIO is running
docker-compose ps minio

# Verify bucket exists in MinIO console
# http://localhost:9001

# Check presigned URL expiration (1 hour default)
```

### Processing Fails
```bash
# Check FFmpeg installation
docker-compose exec web ffmpeg -version

# Check API keys in .env
docker-compose exec web env | grep API_KEY

# View processing job errors
docker-compose exec web python3 manage.py shell
>>> from processing.models import ProcessingJob
>>> job = ProcessingJob.objects.last()
>>> print(job.error_message)
```

## Security Notes

- JWT tokens expire after 1 hour (configurable)
- Refresh tokens valid for 7 days
- Users can only access their own recordings
- Presigned URLs expire after 1 hour
- All API endpoints require authentication except /api/token/

## Performance Considerations

- Celery worker concurrency: 2 (configurable in docker-compose.yml)
- FFmpeg timeout: 1800 seconds (30 minutes)
- Task retry logic: 3 attempts with exponential backoff
- PostgreSQL connection pooling enabled
- Redis persistence enabled via volume mount

## Future Enhancements

- [ ] Add webhook notifications for processing completion
- [ ] Implement processing status polling endpoint
- [ ] Add support for multiple languages in Deepgram
- [ ] Implement video thumbnail generation
- [ ] Add storage cleanup for old recordings
- [ ] Implement rate limiting for API endpoints
- [ ] Add WebSocket support for real-time progress updates
