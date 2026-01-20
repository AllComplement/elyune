# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Elyune is a screen recording platform with AI-powered transcription and analysis. It consists of a Chrome extension for capturing screen recordings and a Django backend for processing videos, transcribing audio, and generating AI insights.

## Repository Structure

```
elyune/
├── elyune-extension/     # WXT-based browser extension (TypeScript + React)
└── elyune-backend/       # Django REST API with Celery processing pipeline
```

## Common Commands

### Backend (elyune-backend/)

```bash
# Start all services (Django, PostgreSQL, Redis, Celery, MinIO, Flower)
docker-compose up -d

# Start with watch mode for hot-reload development
docker compose watch  # Note: requires 'docker compose' (v2), not 'docker-compose'

# View logs
docker-compose logs -f
docker-compose logs -f web           # Django
docker-compose logs -f celery_worker # Task processing

# Run Django management commands
docker-compose exec web python3 manage.py migrate
docker-compose exec web python3 manage.py makemigrations
docker-compose exec web python3 manage.py createsuperuser
docker-compose exec web python3 manage.py shell

# Access database
docker-compose exec web python3 manage.py dbshell
docker-compose exec db psql -U elyune_user -d elyune_db

# Rebuild after dependency changes
docker-compose build web
docker-compose up -d

# Clean rebuild (removes volumes - deletes data)
docker-compose down -v
docker-compose up --build

# Monitor Celery tasks
# Open http://localhost:5555 (Flower UI)

# Access MinIO console
# Open http://localhost:9001 (login: minioadmin/minioadmin)
```

### Extension (elyune-extension/)

```bash
# Development
npm run dev              # Chrome with hot reload
npm run dev:firefox      # Firefox with hot reload

# Build for production
npm run build            # Chrome
npm run build:firefox    # Firefox

# Distribution
npm run zip              # Create Chrome distribution zip
npm run zip:firefox      # Create Firefox distribution zip

# Type checking
npm run compile          # Run TypeScript without emitting

# Testing (after building)
npm run test             # Run Playwright tests
npm run test:ui          # Run Playwright tests with UI
```

## Architecture

### Data Flow

```
Chrome Extension (WXT + React)
    ↓ [WebM upload]
MinIO Object Storage (S3-compatible)
    ↓ [Processing trigger]
Celery Task Pipeline:
  1. convert_webm_to_mp4 (FFmpeg)
  2. extract_audio_from_video (FFmpeg → WAV)
  3. transcribe_audio (Deepgram API)
  4. analyze_transcription (Gemini API)
    ↓ [Results stored]
PostgreSQL Database
    ↓ [API access]
Django REST Framework API (JWT auth)
```

### Backend Architecture

**Django Apps:**
- `recordings/` - File upload management, presigned URL generation, recording metadata
- `processing/` - Celery task orchestration, FFmpeg processing, ProcessingJob/ProcessingStep models
- `analysis/` - Transcription and AI analysis results storage

**Key Technologies:**
- Django 6.0.1 + DRF 3.16.1
- PostgreSQL 16 for relational data
- MinIO for S3-compatible object storage
- Celery 5.4.0 with Redis broker for async processing
- FFmpeg for video/audio conversion
- Deepgram SDK for transcription with speaker diarization
- Google Gemini API for AI analysis (summary, action items, key points, sentiment)
- JWT authentication (djangorestframework-simplejwt)

**Celery Task Chain:**
```python
process_recording_pipeline()
    → convert_webm_to_mp4()
    → extract_audio_from_video()
    → transcribe_audio()
    → analyze_transcription()
```

Each task:
- Updates ProcessingStep status (running/completed/failed)
- Downloads from MinIO → processes locally → uploads back to MinIO
- Has retry logic (2-3 attempts with exponential backoff)
- Timeout: 1800 seconds (30 minutes)

### Extension Architecture

**Entry Points (WXT file-based):**
- `background.ts` - Service worker orchestrating recording lifecycle, message routing
- `offscreen-recorder/` - Modern hidden recording (Chrome 109+) using offscreen document API
- `recorder/` - Fallback pinned tab recorder for older Chrome versions
- `popup/` - React UI for recording controls and status display
- `content.ts` - Optional content script (requires `matches` array for injection)

**Recording Strategy:**
1. Try offscreen document API (Chrome 109+) for invisible background recording
2. Fallback to pinned tab recorder if offscreen unavailable
3. MediaRecorder captures with quality presets (480p-4K)
4. Chunks stored in IndexedDB (offscreen) or memory (tab mode)
5. Storage monitoring (checks quota every 5s, maintains 25MB headroom)
6. Download via chrome.downloads API from background worker

**State Management:**
- `chrome.storage.local` for recording state persistence
- `localforage` wrapper for IndexedDB chunk storage in offscreen mode

## API Endpoints

```
POST   /api/token/                                   # Get JWT token
POST   /api/token/refresh/                           # Refresh JWT token
POST   /api/v1/recordings/request-upload/            # Get presigned MinIO URL
POST   /api/v1/recordings/{id}/upload-complete/      # Trigger processing pipeline
GET    /api/v1/recordings/                           # List user recordings
GET    /api/v1/recordings/{id}/                      # Get recording details + analysis
PATCH  /api/v1/recordings/{id}/                      # Update recording metadata
DELETE /api/v1/recordings/{id}/                      # Delete recording + files
```

