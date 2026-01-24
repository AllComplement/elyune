/**
 * Settings Screen Component
 * Allows users to configure backend URL and logout
 */

import { useState, useEffect } from 'react';
import { getBackendUrl, setBackendUrl } from '../services/storage';
import { apiClient } from '../services/api';
import { useAuth } from '../hooks/useAuth';

export function SettingsScreen() {
  const { user, logout } = useAuth();
  const [backendUrl, setBackendUrlState] = useState('http://localhost:8000');
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'success' | 'error' | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    const url = await getBackendUrl();
    setBackendUrlState(url);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMessage('');

    try {
      // Validate URL format
      const urlPattern = /^https?:\/\/.+/;
      if (!urlPattern.test(backendUrl)) {
        setSaveMessage('Invalid URL format. Must start with http:// or https://');
        setSaving(false);
        return;
      }

      await setBackendUrl(backendUrl);
      apiClient.setBackendUrl(backendUrl);
      setSaveMessage('Settings saved successfully');
    } catch (error) {
      setSaveMessage('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTestingConnection(true);
    setConnectionStatus(null);

    try {
      // Update API client with current URL
      apiClient.setBackendUrl(backendUrl);
      const isConnected = await apiClient.testConnection();

      setConnectionStatus(isConnected ? 'success' : 'error');
    } catch {
      setConnectionStatus('error');
    } finally {
      setTestingConnection(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    // Navigation will happen automatically via useAuth context
  };

  const handleBack = () => {
    window.history.back();
  };

  return (
    <div className="settings-container">
      <div className="settings-header">
        <h1>Settings</h1>
        {user && <span className="user-badge">{user.username}</span>}
      </div>

      <div className="settings-content">
        <div className="settings-section">
          <label htmlFor="backend-url">Backend URL</label>
          <input
            id="backend-url"
            type="text"
            value={backendUrl}
            onChange={(e) => setBackendUrlState(e.target.value)}
            placeholder="http://localhost:8000"
            className="settings-input"
          />

          <div className="settings-actions-inline">
            <button
              onClick={testConnection}
              disabled={testingConnection}
              className="btn-secondary"
            >
              {testingConnection ? 'Testing...' : 'Test Connection'}
            </button>

            {connectionStatus === 'success' && (
              <span className="status-text success">Connected</span>
            )}
            {connectionStatus === 'error' && (
              <span className="status-text error">Failed</span>
            )}
          </div>

          {saveMessage && (
            <p className={`save-message ${saveMessage.includes('success') ? 'success' : 'error'}`}>
              {saveMessage}
            </p>
          )}
        </div>

        <div className="settings-actions">
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>

          <button
            onClick={handleBack}
            className="btn-secondary"
          >
            Back to Recording
          </button>

          {user && (
            <button
              onClick={handleLogout}
              className="btn-danger"
            >
              Logout
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
