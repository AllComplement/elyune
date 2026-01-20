import localforage from 'localforage';

console.log('[Offscreen] Script loading... localforage imported');

// Notify background that offscreen script loaded
(async () => {
  try {
    await browser.runtime.sendMessage({ type: 'offscreen-loaded' });
    console.log('[Offscreen] Sent loaded message to background');
  } catch (error) {
    console.error('[Offscreen] Failed to send loaded message:', error);
  }
})();

// Configure storage
localforage.config({
  driver: localforage.INDEXEDDB,
  name: 'screen-recorder',
  version: 1,
});

console.log('[Offscreen] Localforage configured');

const chunksStore = localforage.createInstance({ name: 'chunks' });

console.log('[Offscreen] Chunks store created');

interface RecordingState {
  mediaRecorder: MediaRecorder | null;
  stream: MediaStream | null;
  chunks: Blob[];
  chunkIndex: number;
  isPaused: boolean;
  quality: string;
  fps: number;
  // Audio mixing properties
  audioContext: AudioContext | null;
  micStream: MediaStream | null;
  systemAudioSource: MediaStreamAudioSourceNode | null;
  micAudioSource: MediaStreamAudioSourceNode | null;
  systemGain: GainNode | null;
  micGain: GainNode | null;
  destination: MediaStreamAudioDestinationNode | null;
  micEnabled: boolean;
  micDeviceId?: string;
}

const state: RecordingState = {
  mediaRecorder: null,
  stream: null,
  chunks: [],
  chunkIndex: 0,
  isPaused: false,
  quality: '1080p',
  fps: 30,
  // Audio mixing properties
  audioContext: null,
  micStream: null,
  systemAudioSource: null,
  micAudioSource: null,
  systemGain: null,
  micGain: null,
  destination: null,
  micEnabled: false,
};

interface DownloadState {
  downloadId: number | null;
  blobUrl: string | null;
}

const downloadState: DownloadState = {
  downloadId: null,
  blobUrl: null,
};

// Storage monitoring
let lastEstimateAt = 0;
const ESTIMATE_INTERVAL_MS = 5000;
const MIN_HEADROOM = 25 * 1024 * 1024; // 25MB minimum

// Listen for messages from background
browser.runtime.onMessage.addListener(async (message) => {
  console.log('Offscreen received message:', message.name || message.type);

  // Handle download completion from background
  if (message.type === 'download-complete') {
    console.log('[Offscreen] Download complete, cleaning up...');

    // Revoke blob URL
    if (downloadState.blobUrl) {
      URL.revokeObjectURL(downloadState.blobUrl);
      console.log('[Offscreen] Blob URL revoked');
    }

    // Clear chunks from IndexedDB
    await clearChunks();
    console.log('[Offscreen] Chunks cleared');

    // Reset download state
    downloadState.downloadId = null;
    downloadState.blobUrl = null;

    return;
  }

  // Handle download error from background
  if (message.type === 'download-error') {
    console.error('[Offscreen] Download error:', message.error);

    // Revoke blob URL even on error
    if (downloadState.blobUrl) {
      URL.revokeObjectURL(downloadState.blobUrl);
    }

    downloadState.downloadId = null;
    downloadState.blobUrl = null;

    return;
  }

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
    case 'updateMicrophoneState':
      updateMicrophoneState(message.enabled);
      break;
    case 'changeMicrophoneDevice':
      await changeMicrophoneDevice(message.deviceId);
      break;
  }
});

