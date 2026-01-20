console.log('[Recorder] Script loading...');

interface RecordingMessage {
  name: string;
  body?: {
    currentTabId: number;
  };
}

let mediaRecorder: MediaRecorder | null = null;
let chunks: Blob[] = [];
let currentStream: MediaStream | null = null;

console.log('[Recorder] Setting up message listener...');

// Listen for messages from background
browser.runtime.onMessage.addListener((message: RecordingMessage) => {
  console.log('[Recorder] Received message:', message.name);
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

    // Add chunk counter to UI
    const chunkCounter = document.createElement('div');
    chunkCounter.id = 'chunk-counter';
    chunkCounter.style.cssText = 'position: fixed; top: 20px; right: 20px; background: rgba(0,0,0,0.8); color: white; padding: 10px; border-radius: 5px; font-family: monospace;';
    chunkCounter.textContent = 'Chunks: 0 | Size: 0 MB';
    document.body.appendChild(chunkCounter);

    let totalSize = 0;

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
        totalSize += event.data.size;
        console.log(`Chunk ${chunks.length} received: ${(event.data.size / 1024).toFixed(2)} KB`);

        // Update counter
        if (chunkCounter) {
          chunkCounter.textContent = `Chunks: ${chunks.length} | Size: ${(totalSize / 1024 / 1024).toFixed(2)} MB`;
        }
      }
    };

    mediaRecorder.onstop = async () => {
      await handleRecordingStop();
    };

    mediaRecorder.start(1000); // Capture in 1-second chunks
    console.log('MediaRecorder started, state:', mediaRecorder.state);

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
    console.log('Stopping recording...');
    console.log('Number of chunks recorded:', chunks.length);

    // Stop all tracks
    if (currentStream) {
      currentStream.getTracks().forEach(track => track.stop());
      console.log('Stream tracks stopped');
    }

    // Check if we have any chunks
    if (chunks.length === 0) {
      console.error('No chunks recorded! Recording may have failed.');
      alert('No video data was recorded. Please try again.');
      setTimeout(() => window.close(), 2000);
      return;
    }

    // Create blob from recorded chunks
    const blob = new Blob(chunks, { type: 'video/webm' });
    console.log('Blob created, size:', blob.size, 'bytes');

    if (blob.size === 0) {
      console.error('Blob is empty!');
      alert('Recording failed - no data captured.');
      setTimeout(() => window.close(), 2000);
      return;
    }

    const url = URL.createObjectURL(blob);
    console.log('Blob URL created:', url);

    // Generate filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const filename = `screen-recording-${timestamp}.webm`;

    // Download the recording - append to DOM first for better compatibility
    const downloadLink = document.createElement('a');
    downloadLink.href = url;
    downloadLink.download = filename;
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);

    console.log('Triggering download for:', filename);
    downloadLink.click();

    // Clean up after a delay
    setTimeout(() => {
      document.body.removeChild(downloadLink);
      URL.revokeObjectURL(url);
      console.log('Cleanup complete');
    }, 100);

    chunks = [];
    console.log('Recording saved successfully:', filename);

    // Show success message
    document.body.innerHTML = `
      <div class="warning-container">
        <div class="warning-icon">✅</div>
        <h1>Recording Saved!</h1>
        <p>File: ${filename}</p>
        <p>Size: ${(blob.size / 1024 / 1024).toFixed(2)} MB</p>
      </div>
    `;

    // Close the recorder tab
    setTimeout(() => window.close(), 3000);
  } catch (error) {
    console.error('Failed to save recording:', error);
    alert(`Failed to save recording: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}
