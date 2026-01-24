# Elyune Developer Guide for Agents

This document provides essential instructions for AI agents working on the Elyune project.

## Project Structure

- `elyune-backend/`: Django REST API with Celery processing pipeline (Dockerized).
- `elyune-extension/`: Chrome extension built with WXT and React.

---

## 🏗️ Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ELYUNE SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │ Chrome Extension │                                                   │
│  │  (WXT + React)   │                                                   │
│  └────────┬─────────┘                                                   │
│           │ WebM upload via presigned URL                               │
│           ▼                                                             │
│  ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
│  │      MinIO       │───►│  Celery Worker  │───►│   PostgreSQL    │    │
│  │  (S3 Storage)    │    │   (Pipeline)    │    │   (Database)    │    │
│  └──────────────────┘    └────────┬────────┘    └────────┬────────┘    │
│                                   │                      │              │
│                          ┌────────┴────────┐             │              │
│                          │  External APIs  │             ▼              │
│                          │  - Deepgram     │    ┌─────────────────┐    │
│                          │  - Gemini       │    │  Django REST    │    │
│                          └─────────────────┘    │  API (JWT Auth) │    │
│                                                 └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Recording**: User records screen via extension → chunks stored in IndexedDB
2. **Upload**: Extension requests presigned URL → uploads WebM to MinIO
3. **Processing**: Backend triggers Celery pipeline:
   - `convert_webm_to_mp4` (FFmpeg)
   - `extract_audio_from_video` (FFmpeg → WAV)
   - `transcribe_audio` (Deepgram API)
   - `analyze_transcription` (Gemini API)
4. **Results**: Transcription + AI analysis stored in PostgreSQL, accessible via API

### Key Services (Docker)

| Service | Port | Purpose |
|---------|------|---------|
| `web` | 8000 | Django REST API |
| `db` | 5432 | PostgreSQL 16 |
| `redis` | 6379 | Celery message broker |
| `minio` | 9000/9001 | S3-compatible storage |
| `celery_worker` | - | Background task processor |
| `flower` | 5555 | Celery monitoring UI |

---

## 🐍 Backend (elyune-backend)

### Commands

**Working Directory:** `/home/extremo/allcomplement/elyune/elyune-backend`

- **Start Services:** `docker compose up -d`
- **Hot Reload Dev:** `docker compose watch`
- **Run Tests (All):** `docker compose exec web python3 manage.py test`
- **Run Single Test:** `docker compose exec web python3 manage.py test path.to.test_module.TestClass.test_method`
  - Example: `docker compose exec web python3 manage.py test processing.tests.ProcessingTaskTests.test_video_conversion`
- **Linting:** No strict linter enforced in CI, but adhere to **PEP 8**.
- **Migrations:** `docker compose exec web python3 manage.py makemigrations`
- **Apply Migrations:** `docker compose exec web python3 manage.py migrate`
- **Shell:** `docker compose exec web python3 manage.py shell`
- **View Logs:** `docker compose logs -f web` (or `celery_worker`, `flower`, etc.)
- **Database Shell:** `docker compose exec db psql -U elyune_user -d elyune_db`

### Django Apps

| App | Purpose | Key Files |
|-----|---------|-----------|
| `accounts/` | User auth & registration | `views.py`, `serializers.py` |
| `recordings/` | Recording metadata, presigned URLs | `models.py`, `views.py` |
| `processing/` | Celery tasks, job tracking | `tasks.py`, `models.py` |
| `analysis/` | Transcription & AI results | `models.py` |
| `config/` | Settings, URLs, Celery config | `settings.py`, `celery.py` |

### Key Models

**recordings.Recording:**
- UUID primary key
- User foreign key (ownership)
- Status: `uploading` → `uploaded` → `processing` → `completed` / `failed`
- Quality, FPS, duration, audio flags

**processing.ProcessingJob:**
- One-to-one with Recording
- Tracks overall pipeline status and progress
- Links to Celery task ID

**processing.ProcessingStep:**
- Steps: `video_conversion`, `audio_extraction`, `speech_to_text`, `ai_analysis`
- Individual status, timing, error tracking

**analysis.Transcription:**
- Full text, confidence score, speaker count
- Related `TranscriptionSegment` for speaker diarization

