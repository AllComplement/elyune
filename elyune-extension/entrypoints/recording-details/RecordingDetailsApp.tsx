import { useState, useEffect } from 'react';
import { apiClient } from '../popup/services/api';
import { getAuthState, getBackendUrl } from '../popup/services/storage';
import type { Recording } from '../popup/types/api.types';

export function RecordingDetailsApp() {
  const [recording, setRecording] = useState<Recording | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  useEffect(() => {
    loadRecordingDetails();
  }, []);

  const loadRecordingDetails = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get recording ID from URL params
      const params = new URLSearchParams(window.location.search);
      const recordingId = params.get('id');

      if (!recordingId) {
        setError('No recording ID provided');
        setLoading(false);
        return;
      }

      // Initialize API client
      const authState = await getAuthState();
      const backendUrl = await getBackendUrl();
      
      if (!authState.authToken) {
        setError('Not authenticated. Please log in.');
        setLoading(false);
        return;
      }

      apiClient.setBackendUrl(backendUrl);
      apiClient.setAuthTokens(authState.authToken, authState.refreshToken || '');

      // Fetch recording details
      const recordingData = await apiClient.getRecording(recordingId);
      setRecording(recordingData);

      // Get video URL if available
      const mp4File = recordingData.files.find((f: any) => f.file_type === 'converted_mp4');
      if (mp4File) {
        // In a real implementation, you'd get a presigned URL from the backend
        // For now, we'll construct the URL (this needs backend support)
        setVideoUrl(`${backendUrl}/api/v1/recordings/${recordingId}/video/`);
      }

    } catch (err) {
      console.error('Failed to load recording:', err);
      setError(err instanceof Error ? err.message : 'Failed to load recording');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="details-container">
        <div className="details-loading">
          <p>Loading recording...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="details-container">
        <div className="details-error">
          <h2>Error</h2>
          <p>{error}</p>
          <button onClick={() => window.close()} className="btn-secondary">
            Close
          </button>
        </div>
      </div>
    );
  }

  if (!recording) {
    return (
      <div className="details-container">
        <div className="details-error">
          <p>Recording not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="details-container">
      {/* Header */}
      <header className="details-header">
        <div className="details-header-content">
          <h1 className="details-title">{recording.title || 'Untitled Recording'}</h1>
          <p className="details-meta">
            {formatDate(recording.created_at)} • {formatDuration(recording.duration_seconds)}
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="details-main">
        {/* Video Player */}
        <section className="details-section video-section">
          <h2>Recording</h2>
          {videoUrl ? (
            <div className="video-player-container">
              <video 
                controls 
                className="video-player"
                poster="/icon/128.png"
              >
                <source src={videoUrl} type="video/mp4" />
                Your browser does not support the video tag.
              </video>
            </div>
          ) : (
            <div className="video-placeholder">
              <p>Video is being processed...</p>
              {recording.status === 'processing' && (
                <p className="processing-status">
                  Processing: {recording.processing_progress}%
                </p>
              )}
            </div>
          )}
        </section>

        {/* AI Analysis Section */}
        {recording.analysis && (
          <div className="analysis-container">
            {/* Summary */}
            {recording.analysis.summary_text && (
              <section className="details-section">
                <h2>Summary</h2>
                <div className="analysis-content">
                  <p>{recording.analysis.summary_text}</p>
                </div>
              </section>
            )}

            {/* Action Items */}
            {recording.analysis.action_items_text && (
              <section className="details-section">
                <h2>Action Items</h2>
                <div className="analysis-content action-items">
                  {recording.analysis.action_items_data?.items ? (
                    <ul className="action-items-list">
                      {recording.analysis.action_items_data.items.map((item: string, idx: number) => (
                        <li key={idx} className="action-item">{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>{recording.analysis.action_items_text}</p>
                  )}
                </div>
              </section>
            )}

            {/* Key Points */}
            {recording.analysis.key_points_text && (
              <section className="details-section">
                <h2>Key Points</h2>
                <div className="analysis-content key-points">
                  {recording.analysis.key_points_data?.points ? (
                    <ul className="key-points-list">
                      {recording.analysis.key_points_data.points.map((point: string, idx: number) => (
                        <li key={idx} className="key-point">{point}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>{recording.analysis.key_points_text}</p>
                  )}
                </div>
              </section>
            )}

            {/* Transcription */}
            {recording.analysis.transcription_text && (
              <section className="details-section">
                <h2>Transcription</h2>
                {recording.analysis.transcription_num_speakers && (
                  <p className="transcription-meta">
                    {recording.analysis.transcription_num_speakers} speaker(s) detected
                  </p>
                )}
                <div className="analysis-content transcription">
                  {recording.analysis.transcription_segments && recording.analysis.transcription_segments.length > 0 ? (
                    <div className="transcription-segments">
                      {recording.analysis.transcription_segments.map((segment, idx) => (
                        <div key={idx} className="transcription-segment">
                          <div className="segment-header">
                            {segment.speaker_label && (
                              <span className="speaker-label">{segment.speaker_label}</span>
                            )}
                            <span className="segment-time">
                              {formatTimestamp(segment.start)} - {formatTimestamp(segment.end)}
                            </span>
                          </div>
                          <p className="segment-text">{segment.text}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="transcription-text">{recording.analysis.transcription_text}</p>
                  )}
                </div>
              </section>
            )}

            {/* Sentiment */}
            {recording.analysis.sentiment_text && (
              <section className="details-section">
                <h2>Sentiment Analysis</h2>
                <div className="analysis-content">
                  <p>{recording.analysis.sentiment_text}</p>
                </div>
              </section>
            )}
          </div>
        )}

        {/* No Analysis Available */}
        {!recording.analysis && recording.status === 'completed' && (
          <section className="details-section">
            <div className="no-analysis">
              <p>No analysis available for this recording.</p>
            </div>
          </section>
        )}

        {/* Processing Status */}
        {recording.status === 'processing' && (
          <section className="details-section">
            <div className="processing-info">
              <h3>Processing Recording...</h3>
              <p>Progress: {recording.processing_progress}%</p>
              <p className="processing-hint">
                Analysis will appear here once processing is complete.
              </p>
            </div>
          </section>
        )}

        {/* Failed Status */}
        {recording.status === 'failed' && (
          <section className="details-section">
            <div className="failed-info">
              <h3>Processing Failed</h3>
              {recording.error_message && <p>{recording.error_message}</p>}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

// Helper function to format timestamps
function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
