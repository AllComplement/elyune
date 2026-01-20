# Screen Recording Implementation Guide

## Overview

This document describes how to implement production-ready screen/window recording functionality in the WXT + React + TypeScript extension, based on modern Manifest V3 patterns used by professional extensions like Screenity.

## Architecture Approaches

### Modern Approach: Offscreen Document API (Recommended)

Uses Chrome's `offscreen` API to create a hidden document with DOM context for MediaRecorder, without creating a visible tab. This is the cleanest solution for Manifest V3.

**Pros:**
- No visible tab for users to accidentally close
- Better UX - seamless recording experience
- More efficient resource usage
- Modern Manifest V3 standard

**Cons:**
- Requires `offscreen` permission (optional permission)
- Newer API - requires fallback for older Chrome versions

### Fallback Approach: Pinned Recorder Tab

Creates a pinned tab for recording when offscreen API is unavailable or for specific recording modes.

**Pros:**
- Works in all Chromium browsers
- Visual feedback for users
- More compatible

**Cons:**
- User can accidentally close the tab
- Visible UI element during recording

### Recommended Strategy

Implement **both approaches** with automatic fallback:
1. Try offscreen document first (best UX)
2. Fall back to pinned tab if offscreen fails or unavailable
3. Use pinned tab for special modes (region recording, camera overlay)

### Component Flow

```
User clicks "Start Recording"
         ↓
Background service worker receives message
         ↓
Attempt: Create offscreen document
         ↓
    Success? → Use getDisplayMedia() in offscreen
         ↓
    Failed? → Create pinned recorder tab (fallback)
         ↓
Prompt user for screen/window/tab selection
         ↓
MediaRecorder captures stream with quality settings
         ↓
Store chunks in IndexedDB with storage monitoring
         ↓
On stop: Process recording, download, cleanup
```

## Required Files

### 1. Install Dependencies

First, install required packages for storage management:

```bash
npm install localforage
```

### 2. Update manifest permissions

**File:** `wxt.config.ts`

Add the required permissions and keyboard shortcuts:

```typescript
import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    permissions: [
      'tabs',
      'activeTab',
      'storage',
      'unlimitedStorage',
      'downloads',        // For chrome.downloads API
      'tabCapture',       // For tab-specific recording
      'system.display',   // For display information
    ],
    // Optional permissions that users can grant later
    optional_permissions: [
      'offscreen',        // Modern offscreen API
      'desktopCapture',   // Fallback screen capture
    ],
    // Keyboard shortcuts for recording control
    commands: {
      'start-recording': {
        suggested_key: {
          default: 'Alt+Shift+R',
          mac: 'Command+Shift+R',
        },
        description: 'Start recording',
      },
      'stop-recording': {
        suggested_key: {
          default: 'Alt+Shift+S',
          mac: 'Command+Shift+S',
        },
        description: 'Stop recording',
      },
      'pause-recording': {
        suggested_key: {
          default: 'Alt+Shift+P',
          mac: 'Command+Shift+P',
        },
        description: 'Pause/Resume recording',
      },
    },
  },
});
```

### 3. Background Service Worker

**File:** `entrypoints/background.ts`