**analysis.AIAnalysis:**
- Types: `summary`, `action_items`, `key_points`, `sentiment`
- Structured JSON in `result_data`, human-readable in `result_text`

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/token/` | Get JWT token (login) |
| POST | `/api/token/refresh/` | Refresh JWT token |
| POST | `/api/v1/recordings/request-upload/` | Get presigned MinIO URL |
| POST | `/api/v1/recordings/{id}/upload-complete/` | Trigger processing pipeline |
| GET | `/api/v1/recordings/` | List user's recordings |
| GET | `/api/v1/recordings/{id}/` | Get recording with analysis |
| PATCH | `/api/v1/recordings/{id}/` | Update recording metadata |
| DELETE | `/api/v1/recordings/{id}/` | Delete recording + files |

### Celery Task Patterns

When creating new Celery tasks:

```python
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3)
def my_task(self, recording_id):
    try:
        # 1. Get recording and create/update ProcessingStep
        recording = Recording.objects.get(id=recording_id)
        step = ProcessingStep.objects.create(
            job=recording.processing_job,
            step_name='my_step',
            status='running',
            started_at=timezone.now()
        )
        
        # 2. Download from S3 if needed
        download_from_s3(s3_key, local_path)
        
        # 3. Process
        # ...
        
        # 4. Upload results to S3
        upload_to_s3(local_path, new_s3_key)
        
        # 5. Update step status
        step.status = 'completed'
        step.completed_at = timezone.now()
        step.save()
        
        return recording_id  # Pass to next task in chain
        
    except Exception as exc:
        logger.error(f"Task failed for {recording_id}: {exc}")
        if step:
            step.status = 'failed'
            step.error_message = str(exc)
            step.save()
        raise self.retry(exc=exc, countdown=60)
```

### Parallel AI Analysis Pattern

**Overview:**  
The AI analysis step (`analyze_transcription`) runs 4 independent analyses in parallel using Celery's `chord` primitive: summary, action items, key points, and sentiment analysis. This provides a **~50% performance improvement** over sequential execution.

**Architecture:**
```python
from celery import chord

# Main orchestrator task
@shared_task(bind=True, max_retries=2)
def analyze_transcription(self, recording_id):
    # Prepare data
    formatted_transcript = format_transcript_with_speakers(transcription)
    model_name = 'gemini-2.5-flash'  # with fallback to gemini-2.0-flash
    
    # Launch 4 parallel tasks with callback
    callback = finalize_parallel_analysis.s(str(recording_id))
    parallel_workflow = chord([
        generate_and_save_summary.s(recording_id, transcript, model),
        generate_and_save_action_items.s(recording_id, transcript, model),
        generate_and_save_key_points.s(recording_id, transcript, model),
        generate_and_save_sentiment.s(recording_id, transcript, model),
    ])(callback)
    
    return recording_id

# Finalization callback
@shared_task(bind=True, max_retries=1)
def finalize_parallel_analysis(self, results, recording_id):
    # Aggregate results from all 4 tasks
    # Handle partial failures (mark completed with warning if 1-3 fail)
    # Update ProcessingStep and Recording status
```

**Performance Metrics (Measured):**
- **Sequential (old):** ~20-25 seconds
- **Parallel (new):** ~14 seconds (50% faster)
- Individual task times: Summary (5.5s), Action Items (7s), Key Points (7.2s), Sentiment (14s)
- Total time limited by slowest task (sentiment analysis)

**Key Features:**
1. **Idempotent Sub-Tasks**: Each analysis uses `update_or_create()` for safe retries
2. **Rate Limit Handling**: Exponential backoff for Gemini API 429 errors
3. **Partial Failure Tolerance**: System completes if 1-3 analyses succeed
4. **Independent Gemini Instances**: Each sub-task initializes its own `GenerativeModel`

**Gemini API Considerations:**
- Model version: `gemini-2.5-flash` (primary) with fallback to `gemini-2.0-flash`
- Model availability is tested before launching parallel tasks
- Each sub-task handles rate limiting independently with `sleep()` + retry

**Error Handling Patterns:**
```python
# In sub-tasks
try:
    result = generate_summary(model, transcript)
    AIAnalysis.objects.update_or_create(...)
    return {'type': 'summary', 'status': 'success', 'time': result['time']}
except Exception as exc:
    # Check for rate limiting
    if '429' in str(exc).lower() or 'rate limit' in str(exc).lower():
        wait_time = min((2 ** self.request.retries) + random.uniform(0, 1), 60)
        sleep(wait_time)
        raise self.retry(exc=exc, countdown=int(wait_time))
    # Return failure status
    return {'type': 'summary', 'status': 'failed', 'error': str(exc)[:200]}
```

**Testing:**
- Unit tests for each sub-task in `processing/tests.py`
- Test idempotency, rate limiting, and partial failures
- Mock `google.generativeai` to avoid actual API calls

### S3/MinIO Helpers

```python
from processing.tasks import get_s3_client, download_from_s3, upload_to_s3

# Get client
s3_client = get_s3_client()

# Download file
download_from_s3('recordings/uuid/file.webm', '/tmp/local.webm')

