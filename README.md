# Elyune

Screen recording and analysis platform with AI-powered transcription, automatic summarization, and intelligent insights.

[![CI Status](https://github.com/AllComplement/elyune/actions/workflows/ci.yml/badge.svg)](https://github.com/AllComplement/elyune/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/AllComplement/elyune)](https://github.com/AllComplement/elyune/releases)

## Overview

Elyune combines a browser extension for screen recording with a backend processing pipeline that automatically transcribes audio, generates summaries, extracts action items, and provides sentiment analysis using advanced AI models.

## 🚀 Try the Extension

### Quick Install (No Setup Required)

**Want to try Elyune without setting up the backend?** Download and install the extension to test screen recording:

1. **Download the latest release:**
   - Go to [Releases](https://github.com/AllComplement/elyune/releases/latest)
   - Download `elyune-chrome-v1.0.0.zip` (for Chrome/Edge/Brave)
   - Download `elyune-firefox-v1.0.0.zip` (for Firefox)

2. **Install in Chrome/Edge/Brave:**
   - Extract the zip file to a folder on your computer
   - Open `chrome://extensions` (or `edge://extensions`)
   - Enable **"Developer mode"** (toggle in top-right corner)
   - Click **"Load unpacked"**
   - Select the extracted folder
   - The Elyune icon will appear in your browser toolbar

3. **Install in Firefox:**
   - Open `about:debugging#/runtime/this-firefox`
   - Click **"Load Temporary Add-on"**
   - Select the downloaded `.zip` file (no need to extract)
   - The Elyune icon will appear in your browser toolbar

4. **Start Recording:**
   - Click the Elyune icon in your toolbar
   - Click **"Start Recording"**
   - Select a screen, window, or tab to record
   - Click **"Stop Recording"** when done
   - Your recording will be saved as a `.webm` file

**Note:** For full functionality including AI transcription and analysis, you'll need to set up the backend (see Full Setup below).

### What You Can Do

**With Extension Only:**
- ✅ Record your screen, windows, or tabs
- ✅ Adjust quality settings (480p - 4K)
- ✅ Use keyboard shortcuts (`Alt+Shift+R` to start/stop)
- ✅ Save recordings locally as `.webm` files
- ✅ Monitor storage usage

**With Full Setup (Extension + Backend):**
- ✅ All of the above, plus:
- ✅ Automatic upload to secure cloud storage
- ✅ AI-powered transcription with speaker detection
- ✅ Automatic summary generation
- ✅ Action items extraction with timestamps
- ✅ Key points identification
- ✅ Sentiment analysis
- ✅ Access recordings from any device

## Architecture

The project consists of two main components:

### 🎬 Browser Extension (`elyune-extension/`)
Production-ready Chrome extension for screen recording with dual-mode recording support.

**Key Features:**
- Modern offscreen document API with automatic fallback
- Smart storage management with IndexedDB
- Configurable quality (480p - 4K)
- Keyboard shortcuts for control
- Resource cleanup and error handling

**Tech Stack:** WXT, React, TypeScript, localforage

[→ Extension Documentation](./elyune-extension/README.md)

### ⚙️ Backend API (`elyune-backend/`)
Django REST Framework backend with automated processing pipeline for recordings.

**Key Features:**
- S3-compatible object storage (MinIO)
- Async processing with Celery task queue
- FFmpeg video/audio conversion
- Deepgram transcription with speaker diarization
- Google Gemini AI analysis (summary, action items, key points, sentiment)

**Tech Stack:** Django 6.0, PostgreSQL 16, Celery, Redis, FFmpeg, MinIO

[→ Backend Documentation](./elyune-backend/README.md)

## Quick Start

### Full Setup (Extension + Backend)

Want the complete experience with AI analysis? Follow these steps:

### Prerequisites
- Node.js 18+ (for extension development)
- Docker Desktop (for backend services)
- Docker Compose v2.0+

### 1. Backend Setup

```bash
# Navigate to backend
cd elyune-backend

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys:
# - DEEPGRAM_API_KEY (for transcription)
# - GEMINI_API_KEY (for AI analysis)
# - JWT_SECRET_KEY (generate with Django)

# Start all services (PostgreSQL, Redis, MinIO, Celery, Django)
docker-compose up -d

# Run migrations
docker-compose exec web python3 manage.py migrate

# Create admin user
docker-compose exec web python3 manage.py createsuperuser

# Access MinIO console at http://localhost:9001
# Login: minioadmin/minioadmin
# Create a bucket named "media"
```

**Backend Services:**
- API: http://localhost:8000
- Admin: http://localhost:8000/admin/
- MinIO Console: http://localhost:9001
- Celery Monitor (Flower): http://localhost:5555

### 2. Extension Setup

```bash
# Navigate to extension
cd elyune-extension

# Install dependencies
npm install

# Start development server
npm run dev

# Load in Chrome:
# 1. Open chrome://extensions
# 2. Enable "Developer mode"
# 3. Click "Load unpacked"
# 4. Select .output/chrome-mv3 directory
```

## System Flow

```
User records screen in browser
         ↓
Extension uploads WebM to MinIO via presigned URL
         ↓
Backend processing pipeline (Celery tasks):
  1. Convert WebM → MP4 (FFmpeg)
  2. Extract audio → WAV (FFmpeg)
  3. Transcribe audio → Text (Deepgram)
  4. Analyze transcription → Insights (Gemini)
         ↓
Results available via API:
  - Full transcription with timestamps
  - Speaker diarization
  - Summary and key points
  - Action items with timestamps
  - Sentiment analysis
```

## API Endpoints

### Authentication
```
POST /api/token/              # Login
POST /api/token/refresh/      # Refresh token
```

### Recordings
```
POST   /api/v1/recordings/request-upload/        # Get presigned URL
POST   /api/v1/recordings/{id}/upload-complete/  # Start processing
GET    /api/v1/recordings/                       # List recordings
GET    /api/v1/recordings/{id}/                  # Get recording details
DELETE /api/v1/recordings/{id}/                  # Delete recording
```

## Development

### Backend Development
```bash
cd elyune-backend

# View logs
docker-compose logs -f

# Run Django commands
docker-compose exec web python3 manage.py [command]

# Access database
docker-compose exec db psql -U elyune_user -d elyune_db

# Monitor Celery tasks
# Open http://localhost:5555
```

### Extension Development
```bash
cd elyune-extension

# Chrome development
npm run dev

# Firefox development
npm run dev:firefox

# Build for production
npm run build

# Create distribution package
npm run zip
```

## Project Structure

```
elyune/
├── elyune-backend/           # Django REST API
│   ├── config/              # Project settings
│   ├── recordings/          # Upload management
│   ├── processing/          # Celery tasks
│   ├── analysis/            # AI results storage
│   ├── docker-compose.yml   # Service orchestration
│   └── requirements.txt     # Python dependencies
│
├── elyune-extension/        # Browser extension
│   ├── entrypoints/
│   │   ├── background.ts   # Service worker
│   │   ├── popup/          # React UI
│   │   ├── offscreen-recorder/  # Modern recording
│   │   └── recorder/       # Fallback recording
│   ├── wxt.config.ts       # Extension manifest
│   └── package.json        # npm dependencies
│
└── README.md               # This file
```

## Environment Variables

### Backend Required
```bash
# API Keys
DEEPGRAM_API_KEY=your_deepgram_api_key
GEMINI_API_KEY=your_gemini_api_key
JWT_SECRET_KEY=your_jwt_secret_key

# Django
SECRET_KEY=your_django_secret_key
DEBUG=True

# Database
POSTGRES_DB=elyune_db
POSTGRES_USER=elyune_user
POSTGRES_PASSWORD=secure_password

# MinIO
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=media

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
```

See [elyune-backend/.env.example](./elyune-backend/.env.example) for complete configuration.

## Monitoring

### Backend Health
- **API Status:** GET http://localhost:8000/admin/
- **Celery Tasks:** http://localhost:5555 (Flower UI)
- **MinIO Storage:** http://localhost:9001 (Console)
- **Database:** `docker-compose exec db psql -U elyune_user -d elyune_db`

### Extension Debug
- **Background Worker:** chrome://extensions → "service worker"
- **Popup:** Right-click icon → "Inspect popup"
- **Storage:** DevTools → Application → IndexedDB

## Processing Pipeline Details

### Video Processing
1. **WebM Upload:** Extension uploads to MinIO via presigned URL
2. **MP4 Conversion:** FFmpeg converts with H.264 codec
3. **Audio Extraction:** Extract 16kHz mono WAV for transcription

### AI Analysis
1. **Transcription:** Deepgram with speaker diarization
2. **Summary:** Gemini generates concise overview
3. **Action Items:** Extract tasks with timestamps
4. **Key Points:** Identify main topics
5. **Sentiment:** Analyze tone and emotion

### Task Queue
- **Retry Logic:** 3 attempts with exponential backoff
- **Timeout:** 30 minutes per task
- **Concurrency:** 2 workers (configurable)

## Browser Compatibility

### Extension
- ✅ Chrome 109+ (offscreen recording)
- ✅ Chrome 100-108 (tab fallback)
- ✅ Chromium-based (Edge, Brave, Opera)
- 🔜 Firefox (planned)

### Backend
- ✅ Any modern browser (REST API)
- ✅ Mobile compatible

## Security

- JWT authentication with 1-hour token expiry
- Presigned URLs for secure uploads (1-hour expiry)
- Users can only access their own recordings
- All API endpoints require authentication
- CORS configured for frontend integration

## Troubleshooting

### Backend Issues
```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f [service]

# Restart services
docker-compose restart

# Clean rebuild
docker-compose down -v
docker-compose up --build
```

### Extension Issues
- **Recording fails:** Check storage permissions and available space
- **Upload fails:** Verify backend is running and API credentials
- **Quality issues:** Adjust quality settings in popup
- **Shortcuts not working:** Check Chrome shortcuts settings

## Performance

### Backend
- FFmpeg timeout: 30 minutes
- Max upload size: 2GB (configurable)
- Celery worker concurrency: 2
- Task retry: 3 attempts
- PostgreSQL connection pooling enabled

### Extension
- Storage monitoring: Every 5 seconds
- Minimum free space: 25MB
- Chunk interval: 1 second
- Default quality: 1080p @ 30 FPS

## License

See [LICENSE](./elyune-backend/LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## Support

For issues and questions:
- Extension issues: [GitHub Issues](https://github.com/AllComplement/elyune/issues)
- Backend issues: [GitHub Issues](https://github.com/AllComplement/elyune/issues)

---

**Built with ❤️ using Django REST Framework, React, and WXT**
