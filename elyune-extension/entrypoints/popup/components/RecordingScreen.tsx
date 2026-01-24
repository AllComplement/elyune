import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function RecordingScreen() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [isRecording, setIsRecording] = useState(false);
  const [micEnabled, setMicEnabled] = useState(false);
  const [availableDevices, setAvailableDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);

  // Load initial state and sync with background
  useEffect(() => {
    // Load initial state from storage
    browser.storage.local.get(['recording', 'recordingMode', 'microphoneEnabled', 'selectedMicrophoneDeviceId']).then((data) => {
      setIsRecording(data.recording || false);
      setMicEnabled(data.microphoneEnabled || false);
      setSelectedDeviceId(data.selectedMicrophoneDeviceId || null);
    });

    // Listen for state changes
    const listener = (changes: Record<string, browser.storage.StorageChange>) => {
      if (changes.recording) {
        setIsRecording(changes.recording.newValue);
      }
      if (changes.microphoneEnabled) {
        setMicEnabled(changes.microphoneEnabled.newValue);
      }
    };

    browser.storage.onChanged.addListener(listener);

    return () => {
      browser.storage.onChanged.removeListener(listener);
    };
  }, []);

  const handleMicToggle = async () => {
    const newMicState = !micEnabled;

    // If enabling mic, open permission page in a new tab
    if (newMicState) {
      console.log('[Popup] Opening permission request page...');

      // Open permission page in new tab
      await browser.tabs.create({
        url: browser.runtime.getURL('/mic-permission.html'),
        active: true
      });

      // The permission page will update storage when permission is granted
      // Listen for the storage change
      const listener = (changes: Record<string, browser.storage.StorageChange>) => {
        if (changes.microphonePermissionGranted?.newValue === true) {
          console.log('[Popup] ✅ Permission granted in tab!');

          // Update UI
          setMicEnabled(true);

          // Enumerate devices
          navigator.mediaDevices.enumerateDevices().then(devices => {
            const audioInputs = devices.filter(d => d.kind === 'audioinput');
            setAvailableDevices(audioInputs);

            // Load selected device
            browser.storage.local.get('selectedMicrophoneDeviceId').then(data => {
              if (data.selectedMicrophoneDeviceId) {
                setSelectedDeviceId(data.selectedMicrophoneDeviceId);
              }
            });
          });

          browser.storage.onChanged.removeListener(listener);
        }
      };

      browser.storage.onChanged.addListener(listener);

      // Remove listener after 60 seconds if permission not granted
      setTimeout(() => {
        browser.storage.onChanged.removeListener(listener);
      }, 60000);

    } else {
      // Disabling mic - just update state
      setMicEnabled(false);
      await browser.storage.local.set({ microphoneEnabled: false });
    }

    // If recording is active, send message to update mic state in real-time
    if (isRecording) {
      try {
        await browser.runtime.sendMessage({
          name: 'toggleMicrophone',
          enabled: newMicState
        });
      } catch (error) {
        console.error('Failed to toggle microphone during recording:', error);
      }
    }
  };

  const handleStartRecording = async () => {
    try {
      await browser.runtime.sendMessage({
        name: 'initiateRecording',
        options: {
          micEnabled: micEnabled
        }
      });
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

  const handleDeviceChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const deviceId = e.target.value;
    setSelectedDeviceId(deviceId);
    await browser.storage.local.set({ selectedMicrophoneDeviceId: deviceId });

    // If recording, notify background to switch device
    if (isRecording) {
      await browser.runtime.sendMessage({
        name: 'changeMicrophoneDevice',
        deviceId: deviceId
      });
    }
  };

  const handleSettingsClick = () => {
    navigate('/settings');
  };

  const handleHistoryClick = () => {
    navigate('/history');
  };

  return (
    <div className="popup-container">
      <div className="recording-header">
        <h1>Screen Recorder</h1>
        <div className="header-controls">
          {user && (
            <span className="recording-user-info">
              {user.username}
            </span>
          )}
          <button
            onClick={handleHistoryClick}
            className="history-icon-btn"
            title="View recordings history"
          >
            📋
          </button>
          <button
            onClick={handleSettingsClick}
            className="settings-icon-btn"
            title="Settings"
          >
            ⚙️
          </button>
        </div>
      </div>

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

      <div className="mic-toggle-container">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={micEnabled}
            onChange={handleMicToggle}
            className="toggle-checkbox"
          />
          <span className="toggle-text">
            {micEnabled ? '🎤 Microphone On' : '🎤 Microphone Off'}
          </span>
        </label>

        {micEnabled && availableDevices.length > 0 && (
          <div className="device-selector-container">
            <label htmlFor="mic-device-select" className="device-label">
              Microphone Device:
            </label>
            <select
              id="mic-device-select"
              value={selectedDeviceId || ''}
              onChange={handleDeviceChange}
              className="device-select"
            >
              {availableDevices.map(device => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Microphone ${device.deviceId.slice(0, 8)}`}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {isRecording && (
        <p className="recording-status">
          Recording in progress. Do not close the recorder tab.
        </p>
      )}
    </div>
  );
}