# Upload file
upload_to_s3('/tmp/output.mp4', 'recordings/uuid/converted.mp4')
```

### Code Style & Conventions

- **Formatting:**
  - Indentation: **4 spaces**.
  - Quotes: Single quotes `'` preferred for strings, double quotes `"` for docstrings.
  - Max Line Length: ~88-100 characters (soft limit).

- **Imports:**
  - Order: Standard library -> Third-party -> Local Django apps.
  - Use relative imports for internal app references (e.g., `from .models import ProcessingJob`).

- **Naming:**
  - Variables/Functions: `snake_case` (e.g., `process_recording`, `user_id`).
  - Classes: `CapWords` (e.g., `RecordingSerializer`).
  - Constants: `UPPER_CASE` (e.g., `MAX_RETRIES`).

- **Type Hinting:**
  - Use Python type hints where helpful for clarity, especially in utility functions and services.
  - Example: `def calculate_duration(start: datetime, end: datetime) -> float:`

- **Error Handling:**
  - Use specific exceptions where possible.
  - Catch `Exception` only when acting as a top-level handler (e.g., in Celery tasks) and log the error.
  - Pattern:
    ```python
    try:
        # code
    except SpecificError as e:
        logger.error(f"Context: {e}")
        raise
    ```

- **Logging:**
  - Use `logger = logging.getLogger(__name__)` or `get_task_logger(__name__)` for Celery.
  - Do not use `print()` in production code.

---

## 🧩 Extension (elyune-extension)

### Commands

**Working Directory:** `/home/extremo/allcomplement/elyune/elyune-extension`

- **Development:** `npm run dev` (Chrome with hot reload)
- **Development Firefox:** `npm run dev:firefox`
- **Build:** `npm run build`
- **Build Firefox:** `npm run build:firefox`
- **Type Check:** `npm run compile` (Runs `tsc --noEmit`)
- **Run Tests (All):** `npm run test` (Playwright, requires build first)
- **Run Single Test:** `npx playwright test tests/specific.spec.ts`
- **Create Distribution:** `npm run zip`

### Entry Points (WXT File-Based)

| Entry Point | Purpose |
|-------------|---------|
| `entrypoints/background.ts` | Service worker - orchestrates recording, message routing |
| `entrypoints/offscreen-recorder/` | Modern invisible recording (Chrome 109+) |
| `entrypoints/recorder/` | Fallback pinned tab recorder (older Chrome) |
| `entrypoints/popup/` | React UI for controls, auth, settings |
| `entrypoints/content.ts` | Content script (optional, needs `matches` config) |

### Popup Components

| Component | Purpose |
|-----------|---------|
| `LoginScreen.tsx` | JWT authentication form |
| `SignupScreen.tsx` | User registration |
| `RecordingScreen.tsx` | Start/stop recording, mic toggle |
| `SettingsScreen.tsx` | Configuration options |

### Message Flow

**Starting a Recording:**
```
Popup                    Background                 Offscreen
  │                          │                          │
  │ {name: 'initiateRecording', options} ───────────►  │
  │                          │                          │
  │                          │ createDocument()         │
  │                          │ ─────────────────────►   │
  │                          │                          │
  │                          │ {name: 'startOffscreenRecording'} ─►│
  │                          │                          │
  │                          │ ◄─ {type: 'recording-started'}      │
  │                          │                          │
```

**Stopping & Uploading:**
```
Popup                    Background                 Offscreen
  │                          │                          │
  │ {name: 'stopRecording'} ────────────────────────►  │
  │                          │                          │
  │                          │ {name: 'stopOffscreenRecording'} ──►│
  │                          │                          │
  │                          │ ◄── {type: 'download-recording', blobUrl}
  │                          │                          │
  │                          │ chrome.downloads.download()
  │                          │                          │
  │                          │ {type: 'upload-recording'} ────────►│
  │                          │                          │
  │                          │ ◄── {type: 'upload-complete'}       │
```

### Recording State Management

```typescript
// Storage keys used
interface StorageState {
  recording: boolean;           // Is recording active?
  recordingMode: 'offscreen';   // Recording mode
  microphoneEnabled: boolean;   // Mic toggle state
  selectedMicrophoneDeviceId: string; // Selected mic
}

// Read state
const { recording } = await browser.storage.local.get('recording');

// Update state
await browser.storage.local.set({ recording: true });

// Listen for changes
browser.storage.onChanged.addListener((changes) => {
  if (changes.recording) {
    console.log('Recording state:', changes.recording.newValue);
  }
});
```

### Offscreen Recorder Key Functions