async function startRecording(originalTabId: number, options: any) {
  try {
    console.log('[Offscreen] startRecording called');
    state.quality = options.quality || '1080p';
    state.fps = options.fps || 30;
    state.micEnabled = options.micEnabled || false;
    state.micDeviceId = options.micDeviceId;

    const { width, height } = getResolutionForQuality(state.quality);

    console.log('[Offscreen] Resolution:', width, 'x', height, 'FPS:', state.fps);
    console.log('[Offscreen] Microphone enabled:', state.micEnabled);

    // Step 1: Get display media (screen + system audio)
    console.log('[Offscreen] Requesting getDisplayMedia...');
    const displayStream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        width: { ideal: width, max: width },
        height: { ideal: height, max: height },
        frameRate: { ideal: state.fps, max: state.fps },
      },
      audio: true,  // Capture system audio
    } as MediaStreamConstraints);

    console.log('[Offscreen] Got display stream');
    console.log('[Offscreen] Video tracks:', displayStream.getVideoTracks().length);
    console.log('[Offscreen] Audio tracks:', displayStream.getAudioTracks().length);

    // Verify stream has video
    if (displayStream.getVideoTracks().length === 0) {
      throw new Error('No video tracks available in stream');
    }

    // Step 2: Get microphone stream if enabled
    let micStream: MediaStream | null = null;
    if (state.micEnabled) {
      try {
        console.log('[Offscreen] ⚠️ REQUESTING MICROPHONE ACCESS - PERMISSION PROMPT SHOULD APPEAR NOW');

        // Build audio constraints with device ID if specified
        const audioConstraints: MediaTrackConstraints = {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        };

        if (state.micDeviceId) {
          audioConstraints.deviceId = { exact: state.micDeviceId };
          console.log('[Offscreen] Using specific device:', state.micDeviceId);
        }

        console.log('[Offscreen] Calling getUserMedia with constraints:', audioConstraints);
        micStream = await navigator.mediaDevices.getUserMedia({
          audio: audioConstraints
        });
        state.micStream = micStream;
        console.log('[Offscreen] ✅ MICROPHONE PERMISSION GRANTED! Got stream');
        console.log('[Offscreen] Mic audio tracks:', micStream.getAudioTracks().length);
      } catch (micError) {
        console.error('[Offscreen] ❌ FAILED TO GET MICROPHONE ACCESS');
        console.error('[Offscreen] Error name:', micError instanceof DOMException ? micError.name : 'Unknown');
        console.error('[Offscreen] Error message:', micError instanceof Error ? micError.message : micError);
        console.error('[Offscreen] Full error:', micError);

        // Check if it's a device-specific error
        if (micError instanceof DOMException &&
            micError.name === 'OverconstrainedError' &&
            state.micDeviceId) {
          console.warn('[Offscreen] Specific device unavailable, trying default...');

          // Retry without device constraint
          try {
            micStream = await navigator.mediaDevices.getUserMedia({
              audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
              }
            });
            state.micStream = micStream;
            state.micDeviceId = undefined;
            console.log('[Offscreen] Using default microphone');
          } catch (fallbackError) {
            console.error('[Offscreen] Fallback also failed:', fallbackError);
            // Fall through to existing error handling below
            micError = fallbackError as DOMException;
          }
        }

        // Check if user denied permission (or fallback also failed)
        if (!micStream) {
          const isMicDenied = micError instanceof DOMException && micError.name === 'NotAllowedError';

          if (isMicDenied) {
            console.log('[Offscreen] User denied microphone permission - continuing without mic');
            // Notify user but continue recording without mic
            await browser.runtime.sendMessage({
              type: 'microphone-permission-denied',
              message: 'Microphone permission denied. Recording will continue without microphone audio.'
            });
          } else {
            console.error('[Offscreen] Technical error accessing microphone:', micError);
          }

          // Continue recording without microphone
          state.micEnabled = false;
          micStream = null;
        }
      }
    }

    // Step 3: Determine if mixing is needed
    const hasSystemAudio = displayStream.getAudioTracks().length > 0;
    const hasMicAudio = micStream && micStream.getAudioTracks().length > 0;

    let finalStream: MediaStream;

    // ONLY use Web Audio API when BOTH sources are present
    if (hasSystemAudio && hasMicAudio) {
      // Case 1: Both sources - use Web Audio mixing
      console.log('[Offscreen] Setting up Web Audio API mixing for both sources...');
      console.log('[Offscreen] System audio available:', hasSystemAudio);
      console.log('[Offscreen] Mic audio available:', hasMicAudio);

      state.audioContext = new AudioContext();
      state.destination = state.audioContext.createMediaStreamDestination();

      // Setup system audio
      const systemAudioTrack = displayStream.getAudioTracks()[0];
      const systemStream = new MediaStream([systemAudioTrack]);
      state.systemAudioSource = state.audioContext.createMediaStreamSource(systemStream);
      state.systemGain = state.audioContext.createGain();
      state.systemGain.gain.value = 1;
      state.systemAudioSource.connect(state.systemGain).connect(state.destination);

      // Setup microphone audio
      state.micAudioSource = state.audioContext.createMediaStreamSource(micStream!);
      state.micGain = state.audioContext.createGain();
      state.micGain.gain.value = state.micEnabled ? 1 : 0;
      state.micAudioSource.connect(state.micGain).connect(state.destination);

      // Create final stream with video + mixed audio
      finalStream = new MediaStream();
      displayStream.getVideoTracks().forEach(track => finalStream.addTrack(track));

      const mixedAudioTrack = state.destination.stream.getAudioTracks()[0];
      if (mixedAudioTrack) {
        finalStream.addTrack(mixedAudioTrack);
      }

      console.log('[Offscreen] Both audio sources mixed with Web Audio API');

    } else if (hasSystemAudio && !hasMicAudio) {
      // Case 2: System audio only - use directly without Web Audio
      console.log('[Offscreen] Using system audio only (no mixing needed)');
      finalStream = displayStream;  // Use original stream with system audio

    } else if (!hasSystemAudio && hasMicAudio) {
      // Case 3: Mic audio only - use directly without Web Audio
      console.log('[Offscreen] Using microphone audio only (no mixing needed)');

      finalStream = new MediaStream();
      displayStream.getVideoTracks().forEach(track => finalStream.addTrack(track));
      micStream!.getAudioTracks().forEach(track => finalStream.addTrack(track));

      console.log('[Offscreen] Microphone audio added to stream');

    } else {
      // Case 4: No audio at all - video only
      console.log('[Offscreen] No audio sources available - video only');
      finalStream = displayStream;
    }

    state.stream = finalStream;

    console.log('[Offscreen] Final stream tracks:');
    console.log('[Offscreen] - Video tracks:', finalStream.getVideoTracks().length);
    console.log('[Offscreen] - Audio tracks:', finalStream.getAudioTracks().length);

    // Step 4: Create MediaRecorder with final stream
    const mimeType = getSupportedMimeType();
    const bitrates = getBitrates(state.quality);

    console.log('[Offscreen] Using MIME type:', mimeType);
    console.log('[Offscreen] Video bitrate:', bitrates.video, 'Audio bitrate:', bitrates.audio);

    console.log('[Offscreen] Creating MediaRecorder...');
    state.mediaRecorder = new MediaRecorder(finalStream, {
      mimeType,
      videoBitsPerSecond: bitrates.video,
      audioBitsPerSecond: bitrates.audio,
    });
    console.log('[Offscreen] MediaRecorder created, state:', state.mediaRecorder.state);

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
    displayStream.getVideoTracks()[0].onended = () => {
      console.log('[Offscreen] Stream ended by user');
      stopRecording();
    };

    // Start recording (capture in 1-second chunks)
    console.log('[Offscreen] Starting MediaRecorder with 1000ms timeslice...');
    try {
      state.mediaRecorder.start(1000);
      console.log('[Offscreen] MediaRecorder.start() called successfully');
      console.log('[Offscreen] MediaRecorder state after start:', state.mediaRecorder.state);
    } catch (startError) {
      console.error('[Offscreen] Error calling start():', startError);
      throw startError;
    }

    // Monitor device changes (disconnection/reconnection)
    const handleDeviceChange = async () => {
      console.log('[Offscreen] Device change detected');

      if (state.micDeviceId && state.micEnabled) {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioInputs = devices.filter(d => d.kind === 'audioinput');
        const deviceStillExists = audioInputs.some(d => d.deviceId === state.micDeviceId);

        if (!deviceStillExists) {
          console.warn('[Offscreen] Selected microphone disconnected');

          // Switch to default device
          const defaultDevice = audioInputs[0];
          if (defaultDevice) {
            console.log('[Offscreen] Switching to default:', defaultDevice.label);
            await changeMicrophoneDevice(defaultDevice.deviceId);

            await browser.runtime.sendMessage({
              type: 'microphone-device-changed',
              message: `Switched to: ${defaultDevice.label || 'Default'}`
            });
          }
        }
      }
    };

    navigator.mediaDevices.addEventListener('devicechange', handleDeviceChange);

    // Notify background
    await browser.runtime.sendMessage({
      type: 'recording-started',
      mode: 'offscreen',
      micEnabled: state.micEnabled,
    });

    console.log('[Offscreen] Recording started successfully');
  } catch (error) {
    console.error('[Offscreen] Failed to start recording:', error);

    // Cleanup on error
    cleanupAudioResources();

    // Check if user denied permission
    const isDenied = error instanceof DOMException && error.name === 'NotAllowedError';
    const errorMessage = isDenied
      ? 'Permission denied by user'
      : (error instanceof Error ? error.message : 'Unknown error');

    console.log('[Offscreen] Error type:', isDenied ? 'User cancelled' : 'Technical error');

    // Notify background of error with details
    await browser.runtime.sendMessage({
      type: 'recording-error',
      error: errorMessage,
      userCancelled: isDenied,
    });
  }
}