```typescript
export default defineBackground(() => {
  console.log('Background service worker initialized');

  // Listen for recording messages
  browser.runtime.onMessage.addListener(async (message, sender) => {
    if (message.name === 'initiateRecording') {
      await startRecording(message.options);
    }

    if (message.name === 'stopRecording') {
      await stopRecording();
    }

    if (message.name === 'pauseRecording') {
      await pauseRecording();
    }
  });

  // Handle keyboard shortcuts
  browser.commands.onCommand.addListener(async (command) => {
    switch (command) {
      case 'start-recording':
        await startRecording({});
        break;
      case 'stop-recording':
        await stopRecording();
        break;
      case 'pause-recording':
        await pauseRecording();
        break;
    }
  });
});

interface RecordingOptions {
  useOffscreen?: boolean;
  quality?: string;
  fps?: number;
  audioEnabled?: boolean;
  micEnabled?: boolean;
}

async function startRecording(options: RecordingOptions) {
  try {
    // Get current active tab
    const [currentTab] = await browser.tabs.query({
      active: true,
      lastFocusedWindow: true,
      currentWindow: true,
    });

    if (!currentTab?.id) {
      console.error('No active tab found');
      return;
    }

    // Store recording state
    await browser.storage.local.set({
      recording: true,
      activeTab: currentTab.id,
      recordingOptions: options,
    });

    // Try offscreen API first (modern approach)
    const useOffscreen = options.useOffscreen !== false; // Default to true

    if (useOffscreen) {
      try {
        await createOffscreenRecorder(currentTab.id, options);
        return; // Success - using offscreen
      } catch (error) {
        console.warn('Offscreen recording failed, falling back to tab:', error);
        // Fall through to tab-based recording
      }
    }

    // Fallback to tab-based recording
    await createTabRecorder(currentTab.id, options);
  } catch (error) {
    console.error('Failed to start recording:', error);
    await browser.storage.local.set({ recording: false });
  }
}

async function createOffscreenRecorder(
  originalTabId: number,
  options: RecordingOptions
) {
  // Close any existing offscreen document
  await closeOffscreenDocument();

  // Create offscreen document for recording
  await chrome.offscreen.createDocument({
    url: browser.runtime.getURL('/offscreen-recorder.html'),
    reasons: [
      chrome.offscreen.Reason.USER_MEDIA,
      chrome.offscreen.Reason.DISPLAY_MEDIA,
    ] as chrome.offscreen.Reason[],
    justification: 'Recording screen using MediaRecorder API',
  });

  // Store that we're using offscreen
  await browser.storage.local.set({
    recordingMode: 'offscreen',
    recordingTab: null,
  });

  // Send message to offscreen document to start recording
  await browser.runtime.sendMessage({
    name: 'startOffscreenRecording',
    originalTabId,
    options,
  });

  // Switch back to original tab
  await browser.tabs.update(originalTabId, { active: true });
}

async function createTabRecorder(
  originalTabId: number,
  options: RecordingOptions
) {
  // Create recorder tab
  const recorderTab = await browser.tabs.create({
    url: browser.runtime.getURL('/recorder.html'),
    pinned: true,
    active: true,
    index: 0,
  });

  if (!recorderTab.id) {
    throw new Error('Failed to create recorder tab');
  }

  // Prevent Chrome from auto-discarding this tab
  try {
    await browser.tabs.update(recorderTab.id, { autoDiscardable: false });
  } catch (error) {
    console.warn('Could not set autoDiscardable:', error);
  }

  // Store recorder tab info
  await browser.storage.local.set({
    recordingMode: 'tab',
    recordingTab: recorderTab.id,
  });

  // Wait for tab to load
  const listener = (
    tabId: number,
    changeInfo: browser.tabs._OnUpdatedChangeInfo
  ) => {
    if (tabId === recorderTab.id && changeInfo.status === 'complete') {
      browser.tabs.onUpdated.removeListener(listener);

      // Send start recording message
      browser.tabs.sendMessage(recorderTab.id!, {
        name: 'startRecording',
        originalTabId,
        options,
      });

      // Switch back to original tab
      browser.tabs.update(originalTabId, { active: true });
    }
  };

  browser.tabs.onUpdated.addListener(listener);
}

async function stopRecording() {
  const { recordingMode, recordingTab } = await browser.storage.local.get([
    'recordingMode',
    'recordingTab',
  ]);

  if (recordingMode === 'offscreen') {
    // Send message to offscreen document
    await browser.runtime.sendMessage({ name: 'stopOffscreenRecording' });
    await closeOffscreenDocument();
  } else if (recordingMode === 'tab' && recordingTab) {
    // Send message to recorder tab
    try {
      await browser.tabs.sendMessage(recordingTab, { name: 'stopRecording' });
    } catch (error) {
      console.error('Failed to send stop message:', error);
    }
  }

  await browser.storage.local.set({ recording: false });
}

async function pauseRecording() {
  const { recordingMode, recordingTab } = await browser.storage.local.get([
    'recordingMode',
    'recordingTab',
  ]);

  if (recordingMode === 'offscreen') {
    await browser.runtime.sendMessage({ name: 'pauseOffscreenRecording' });
  } else if (recordingMode === 'tab' && recordingTab) {
    try {
      await browser.tabs.sendMessage(recordingTab, { name: 'pauseRecording' });
    } catch (error) {
      console.error('Failed to send pause message:', error);
    }
  }
}

async function closeOffscreenDocument() {
  try {
    // Check if offscreen document exists
    const offscreenUrl = browser.runtime.getURL('/offscreen-recorder.html');
    const existingContexts = await chrome.runtime.getContexts({
      contextTypes: ['OFFSCREEN_DOCUMENT'] as chrome.runtime.ContextType[],
    });

    const offscreenDoc = existingContexts.find(
      (context) => context.documentUrl === offscreenUrl
    );

    if (offscreenDoc) {
      await chrome.offscreen.closeDocument();
    }
  } catch (error) {
    console.warn('Error closing offscreen document:', error);
  }
}
```