| Function | Purpose |
|----------|---------|
| `startRecording(options)` | Initialize MediaRecorder with display/mic streams |
| `stopRecording()` | Stop recorder, trigger blob assembly |
| `handleRecordingStop()` | Assemble chunks, create download |
| `handleUpload(filename, auth)` | Upload to backend via presigned URL |
| `saveChunk(chunk)` | Store chunk in IndexedDB |
| `clearChunks()` | Clean up IndexedDB after download |

### Code Style & Conventions

- **Frameworks:** WXT (Web Extension Tools), React 19, TypeScript.

- **Formatting:**
  - Indentation: **2 spaces**.
  - Quotes: Single quotes `'` preferred.
  - Semicolons: Always use semicolons.

- **Naming:**
  - Files: `kebab-case.ts` or `PascalCase.tsx` for components.
  - Variables/Functions: `camelCase` (e.g., `startRecording`, `isRecording`).
  - Components: `PascalCase` (e.g., `RecordingStatus`).
  - Interfaces/Types: `PascalCase` (e.g., `RecordingOptions`).

- **TypeScript:**
  - **Strict:** Yes. Avoid `any` whenever possible.
  - Define interfaces for props and message payloads.

- **Messaging (Background <-> Content/Popup):**
  - Use `browser.runtime.sendMessage` and `browser.runtime.onMessage`.
  - Message format should include a `type` or `name` property.
  - Example: `{ type: 'recording-started', payload: { ... } }`

- **Logging:**
  - Use `console.log` / `console.error`.
  - Prefix logs with context for clarity: `console.log('[Background] Message received:', msg);`

### Adding New Message Types

1. Define the message interface:
```typescript
interface MyMessage {
  type: 'my-new-message';
  data: string;
}
```

2. Handle in background.ts:
```typescript
if (message.type === 'my-new-message') {
  console.log('[Background] Received:', message.data);
  // Handle message
  return;
}
```

3. Send from popup/content:
```typescript
await browser.runtime.sendMessage({
  type: 'my-new-message',
  data: 'hello'
});
```

---

## 🔑 Environment Variables

### Backend Required (.env)

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
JWT_SECRET_KEY=your-jwt-secret

# Database
POSTGRES_DB=elyune_db
POSTGRES_USER=elyune_user
POSTGRES_PASSWORD=secure_password

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=media

# External APIs (required for full pipeline)
DEEPGRAM_API_KEY=your-deepgram-key
GEMINI_API_KEY=your-gemini-key
```

### Extension

The extension reads backend URL from storage (configurable in Settings).
Default: `http://localhost:8000`

---

## 🐛 Debugging Tips

### Backend

```bash
# Check service health
docker compose ps

# View specific service logs
docker compose logs -f celery_worker

# Check processing job status
docker compose exec web python3 manage.py shell
>>> from processing.models import ProcessingJob
>>> job = ProcessingJob.objects.last()
>>> print(job.status, job.error_message)

# Check Celery queue length
docker compose exec redis redis-cli LLEN celery

# Restart a service
docker compose restart celery_worker
```

### Extension

- **Background Worker:** `chrome://extensions` → Click "service worker" link
- **Popup DevTools:** Right-click extension icon → "Inspect popup"
- **Storage Inspection:** DevTools → Application → IndexedDB → `chunksStore`
- **Check Recording State:**
```javascript
// In background console
chrome.storage.local.get(null, console.log);
```

---

## 🤖 General Agent Guidelines

1. **Safety First:** Never commit secrets (API keys, credentials) to git.

2. **Context:** Always read the file you are modifying first.

3. **Verification:**
   - **Backend:** Run related tests after changes. If no tests exist, create a basic test case.
   - **Extension:** Ensure `npm run compile` passes after TypeScript changes.

4. **Docker:** The backend runs in Docker. Do not try to run `python manage.py` directly on the host machine; use `docker compose exec web ...`.

5. **Recording Flow:** When modifying recording logic:
   - Changes to capture → `offscreen-recorder/index.ts`
   - Changes to orchestration → `background.ts`
   - Changes to UI → `popup/components/RecordingScreen.tsx`

6. **Processing Pipeline:** When modifying processing:
   - New tasks go in `processing/tasks.py`
   - Update task chain in `process_recording_pipeline()` if sequential
   - Create corresponding `ProcessingStep` for tracking

7. **API Changes:**
   - Add serializer in `{app}/serializers.py`
   - Add view in `{app}/views.py`
   - Register route in `{app}/urls.py`
   - All endpoints require JWT auth by default

8. **Database Changes:**
   - Modify model in `{app}/models.py`
   - Run: `docker compose exec web python3 manage.py makemigrations`
   - Run: `docker compose exec web python3 manage.py migrate`

9. **Testing Changes:**
   - Backend: `docker compose exec web python3 manage.py test {app}`
   - Extension: `npm run build && npm run test`