## Environment Setup

### Backend (.env)

Required environment variables:
```bash
# External APIs
DEEPGRAM_API_KEY=your_deepgram_key    # Transcription service
GEMINI_API_KEY=your_gemini_key        # AI analysis

# Django
SECRET_KEY=your_secret_key
JWT_SECRET_KEY=your_jwt_key
DEBUG=True

# Database
POSTGRES_DB=elyune_db
POSTGRES_USER=elyune_user
POSTGRES_PASSWORD=secure_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

# MinIO (S3-compatible storage)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=media
AWS_S3_ENDPOINT_URL=http://minio:9000

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Processing
MAX_UPLOAD_SIZE_MB=2048
FFMPEG_PATH=/usr/bin/ffmpeg
```

**Initial Setup:**
1. Copy `.env.example` to `.env`
2. Add API keys for Deepgram and Gemini
3. Generate JWT secret: `python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
4. Start services: `docker-compose up -d`
5. Create bucket in MinIO console (http://localhost:9001) named "media"

## Development Patterns

### Backend Development

**Watch mode for hot-reload:**
The backend has Docker Compose watch support configured for efficient development:
```bash
docker compose watch
```
This enables:
- **Web service:** Auto-syncs Python files, Django auto-reloads changes
- **Celery worker:** Auto-syncs and restarts on Python file changes
- **Both:** Auto-rebuild when requirements.txt changes

The watch ignores `.venv/`, `__pycache__/`, `.git/`, and config files for performance.

**Adding new Celery task:**
- Define task in `processing/tasks.py` with `@shared_task` decorator
- Update task chain in `process_recording_pipeline()` if sequential
- Create ProcessingStep for tracking
- Add S3 upload/download logic using `get_s3_client()`

**Adding new API endpoint:**
- Define serializer in `{app}/serializers.py`
- Add view in `{app}/views.py` (use DRF viewsets)
- Register route in `{app}/urls.py`
- All endpoints require JWT authentication by default

**Database changes:**
```bash
docker-compose exec web python3 manage.py makemigrations
docker-compose exec web python3 manage.py migrate
```

### Extension Development

**WXT entry points:**
- Use `defineBackground()` for background.ts
- Use `defineContentScript({ matches: [...] })` for content scripts
- React components use standard setup (no special WXT wrapper)
- `browser` API is globally available

**Adding keyboard shortcuts:**
- Update `manifest.commands` in `wxt.config.ts`
- Handle in `background.ts` with `chrome.commands.onCommand.addListener()`

**Debugging:**
- Background worker: chrome://extensions → "service worker" link
- Popup: Right-click extension icon → "Inspect popup"
- Storage: DevTools → Application → IndexedDB → check "chunks" store

## Testing

### Backend Testing
```bash
# Run all tests
docker-compose exec web python3 manage.py test

# Run specific app tests
docker-compose exec web python3 manage.py test recordings

# Run with coverage
docker-compose exec web coverage run --source='.' manage.py test
docker-compose exec web coverage report
```

### Extension Testing
```bash
# Build first (required)
npm run build

# Run Playwright tests
npm run test
npm run test:ui  # Interactive mode
```

## Monitoring & Debugging

**Backend Services:**
- Django Admin: http://localhost:8000/admin/
- Celery Flower: http://localhost:5555 (task monitoring)
- MinIO Console: http://localhost:9001 (storage browser)

**Troubleshooting:**
```bash
# Check service health
docker-compose ps

# View processing job status
docker-compose exec web python3 manage.py shell
>>> from processing.models import ProcessingJob
>>> job = ProcessingJob.objects.last()
>>> job.status, job.error_message

# Check Celery task queue
docker-compose exec redis redis-cli
> LLEN celery

# Restart failed services
docker-compose restart celery_worker
docker-compose restart web
```

## Important Notes

- **Celery worker concurrency:** 2 workers (configurable in docker-compose.yml)
- **FFmpeg timeout:** 30 minutes per conversion task
- **JWT token expiry:** 1 hour (refresh token: 7 days)
- **Presigned URL expiry:** 1 hour
- **Task retry logic:** 2-3 attempts with exponential backoff
- **Recording quality defaults:** 1080p @ 30 FPS, 8 Mbps bitrate
- **Storage monitoring:** Extension checks quota every 5 seconds during recording
- **Chrome version requirement:** Offscreen API requires Chrome 109+, fallback works on Chrome 100+
- **Docker volume mounts:** The `- .:/app` volume mount is commented out in docker-compose.yml to prevent overwriting the container's virtual environment. Use `docker compose watch` for hot-reload instead.

## File Organization Conventions

**Backend:**
- Models define database schema (one model per logical entity)
- Serializers handle API request/response transformation
- Views use DRF ViewSets for REST operations
- Celery tasks in `processing/tasks.py` handle all async operations
- S3 operations centralized with `get_s3_client()`, `download_from_s3()`, `upload_to_s3()`

**Extension:**
- Entry points are file-based (background.ts, popup/, etc.)
- Message passing between contexts via `browser.runtime.sendMessage()`
- State persistence via `chrome.storage.local`
- Recording chunks stored in IndexedDB using localforage wrapper
- Cleanup logic centralizes resource management (streams, URLs, storage)