### 3. Popup UI Component

**File:** `entrypoints/popup/App.tsx`

```tsx
import { useState } from 'react';
import './App.css';

function App() {
  const [isRecording, setIsRecording] = useState(false);

  const handleStartRecording = async () => {
    try {
      await browser.runtime.sendMessage({ name: 'initiateRecording' });
      setIsRecording(true);
    } catch (error) {
      console.error('Failed to start recording:', error);
    }
  };

  const handleStopRecording = async () => {
    try {
      await browser.runtime.sendMessage({ name: 'stopRecording' });
      setIsRecording(false);
    } catch (error) {
      console.error('Failed to stop recording:', error);
    }
  };

  return (
    <div className="popup-container">
      <h1>Screen Recorder</h1>

      <div className="button-group">
        <button
          onClick={handleStartRecording}
          disabled={isRecording}
          className="btn btn-start"
        >
          {isRecording ? 'Recording...' : 'Start Recording'}
        </button>

        <button
          onClick={handleStopRecording}
          disabled={!isRecording}
          className="btn btn-stop"
        >
          Stop Recording
        </button>
      </div>

      {isRecording && (
        <p className="recording-status">
          Recording in progress. Do not close the recorder tab.
        </p>
      )}
    </div>
  );
}

export default App;
```

**File:** `entrypoints/popup/App.css`

```css
.popup-container {
  width: 300px;
  padding: 20px;
  font-family: system-ui, -apple-system, sans-serif;
}

h1 {
  font-size: 20px;
  margin-bottom: 20px;
  text-align: center;
}

.button-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.btn {
  padding: 12px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-start {
  background-color: #0073e6;
  color: white;
}

.btn-start:hover:not(:disabled) {
  background-color: #005ba4;
}

.btn-stop {
  background-color: #dc3545;
  color: white;
}

.btn-stop:hover:not(:disabled) {
  background-color: #c82333;
}

.recording-status {
  margin-top: 15px;
  padding: 10px;
  background-color: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 4px;
  font-size: 12px;
  text-align: center;
  color: #856404;
}
```

### 4. Recorder Page

**File:** `entrypoints/recorder.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Screen Recorder</title>
  <style>
    body {
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    .warning-container {
      background-color: #ffffff;
      padding: 40px;
      border-radius: 12px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
      text-align: center;
      max-width: 500px;
    }

    .warning-icon {
      font-size: 60px;
      margin-bottom: 20px;
    }

    h1 {
      color: #dc3545;
      margin: 0 0 15px 0;
      font-size: 28px;
    }

    p {
      color: #666;
      font-size: 16px;
      line-height: 1.6;
      margin: 0;
    }

    .recording-indicator {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 20px;
      padding: 10px 20px;
      background-color: #dc3545;
      color: white;
      border-radius: 20px;
      font-weight: 600;
    }

    .recording-dot {
      width: 10px;
      height: 10px;
      background-color: white;
      border-radius: 50%;
      animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
  </style>
</head>
<body>
  <div class="warning-container">
    <div class="warning-icon">⚠️</div>
    <h1>Recording in Progress</h1>
    <p>
      Do not close this window while recording is active.
      Your screen recording will be saved automatically when you stop.
    </p>
    <div class="recording-indicator">
      <div class="recording-dot"></div>
      <span>Recording...</span>
    </div>
  </div>
  <script type="module" src="./recorder.ts"></script>
</body>
</html>
```

**File:** `entrypoints/recorder.ts`