async function stopRecording() {
  console.log('[Offscreen] stopRecording called');
  console.log('[Offscreen] MediaRecorder state:', state.mediaRecorder?.state);

  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    console.log('[Offscreen] Stopping MediaRecorder...');
    state.mediaRecorder.stop();
  } else {
    console.log('[Offscreen] MediaRecorder already inactive or null');
  }

  // Stop all tracks
  if (state.stream) {
    console.log('[Offscreen] Stopping stream tracks...');
    state.stream.getTracks().forEach((track) => track.stop());
  }

  // Cleanup audio resources
  cleanupAudioResources();
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

function updateMicrophoneState(enabled: boolean) {
  console.log('[Offscreen] updateMicrophoneState called:', enabled);

  state.micEnabled = enabled;

  // Update mic gain in real-time if audio context exists
  if (state.micGain) {
    state.micGain.gain.value = enabled ? 1 : 0;
    console.log('[Offscreen] Mic gain updated to:', enabled ? 1 : 0);
  }
}

async function changeMicrophoneDevice(deviceId: string) {
  console.log('[Offscreen] changeMicrophoneDevice:', deviceId);

  if (!state.micEnabled || !state.audioContext) {
    console.log('[Offscreen] No active mic to switch');
    return;
  }

  try {
    // Get new microphone stream
    const newMicStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: { exact: deviceId },
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      }
    });

    console.log('[Offscreen] Got new microphone stream');

    // Disconnect old mic source
    if (state.micAudioSource) {
      state.micAudioSource.disconnect();
    }

    // Stop old mic stream
    if (state.micStream) {
      state.micStream.getTracks().forEach(track => track.stop());
    }

    // Create new mic source and connect to existing gain node
    state.micStream = newMicStream;
    state.micAudioSource = state.audioContext.createMediaStreamSource(newMicStream);
    state.micAudioSource.connect(state.micGain!).connect(state.destination!);
    state.micDeviceId = deviceId;

    console.log('[Offscreen] Microphone switched successfully');
  } catch (error) {
    console.error('[Offscreen] Failed to switch device:', error);
    await browser.runtime.sendMessage({
      type: 'microphone-device-error',
      message: 'Failed to switch microphone device'
    });
  }
}

