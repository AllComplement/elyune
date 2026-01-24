import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../services/api';
import type { RecordingListItem } from '../types/api.types';

export function RecordingsListScreen() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [recordings, setRecordings] = useState<RecordingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRecordings();
  }, []);

  const loadRecordings = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getRecordings();
      setRecordings(response.results);
    } catch (err) {
      console.error('Failed to load recordings:', err);
      setError('Failed to load recordings. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSettingsClick = () => {
    navigate('/settings');
  };

  const handleBackClick = () => {
    navigate('/');
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'completed':
        return 'status-completed';
      case 'processing':
        return 'status-processing';
      case 'failed':
        return 'status-failed';
      case 'uploading':
        return 'status-uploading';
      default:
        return 'status-completed';
    }
  };

  const getStatusText = (status: string, progress?: number) => {
    if (status === 'processing' && progress !== undefined) {
      return `Processing ${progress}%`;
    }
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  return (
    <div className="recordings-container">
      <div className="recordings-header">
        <button
          onClick={handleBackClick}
          className="back-button"
          title="Back to recording"
        >
          ← Back
        </button>
        <div className="recordings-header-row">
          <h1>Recordings</h1>
          <div className="header-controls">
            {user && (
              <span className="recording-user-info">
                {user.username}
              </span>
            )}
            <button
              onClick={handleSettingsClick}
              className="settings-icon-btn"
              title="Settings"
            >
              ⚙
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div className="recordings-loading">
          <p>Loading recordings...</p>
        </div>
      )}

      {error && (
        <div className="recordings-error">
          <p>{error}</p>
          <button onClick={loadRecordings} className="btn-secondary">
            Retry
          </button>
        </div>
      )}

      {!loading && !error && recordings.length === 0 && (
        <div className="recordings-empty">
          <p>No recordings yet.</p>
          <p className="recordings-empty-hint">
            Start a recording to see it here!
          </p>
        </div>
      )}

      {!loading && !error && recordings.length > 0 && (
        <div className="recordings-content">
          <div className="recordings-list">
            {recordings.map((recording) => (
              <div key={recording.id} className="recording-item">
                <div className="recording-item-header">
                  <div>
                    <span className="recording-date">
                      {formatDate(recording.created_at)}
                    </span>
                    <span
                      className={`recording-status-badge ${getStatusClass(recording.status)}`}
                    >
                      {getStatusText(recording.status, recording.processing_progress)}
                    </span>
                  </div>
                </div>

              <div className="recording-item-details">
                <div className="recording-detail-row">
                  <span className="recording-detail-label">Duration:</span>
                  <span className="recording-detail-value">
                    {formatDuration(recording.duration)}
                  </span>
                </div>

                {recording.quality && (
                  <div className="recording-detail-row">
                    <span className="recording-detail-label">Quality:</span>
                    <span className="recording-detail-value">
                      {recording.quality}
                    </span>
                  </div>
                )}

                {recording.has_audio && (
                  <div className="recording-detail-row">
                    <span className="recording-detail-label">Audio:</span>
                    <span className="recording-detail-value">
                      Included
                    </span>
                  </div>
                )}
              </div>

              {recording.status === 'completed' && recording.analysis && (
                <div className="recording-analysis-preview">
                  {recording.analysis.transcription_num_speakers && (
                    <div className="analysis-stat">
                      <span className="analysis-stat-label">Speakers:</span>
                      <span className="analysis-stat-value">
                        {recording.analysis.transcription_num_speakers}
                      </span>
                    </div>
                  )}
                  {recording.analysis.has_summary && (
                    <div className="analysis-stat">
                      <span className="analysis-stat-label">✓</span>
                      <span className="analysis-stat-value">Summary</span>
                    </div>
                  )}
                  {recording.analysis.has_action_items && (
                    <div className="analysis-stat">
                      <span className="analysis-stat-label">✓</span>
                      <span className="analysis-stat-value">Action Items</span>
                    </div>
                  )}
                </div>
              )}

              {recording.status === 'failed' && recording.error_message && (
                <div className="recording-error-message">
                  Error: {recording.error_message}
                </div>
              )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="recordings-footer">
        <button onClick={loadRecordings} className="btn-secondary">
          Refresh
        </button>
      </div>
    </div>
  );
}