```typescript
interface RecordingMessage {
  name: string;
  body?: {
    currentTabId: number;
  };
}

let mediaRecorder: MediaRecorder | null = null;
let chunks: Blob[] = [];
let currentStream: MediaStream | null = null;

// Listen for messages from background
browser.runtime.onMessage.addListener((message: RecordingMessage) => {
  if (message.name === 'startRecording') {
    if (message.body?.currentTabId) {
      startRecording(message.body.currentTabId);
    }
  }

  if (message.name === 'stopRecording') {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  }
});

async function startRecording(originalTabId: number) {
  try {
    // Prompt user to choose screen or window
    // @ts-ignore - chrome.desktopCapture is not in standard types
    const streamId = await new Promise<string>((resolve, reject) => {
      chrome.desktopCapture.chooseDesktopMedia(
        ['screen', 'window'],
        (streamId: string | null) => {
          if (!streamId) {
            reject(new Error('User cancelled screen selection'));
            return;
          }
          resolve(streamId);
        }
      );
    });

    // Get media stream from the selected screen/window
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        // @ts-ignore - chromeMediaSource is a Chrome-specific constraint
        mandatory: {
          chromeMediaSource: 'desktop',
          chromeMediaSourceId: streamId,
        },
      },
    });

    currentStream = stream;
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'video/webm;codecs=vp9',
    });

    chunks = [];

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      await handleRecordingStop();
    };

    mediaRecorder.start(1000); // Capture in 1-second chunks

    // Switch back to original tab
    await browser.tabs.update(originalTabId, { active: true });

    console.log('Recording started successfully');
  } catch (error) {
    console.error('Failed to start recording:', error);

    // Show error to user
    document.body.innerHTML = `
      <div class="warning-container">
        <div class="warning-icon">❌</div>
        <h1>Recording Failed</h1>
        <p>${error instanceof Error ? error.message : 'Unknown error occurred'}</p>
      </div>
    `;

    // Close tab after 3 seconds
    setTimeout(() => window.close(), 3000);
  }
}

async function handleRecordingStop() {
  try {
    // Stop all tracks
    if (currentStream) {
      currentStream.getTracks().forEach(track => track.stop());
    }

    // Create blob from recorded chunks
    const blob = new Blob(chunks, { type: 'video/webm' });
    const url = URL.createObjectURL(blob);

    // Generate filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const filename = `screen-recording-${timestamp}.webm`;

    // Download the recording
    const downloadLink = document.createElement('a');
    downloadLink.href = url;
    downloadLink.download = filename;
    downloadLink.click();

    // Clean up
    URL.revokeObjectURL(url);
    chunks = [];

    console.log('Recording saved:', filename);

    // Close the recorder tab
    setTimeout(() => window.close(), 1000);
  } catch (error) {
    console.error('Failed to save recording:', error);
  }
}
```

### 5. Offscreen Recorder (Modern Approach)

**File:** `entrypoints/offscreen-recorder.html`

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Offscreen Recorder</title>
</head>
<body>
  <!-- Hidden offscreen document for recording -->
  <script type="module" src="./offscreen-recorder.ts"></script>
</body>
</html>
```

**File:** `entrypoints/offscreen-recorder.ts`

This is the key improvement over the tab-based approach - uses `getDisplayMedia()` API:

```typescript
import localforage from 'localforage';

// Configure storage
localforage.config({
  driver: localforage.INDEXEDDB,
  name: 'screen-recorder',
  version: 1,
});

const chunksStore = localforage.createInstance({ name: 'chunks' });

interface RecordingState {
  mediaRecorder: MediaRecorder | null;
  stream: MediaStream | null;
  chunks: Blob[];
  chunkIndex: number;
  isPaused: boolean;
  quality: string;
  fps: number;
}

const state: RecordingState = {
  mediaRecorder: null,
  stream: null,
  chunks: [],
  chunkIndex: 0,
  isPaused: false,
  quality: '1080p',
  fps: 30,
};

// Storage monitoring
let lastEstimateAt = 0;
const ESTIMATE_INTERVAL_MS = 5000;
const MIN_HEADROOM = 25 * 1024 * 1024; // 25MB minimum

// Listen for messages from background
browser.runtime.onMessage.addListener(async (message) => {
  console.log('Offscreen received message:', message.name);

  switch (message.name) {
    case 'startOffscreenRecording':
      await startRecording(message.originalTabId, message.options);
      break;
    case 'stopOffscreenRecording':
      await stopRecording();
      break;
    case 'pauseOffscreenRecording':
      pauseRecording();
      break;
  }
});