function cleanupAudioResources() {
  console.log('[Offscreen] Cleaning up audio resources...');

  // Stop microphone stream
  if (state.micStream) {
    state.micStream.getTracks().forEach(track => track.stop());
    state.micStream = null;
    console.log('[Offscreen] Microphone stream stopped');
  }

  // Disconnect audio nodes
  if (state.systemAudioSource) {
    state.systemAudioSource.disconnect();
    state.systemAudioSource = null;
  }

  if (state.micAudioSource) {
    state.micAudioSource.disconnect();
    state.micAudioSource = null;
  }

  if (state.systemGain) {
    state.systemGain.disconnect();
    state.systemGain = null;
  }

  if (state.micGain) {
    state.micGain.disconnect();
    state.micGain = null;
  }

  if (state.destination) {
    state.destination.disconnect();
    state.destination = null;
  }

  // Close audio context
  if (state.audioContext) {
    state.audioContext.close().then(() => {
      console.log('[Offscreen] AudioContext closed');
    }).catch(err => {
      console.warn('[Offscreen] Error closing AudioContext:', err);
    });
    state.audioContext = null;
  }

  console.log('[Offscreen] Audio resources cleanup complete');
}

async function saveChunk(event: BlobEvent) {
  console.log(`[Offscreen] saveChunk called - size: ${event.data.size} bytes`);

  // Check storage before saving
  if (!(await canFitChunk(event.data.size))) {
    console.error('[Offscreen] Insufficient storage');
    await browser.runtime.sendMessage({
      type: 'recording-error',
      error: 'Insufficient storage space',
    });
    stopRecording();
    return;
  }

  try {
    const chunkKey = `chunk_${state.chunkIndex}`;
    console.log(`[Offscreen] Saving chunk ${state.chunkIndex} to IndexedDB...`);

    await chunksStore.setItem(chunkKey, {
      index: state.chunkIndex,
      chunk: event.data,
      timestamp: Date.now(),
    });

    state.chunkIndex++;
    console.log(`[Offscreen] Chunk saved successfully. Total chunks: ${state.chunkIndex}`);

    // Notify background of progress
    await browser.runtime.sendMessage({
      type: 'recording-progress',
      chunkCount: state.chunkIndex,
      size: event.data.size,
    });
  } catch (error) {
    console.error('[Offscreen] Failed to save chunk:', error);
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
  console.log('[Offscreen] handleRecordingStop called');
  console.log('[Offscreen] Chunk index:', state.chunkIndex);

  // Cleanup audio resources first
  cleanupAudioResources();

  try {
    // Collect all chunks from IndexedDB
    console.log('[Offscreen] Collecting chunks from IndexedDB...');
    const chunks: Blob[] = [];
    for (let i = 0; i < state.chunkIndex; i++) {
      const item = await chunksStore.getItem<{ chunk: Blob }>(`chunk_${i}`);
      if (item) {
        chunks.push(item.chunk);
        console.log(`[Offscreen] Chunk ${i} size:`, item.chunk.size, 'bytes');
      } else {
        console.warn(`[Offscreen] Chunk ${i} not found in storage`);
      }
    }

    console.log('[Offscreen] Total chunks collected:', chunks.length);

    if (chunks.length === 0) {
      console.error('[Offscreen] No chunks available!');
      throw new Error('No recording data available');
    }

    // Create final blob
    const mimeType = getSupportedMimeType();
    const blob = new Blob(chunks, { type: mimeType });
    console.log('[Offscreen] Blob created - size:', blob.size, 'bytes, type:', mimeType);

    // Generate filename
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const extension = mimeType.includes('webm') ? 'webm' : 'mp4';
    const filename = `screen-recording-${timestamp}.${extension}`;
    console.log('[Offscreen] Generated filename:', filename);

    // Create blob URL and send to background for download
    // (offscreen documents don't have access to chrome.downloads API)
    const url = URL.createObjectURL(blob);
    console.log('[Offscreen] Blob URL created:', url);
    downloadState.blobUrl = url;

    console.log('[Offscreen] Sending download request to background...');

    // Request background to initiate download
    await browser.runtime.sendMessage({
      type: 'download-recording',
      blobUrl: url,
      filename,
      blobSize: blob.size,
    });

    console.log('[Offscreen] Download request sent to background');
  } catch (error) {
    console.error('[Offscreen] Failed to save recording:', error);
    console.error('[Offscreen] Error stack:', error instanceof Error ? error.stack : 'No stack');

    await browser.runtime.sendMessage({
      type: 'recording-error',
      error: error instanceof Error ? error.message : 'Failed to save recording',
    });

    // Still notify background to close offscreen on error
    await browser.runtime.sendMessage({
      type: 'recording-completed',
      filename: '',
      success: false,
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
