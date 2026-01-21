import { getAuthState, getBackendUrl } from './popup/services/storage';

export default defineBackground(() => {
  console.log('Background service worker initialized');

  // Listen for recording messages
  browser.runtime.onMessage.addListener(async (message, sender) => {
    console.log('[Background] Received message:', message.name || message.type);

    if (message.type === 'offscreen-loaded') {
      console.log('[Background] ✅ Offscreen document loaded successfully!');
      return;
    }

    if (message.type === 'recording-error') {
      console.error('[Background] ❌ Recording error from offscreen:', message.error);

      // Update storage to reflect recording stopped
      await browser.storage.local.set({ recording: false });

      // Close offscreen document
      console.log('[Background] Closing offscreen document due to error...');
      await closeOffscreenDocument();

      // Log user-friendly message
      if (message.userCancelled) {
        console.log('[Background] 📝 User cancelled screen selection - this is normal');
      } else {
        console.error('[Background] 📝 Technical error occurred during recording setup');
      }

      return;
    }

    if (message.type === 'recording-started') {
      console.log('[Background] ✅ Recording started in offscreen mode');
      return;
    }

    if (message.type === 'recording-progress') {
      console.log(`[Background] Recording progress: ${message.chunkCount} chunks, ${message.size} bytes`);
      return;
    }

    if (message.type === 'upload-complete') {
      console.log('[Background] ✅ Upload complete:', message.filename);

      // Show notification
      await chrome.notifications.create({
        type: 'basic',
        iconUrl: browser.runtime.getURL('/icon/128.png'),
        title: 'Recording Uploaded',
        message: `${message.filename} uploaded successfully`,
      });

      return;
    }

    if (message.type === 'upload-error') {
      console.error('[Background] ❌ Upload failed:', message.error);

      // Show notification
      await chrome.notifications.create({
        type: 'basic',
        iconUrl: browser.runtime.getURL('/icon/128.png'),
        title: 'Upload Failed',
        message: `Failed to upload recording: ${message.error}`,
      });

      return;
    }

    if (message.type === 'download-recording') {
      console.log('[Background] Download request received for:', message.filename);
      console.log('[Background] Blob size:', message.blobSize, 'bytes');

      try {
        // Download using chrome.downloads API (only available in background)
        const downloadId = await chrome.downloads.download({
          url: message.blobUrl,
          filename: message.filename,
          saveAs: true,
        });

        console.log('[Background] Download initiated with ID:', downloadId);

        // Monitor download completion
        await waitForDownloadComplete(downloadId);

        console.log('[Background] Download verified complete');

        // Check if user is authenticated and initiate upload
        try {
          const authState = await getAuthState();
          if (authState.isAuthenticated && authState.authToken && authState.refreshToken) {
            console.log('[Background] User authenticated, requesting upload...');

            const backendUrl = await getBackendUrl();

            // Request offscreen to upload before cleaning up
            await browser.runtime.sendMessage({
              type: 'upload-recording',
              filename: message.filename,
              authToken: authState.authToken,
              refreshToken: authState.refreshToken,
              backendUrl,
            });

            console.log('[Background] Upload request sent to offscreen');
          } else {
            console.log('[Background] User not authenticated, skipping upload');

            // If not authenticated, proceed with cleanup immediately
            await browser.runtime.sendMessage({
              type: 'download-complete',
            });
          }
        } catch (uploadError) {
          console.error('[Background] Failed to initiate upload:', uploadError);

          // Continue with cleanup even if upload fails
          await browser.runtime.sendMessage({
            type: 'download-complete',
          });
        }

        // Notify that recording is complete
        await browser.runtime.sendMessage({
          type: 'recording-completed',
          filename: message.filename,
          success: true,
        });

      } catch (error) {
        console.error('[Background] Download failed:', error);

        // Notify offscreen of error
        await browser.runtime.sendMessage({
          type: 'download-error',
          error: error instanceof Error ? error.message : 'Download failed',
        });

        // Still send recording-completed to trigger cleanup
        await browser.runtime.sendMessage({
          type: 'recording-completed',
          filename: '',
          success: false,
        });
      }

      return;
    }

    if (message.type === 'recording-completed') {
      console.log('[Background] ✅ Recording completed:', message.filename);

      // Now safe to close offscreen document after download finished
      console.log('[Background] Closing offscreen document after successful download...');
      setTimeout(async () => {
        await closeOffscreenDocument();
        console.log('[Background] Offscreen document closed');
      }, 1000); // Small delay for cleanup

      return;
    }

    if (message.name === 'initiateRecording') {
      await startRecording(message.options || {});
    }

    if (message.name === 'stopRecording') {
      await stopRecording();
    }

    if (message.name === 'pauseRecording') {
      await pauseRecording();
    }

    if (message.name === 'toggleMicrophone') {
      await toggleMicrophone(message.enabled);
    }

    if (message.name === 'changeMicrophoneDevice') {
      await changeMicrophoneDevice(message.deviceId);
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
      console.error('[Background] No active tab found');
      return;
    }

    // Get microphone preferences from storage
    const { microphoneEnabled, selectedMicrophoneDeviceId } = await browser.storage.local.get([
      'microphoneEnabled',
      'selectedMicrophoneDeviceId'
    ]);

    // Merge options with mic preferences
    const fullOptions = {
      ...options,
      micEnabled: options.micEnabled ?? microphoneEnabled ?? false,
      micDeviceId: selectedMicrophoneDeviceId || undefined
    };

    // Store recording state
    await browser.storage.local.set({
      recording: true,
      activeTab: currentTab.id,
      recordingOptions: fullOptions,
    });

    // Use offscreen recorder only
    await createOffscreenRecorder(currentTab.id, fullOptions);
  } catch (error) {
    console.error('[Background] Failed to start recording:', error);
    await browser.storage.local.set({ recording: false });
  }
}

async function createOffscreenRecorder(
  originalTabId: number,
  options: RecordingOptions
) {
  // Check if offscreen API is available
  if (!chrome.offscreen) {
    console.error('Offscreen API not available - chrome.offscreen is undefined');
    throw new Error('Offscreen API not available');
  }

  console.log('[Background] Using offscreen recorder (modern mode)');

  // Close any existing offscreen document
  console.log('[Background] Closing any existing offscreen document...');
  await closeOffscreenDocument();

  // Create offscreen document for recording
  console.log('[Background] Creating offscreen document...');
  try {
    await chrome.offscreen.createDocument({
      url: browser.runtime.getURL('/offscreen-recorder.html'),
      reasons: [
        chrome.offscreen.Reason.USER_MEDIA,
        chrome.offscreen.Reason.DISPLAY_MEDIA,
      ] as chrome.offscreen.Reason[],
      justification: 'Recording screen using MediaRecorder API',
    });
    console.log('[Background] Offscreen document created successfully');
  } catch (error) {
    console.error('[Background] Failed to create offscreen document:', error);
    throw error;
  }

  // Store that we're using offscreen
  await browser.storage.local.set({
    recordingMode: 'offscreen',
    recordingTab: null,
  });
  console.log('[Background] Stored offscreen mode in storage');

  // Wait a bit for offscreen document to load
  await new Promise(resolve => setTimeout(resolve, 500));

  // Send message to offscreen document to start recording
  // The offscreen document will call getDisplayMedia() directly
  console.log('[Background] Sending startOffscreenRecording message...');
  try {
    await browser.runtime.sendMessage({
      name: 'startOffscreenRecording',
      originalTabId,
      options,
    });
    console.log('[Background] Message sent successfully');
  } catch (error) {
    console.error('[Background] Failed to send message to offscreen:', error);
    throw error;
  }

  // Switch back to original tab
  await browser.tabs.update(originalTabId, { active: true });
  console.log('[Background] Switched back to original tab');

  // Schedule safety cleanup
  scheduleOffscreenCleanup();
}

async function stopRecording() {
  console.log('[Background] stopRecording called');

  // Send message to offscreen document
  console.log('[Background] Sending stopOffscreenRecording message...');
  try {
    await browser.runtime.sendMessage({ name: 'stopOffscreenRecording' });
    console.log('[Background] Stop message sent');
  } catch (error) {
    console.error('[Background] Failed to send stop message:', error);
  }

  // DON'T close offscreen document immediately
  // Wait for recording-completed message to ensure download finishes
  console.log('[Background] Waiting for download to complete...');

  await browser.storage.local.set({ recording: false });
  console.log('[Background] Recording stopped, storage updated');
}

async function pauseRecording() {
  console.log('[Background] pauseRecording called');
  await browser.runtime.sendMessage({ name: 'pauseOffscreenRecording' });
}

async function toggleMicrophone(enabled: boolean) {
  console.log('[Background] toggleMicrophone called:', enabled);

  // Update storage
  await browser.storage.local.set({ microphoneEnabled: enabled });

  // Forward to offscreen document if recording is active
  const { recording, recordingMode } = await browser.storage.local.get(['recording', 'recordingMode']);

  if (recording && recordingMode === 'offscreen') {
    try {
      await browser.runtime.sendMessage({
        name: 'updateMicrophoneState',
        enabled: enabled
      });
      console.log('[Background] Microphone state forwarded to offscreen');
    } catch (error) {
      console.error('[Background] Failed to forward mic state to offscreen:', error);
    }
  }
}

async function changeMicrophoneDevice(deviceId: string) {
  console.log('[Background] changeMicrophoneDevice:', deviceId);

  // Update storage
  await browser.storage.local.set({ selectedMicrophoneDeviceId: deviceId });

  // Forward to offscreen if recording
  const { recording } = await browser.storage.local.get(['recording']);

  if (recording) {
    try {
      await browser.runtime.sendMessage({
        name: 'changeMicrophoneDevice',
        deviceId: deviceId
      });
      console.log('[Background] Device change forwarded to offscreen');
    } catch (error) {
      console.error('[Background] Failed to forward device change:', error);
    }
  }
}

async function scheduleOffscreenCleanup() {
  // Safety: close offscreen after 10 min if still open
  setTimeout(async () => {
    const { recording } = await browser.storage.local.get('recording');
    if (!recording) {
      console.log('[Background] Safety timeout: closing offscreen document');
      await closeOffscreenDocument();
    }
  }, 10 * 60 * 1000);
}

async function waitForDownloadComplete(downloadId: number): Promise<void> {
  console.log('[Background] Waiting for download to complete, ID:', downloadId);

  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      console.error('[Background] Download timeout after 5 minutes');
      chrome.downloads.onChanged.removeListener(handler);
      reject(new Error('Download timeout'));
    }, 5 * 60 * 1000); // 5 minute timeout

    const handler = (delta: chrome.downloads.DownloadDelta) => {
      // Only handle our specific download
      if (delta.id !== downloadId || !delta.state) return;

      console.log('[Background] Download state changed:', delta.state.current);

      const cleanup = () => {
        clearTimeout(timeoutId);
        chrome.downloads.onChanged.removeListener(handler);
      };

      // Download completed successfully
      if (delta.state.current === 'complete') {
        cleanup();
        resolve();
        return;
      }

      // Download interrupted or failed
      if (delta.state.current === 'interrupted') {
        const error = delta.error?.current;
        console.warn('[Background] Download interrupted:', error);

        cleanup();

        // If user canceled, that's not an error
        if (error === 'USER_CANCELED') {
          resolve();
        } else {
          reject(new Error(`Download failed: ${error || 'Unknown error'}`));
        }
      }
    };

    chrome.downloads.onChanged.addListener(handler);
  });
}

async function closeOffscreenDocument() {
  try {
    // Check if offscreen API is available
    if (!chrome.offscreen || !chrome.runtime.getContexts) {
      return; // API not available, nothing to close
    }

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