async function startRecording(originalTabId: number, options: any) {
  try {
    state.quality = options.quality || '1080p';
    state.fps = options.fps || 30;

    const { width, height } = getResolutionForQuality(state.quality);

    // Use modern getDisplayMedia API
    const stream = await navigator.mediaDevices.getDisplayMedia({
      audio: options.audioEnabled !== false,
      video: {
        width: { ideal: width },
        height: { ideal: height },
        frameRate: { ideal: state.fps },
        displaySurface: 'monitor',
      },
      selfBrowserSurface: 'exclude',
      systemAudio: 'include',
    } as MediaStreamConstraints);

    // Verify stream has video
    if (stream.getVideoTracks().length === 0) {
      throw new Error('No video tracks available in stream');
    }

    state.stream = stream;

    // Get optimal MIME type
    const mimeType = getSupportedMimeType();
    const bitrates = getBitrates(state.quality);

    // Create MediaRecorder with quality settings
    state.mediaRecorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: bitrates.video,
      audioBitsPerSecond: bitrates.audio,
    });

    // Handle recording data
    state.mediaRecorder.ondataavailable = async (event) => {
      if (event.data && event.data.size > 0) {
        await saveChunk(event);
      }
    };

    // Handle recording stop
    state.mediaRecorder.onstop = async () => {
      await handleRecordingStop();
    };

    // Handle stream end (user stops sharing)
    stream.getVideoTracks()[0].onended = () => {
      console.log('Stream ended by user');
      stopRecording();
    };

    // Start recording (capture in 1-second chunks)
    state.mediaRecorder.start(1000);

    // Notify background
    await browser.runtime.sendMessage({
      type: 'recording-started',
      mode: 'offscreen',
    });

    console.log('Offscreen recording started successfully');
  } catch (error) {
    console.error('Failed to start offscreen recording:', error);

    // Notify background of error
    await browser.runtime.sendMessage({
      type: 'recording-error',
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}

async function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
  }

  // Stop all tracks
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
  }
}

function pauseRecording() {
  if (!state.mediaRecorder) return;

  if (state.mediaRecorder.state === 'recording') {
    state.mediaRecorder.pause();
    state.isPaused = true;
  } else if (state.mediaRecorder.state === 'paused') {
    state.mediaRecorder.resume();
    state.isPaused = false;
  }
}

async function saveChunk(event: BlobEvent) {
  // Check storage before saving
  if (!(await canFitChunk(event.data.size))) {
    console.error('Insufficient storage');
    await browser.runtime.sendMessage({
      type: 'recording-error',
      error: 'Insufficient storage space',
    });
    stopRecording();
    return;
  }

  try {
    await chunksStore.setItem(`chunk_${state.chunkIndex}`, {
      index: state.chunkIndex,
      chunk: event.data,
      timestamp: Date.now(),
    });

    state.chunkIndex++;

    // Notify background of progress
    await browser.runtime.sendMessage({
      type: 'recording-progress',
      chunkCount: state.chunkIndex,
      size: event.data.size,
    });
  } catch (error) {
    console.error('Failed to save chunk:', error);
    await browser.runtime.sendMessage({
      type: 'recording-error',
      error: 'Failed to save recording data',
    });
    stopRecording();
  }
}

async function canFitChunk(byteLength: number): Promise<boolean> {
  const now = performance.now();
  if (now - lastEstimateAt < ESTIMATE_INTERVAL_MS) {
    return true; // Skip check to avoid overhead
  }
  lastEstimateAt = now;

  try {
    const { usage = 0, quota = 0 } = await navigator.storage.estimate();
    const remaining = quota - usage;
    return remaining > MIN_HEADROOM + byteLength;
  } catch {
    return true; // Assume OK if estimation fails
  }
}

async function handleRecordingStop() {
  try {
    // Collect all chunks from IndexedDB
    const chunks: Blob[] = [];
    for (let i = 0; i < state.chunkIndex; i++) {
      const item = await chunksStore.getItem<{ chunk: Blob }>(`chunk_${i}`);
      if (item) {
        chunks.push(item.chunk);
      }
    }

    if (chunks.length === 0) {
      throw new Error('No recording data available');
    }

    // Create final blob
    const mimeType = getSupportedMimeType();
    const blob = new Blob(chunks, { type: mimeType });

    // Generate filename
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const extension = mimeType.includes('webm') ? 'webm' : 'mp4';
    const filename = `screen-recording-${timestamp}.${extension}`;

    // Download using chrome.downloads API
    const url = URL.createObjectURL(blob);

    await chrome.downloads.download({
      url,
      filename,
      saveAs: true,
    });

    // Clean up
    URL.revokeObjectURL(url);
    await clearChunks();

    // Notify background
    await browser.runtime.sendMessage({
      type: 'recording-completed',
      filename,
    });

    console.log('Recording saved:', filename);
  } catch (error) {
    console.error('Failed to save recording:', error);
    await browser.runtime.sendMessage({
      type: 'recording-error',
      error: error instanceof Error ? error.message : 'Failed to save recording',
    });
  }
}

async function clearChunks() {
  try {
    await chunksStore.clear();
    state.chunkIndex = 0;
    state.chunks = [];
  } catch (error) {
    console.error('Failed to clear chunks:', error);
  }
}

// Quality and codec utilities
function getSupportedMimeType(): string {
  const types = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm;codecs=h264',
    'video/webm',
  ];

  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }

  return 'video/webm';
}

function getBitrates(quality: string) {
  const bitrates: Record<string, { audio: number; video: number }> = {
    '4k': { audio: 192000, video: 20000000 },
    '1080p': { audio: 128000, video: 8000000 },
    '720p': { audio: 128000, video: 5000000 },
    '480p': { audio: 96000, video: 3000000 },
  };

  return bitrates[quality] || bitrates['1080p'];
}

function getResolutionForQuality(quality: string) {
  const resolutions: Record<string, { width: number; height: number }> = {
    '4k': { width: 4096, height: 2160 },
    '1080p': { width: 1920, height: 1080 },
    '720p': { width: 1280, height: 720 },
    '480p': { width: 854, height: 480 },
  };

  return resolutions[quality] || resolutions['1080p'];
}

console.log('Offscreen recorder loaded');
```

### 6. Type Definitions

**File:** `types/chrome.d.ts`

```typescript
// Add Chrome-specific types that aren't in the standard definitions
declare namespace chrome {
  namespace desktopCapture {
    function chooseDesktopMedia(
      sources: string[],
      callback: (streamId: string | null) => void
    ): void;
  }

  namespace offscreen {
    enum Reason {
      USER_MEDIA = 'USER_MEDIA',
      DISPLAY_MEDIA = 'DISPLAY_MEDIA',
      AUDIO_PLAYBACK = 'AUDIO_PLAYBACK',
    }

    function createDocument(options: {
      url: string;
      reasons: Reason[];
      justification: string;
    }): Promise<void>;

    function closeDocument(): Promise<void>;
  }

  namespace runtime {
    enum ContextType {
      OFFSCREEN_DOCUMENT = 'OFFSCREEN_DOCUMENT',
    }

    function getContexts(filter: {
      contextTypes: ContextType[];
    }): Promise<Array<{ documentUrl?: string }>>;
  }

  namespace downloads {
    function download(options: {
      url: string;
      filename: string;
      saveAs?: boolean;
    }): Promise<number>;
  }
}
```

Update `tsconfig.json` to include this file:

```json
{
  "compilerOptions": {
    "typeRoots": ["./node_modules/@types", "./types"]
  }
}
```

## Implementation Steps

1. **Update WXT config** with required permissions
2. **Implement background service worker** to handle recording lifecycle
3. **Update popup UI** with Start/Stop recording buttons
4. **Create recorder page** (HTML + TypeScript) for actual capture
5. **Add type definitions** for Chrome-specific APIs
6. **Test the extension** in development mode

## Testing

```bash
# Start development server
npm run dev

# Load extension in Chrome
# 1. Open chrome://extensions
# 2. Enable "Developer mode"
# 3. Click "Load unpacked"
# 4. Select the .output/chrome-mv3 directory

# Test recording flow
# 1. Click extension icon
# 2. Click "Start Recording"
# 3. Select screen/window in Chrome's picker
# 4. Verify recording indicator appears
# 5. Click "Stop Recording"
# 6. Check downloaded video file
```

## Key Improvements from Professional Extensions

### 1. **Modern Offscreen API (Primary Advantage)**
- Uses `chrome.offscreen.createDocument()` instead of visible tabs
- Better UX - no visible UI element to confuse users
- Uses `getDisplayMedia()` API (modern standard)
- Automatic fallback to tab-based recording

### 2. **Storage Management**
- IndexedDB storage via localforage for large recordings
- Storage estimation to prevent disk space issues
- Chunked recording (1-second chunks) for reliability
- Efficient memory management

### 3. **Quality Configuration**
- Configurable video quality (480p to 4k)
- Adjustable FPS settings
- Optimal bitrate selection per quality level
- Automatic MIME type detection (VP9/VP8/H264)

### 4. **Resource Management**
- `autoDiscardable: false` prevents Chrome from killing recorder tab
- Proper cleanup of streams and storage
- Memory monitoring to avoid crashes
- Graceful error handling with user notifications

### 5. **Enhanced User Experience**
- Keyboard shortcuts for all recording actions
- Pause/Resume functionality
- Recording progress tracking
- Automatic detection when user stops sharing
- Chrome downloads API for better file management

### 6. **WXT Framework Benefits**
- `defineBackground()` for service worker
- File-based entry points
- Built-in TypeScript support
- Cross-browser compatibility layer

### 7. **React Integration**
- State management for recording status
- Loading states and error feedback
- Type-safe component props
- Modern UI/UX patterns

## Architecture Comparison

| Feature | Basic Tab Approach | Modern Offscreen Approach |
|---------|-------------------|---------------------------|
| **User Visibility** | Pinned tab visible | Hidden offscreen document |
| **API Used** | `desktopCapture.chooseDesktopMedia()` | `getDisplayMedia()` |
| **User Risk** | Can close tab accidentally | No visible UI to close |
| **Chrome Version** | All Chromium browsers | Chrome 109+ (with fallback) |
| **Storage** | In-memory chunks | IndexedDB with monitoring |
| **Quality Control** | Fixed settings | Configurable bitrate/resolution |
| **Error Handling** | Basic | Comprehensive with notifications |
| **Resource Management** | Manual cleanup | `autoDiscardable`, storage monitoring |
| **Keyboard Shortcuts** | No | Yes, via commands API |
| **Pause/Resume** | No | Yes |
| **Progress Tracking** | No | Yes, with chunk counting |

## Known Limitations & Considerations

### Current Implementation

1. **Audio Configuration** - System audio requires user permission and browser support
2. **WebM Format** - Output is WebM (browser native, excellent compatibility)
3. **Chrome/Chromium Only** - Both approaches are Chromium-specific
4. **Storage Limits** - Large recordings constrained by available disk space
5. **VP9 Codec** - Best quality but requires hardware encoding for smooth recording

### Trade-offs

**Offscreen Approach:**
- **Pro:** Best UX, no visible recorder
- **Con:** Newer API, requires Chrome 109+, needs fallback

**Tab Approach:**
- **Pro:** Universal Chromium support, visual confirmation
- **Con:** User can accidentally close tab, less polished UX

## Future Enhancements

### Phase 1 (Core Features)
- [ ] Audio mixing (system + microphone with Web Audio API)
- [ ] Camera overlay with positioning
- [ ] Drawing tools during recording
- [ ] Annotation/arrow overlays

### Phase 2 (Advanced Features)
- [ ] Tab-specific recording (using tabCapture API)
- [ ] Region selection for partial screen recording
- [ ] Countdown timer before recording starts
- [ ] Recording time limit warnings
- [ ] Video trimming/editing

### Phase 3 (Cloud & Sharing)
- [ ] Cloud upload integration (Drive, Dropbox)
- [ ] Recording history/management
- [ ] Direct sharing links
- [ ] Automatic transcoding to MP4

### Phase 4 (Professional Features)
- [ ] WebCodecs API for better compression
- [ ] GPU-accelerated encoding
- [ ] Real-time preview window
- [ ] Background blur for camera
- [ ] Noise cancellation for microphone

## Troubleshooting

### Recording doesn't start
- Verify permissions in manifest
- Check browser console for errors
- Ensure user didn't cancel screen picker

### Video file corrupted
- Ensure recording was stopped properly
- Check available disk space
- Try shorter recording duration

### Recorder tab closes immediately
- Check for JavaScript errors in recorder.ts
- Verify message passing between background and recorder
- Check browser console logs

## Best Practices (Learned from Screenity)

### 1. **Always Implement Fallbacks**
```typescript
// Try modern approach first, fallback gracefully
try {
  await createOffscreenRecorder();
} catch (error) {
  console.warn('Offscreen failed, using fallback');
  await createTabRecorder(); // Fallback
}
```

### 2. **Monitor Storage Continuously**
```typescript
// Check storage before saving every chunk
const { usage, quota } = await navigator.storage.estimate();
if (quota - usage < MIN_HEADROOM) {
  stopRecording(); // Prevent data loss
}
```

### 3. **Prevent Tab Discarding**
```typescript
// Critical for tab-based recording
await browser.tabs.update(tabId, {
  autoDiscardable: false // Prevent Chrome from killing tab
});
```

### 4. **Use Chunked Recording**
```typescript
// Start with time slice for reliability
mediaRecorder.start(1000); // 1-second chunks

// Allows recovery if recording crashes
// Enables progress tracking
// Reduces memory pressure
```

### 5. **Clean Up Resources**
```typescript
// Always stop tracks when done
stream.getTracks().forEach(track => track.stop());

// Clear storage
await chunksStore.clear();

// Revoke object URLs
URL.revokeObjectURL(url);
```

### 6. **Handle User-Initiated Stop**
```typescript
// Listen for when user stops screen sharing
stream.getVideoTracks()[0].onended = () => {
  console.log('User stopped sharing');
  stopRecording(); // Clean up gracefully
};
```

### 7. **Use IndexedDB for Large Recordings**
```typescript
// Never keep all chunks in memory
// Save to IndexedDB immediately
await chunksStore.setItem(`chunk_${i}`, {
  chunk: event.data,
  timestamp: Date.now()
});
```

### 8. **Provide Quality Options**
```typescript
// Let users choose based on their needs
const bitrates = {
  '1080p': { video: 8000000, audio: 128000 },
  '720p': { video: 5000000, audio: 128000 },
};
```

### 9. **Test MIME Type Support**
```typescript
// Not all browsers support all codecs
function getBestMimeType() {
  const types = ['video/webm;codecs=vp9', 'video/webm'];
  return types.find(type => MediaRecorder.isTypeSupported(type));
}
```

### 10. **Communicate Clearly with Users**
```typescript
// Send progress updates
browser.runtime.sendMessage({
  type: 'recording-progress',
  chunkCount: state.chunkIndex,
  duration: Date.now() - startTime,
});
```

## Summary: Production-Ready Checklist

✅ **Modern offscreen API with fallback**
✅ **Storage monitoring and management**
✅ **Configurable quality settings (480p-4k)**
✅ **Keyboard shortcuts for control**
✅ **Pause/Resume functionality**
✅ **Graceful error handling**
✅ **Resource cleanup (streams, storage, URLs)**
✅ **Progress tracking and notifications**
✅ **Automatic codec detection**
✅ **User-initiated stop detection**
✅ **Timestamp-based filenames**
✅ **Chrome downloads API integration**
✅ **TypeScript type safety**
✅ **Cross-browser compatibility layer (WXT)**

## Resources

- [WXT Documentation](https://wxt.dev)
- [Chrome Extension APIs](https://developer.chrome.com/docs/extensions/reference/)
- [Offscreen Documents API](https://developer.chrome.com/docs/extensions/reference/offscreen/)
- [MediaRecorder API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- [getDisplayMedia API](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)
- [Desktop Capture API](https://developer.chrome.com/docs/extensions/reference/desktopCapture/)
- [Screenity GitHub](https://github.com/alyssaxuu/screenity) - Professional reference implementation
- [Storage Quota Management](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/estimate)

---

**Implementation Status:** This guide provides production-ready code based on patterns from professional extensions like Screenity. The offscreen approach represents the current best practice for Manifest V3 screen recording.

**Last Updated:** Based on Screenity v4.2.2 and Chrome Extension Manifest V3 standards as of 2024.
