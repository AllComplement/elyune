/**
 * TypeScript interfaces for Elyune Backend API
 */

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  date_joined?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface SignupRequest {
  username: string;
  email: string;
  password: string;
  password2: string;
  first_name?: string;
  last_name?: string;
}

export interface AuthResponse {
  message: string;
  user: User;
  tokens: {
    access: string;
    refresh: string;
  };
}

export interface TokenRefreshRequest {
  refresh: string;
}

export interface TokenRefreshResponse {
  access: string;
}

export interface RecordingMetadata {
  filename: string;
  file_size: number;
  quality: string;
  fps: number;
  has_system_audio: boolean;
  has_microphone: boolean;
  codec?: string;
}

export interface UploadUrlResponse {
  recording_id: string;
  upload_url: string;
  s3_key: string;
}

export interface UploadCompleteRequest {
  s3_key: string;
}

/**
 * Recording file object
 */
export interface RecordingFile {
  id: string;
  file_type: 'original_webm' | 'converted_mp4' | 'audio_extract';
  s3_key: string;
  s3_bucket: string;
  file_size_bytes: number;
  created_at: string;
}

/**
 * Transcription segment with speaker diarization
 */
export interface TranscriptionSegment {
  start: number;
  end: number;
  text: string;
  confidence: number;
  speaker_id?: number;
  speaker_label?: string;
  words?: Array<{
    word: string;
    start: number;
    end: number;
    confidence: number;
  }>;
}

/**
 * Consolidated recording analysis data
 * Contains transcription + all AI analysis results
 */
export interface RecordingAnalysis {
  // Transcription fields
  transcription_text: string;
  transcription_confidence?: number;
  transcription_language?: string;
  transcription_num_speakers?: number;
  transcription_audio_duration?: number;
  transcription_processing_time?: number;
  transcription_segments: TranscriptionSegment[];
  
  // Summary analysis
  summary_text?: string;
  summary_data?: Record<string, any>;
  summary_tokens?: number;
  summary_processing_time?: number;
  summary_model_version?: string;
  
  // Action items analysis
  action_items_text?: string;
  action_items_data?: Record<string, any>;
  action_items_tokens?: number;
  action_items_processing_time?: number;
  action_items_model_version?: string;
  
  // Key points analysis
  key_points_text?: string;
  key_points_data?: Record<string, any>;
  key_points_tokens?: number;
  key_points_processing_time?: number;
  key_points_model_version?: string;
  
  // Sentiment analysis
  sentiment_text?: string;
  sentiment_data?: Record<string, any>;
  sentiment_tokens?: number;
  sentiment_processing_time?: number;
  sentiment_model_version?: string;
  
  // Processing totals
  total_tokens_used?: number;
  total_processing_time?: number;
  
  created_at?: string;
  updated_at?: string;
}

/**
 * Recording detail response
 * Updated to match new consolidated backend API format
 */
export interface Recording {
  id: string;
  user: string;
  title: string;
  status: 'uploading' | 'uploaded' | 'processing' | 'completed' | 'failed';
  quality: string;
  fps: number;
  duration_seconds?: number;
  has_system_audio: boolean;
  has_microphone: boolean;
  original_filename: string;
  file_size_bytes: number;
  mime_type?: string;
  codec?: string;
  error_message?: string;
  
  // Processing tracking (NEW in refactored backend)
  processing_progress: number; // 0-100
  processing_started_at?: string;
  celery_task_id?: string;
  
  // Timestamps
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  
  // Nested relationships (NEW in refactored backend)
  files: RecordingFile[];
  analysis?: RecordingAnalysis | null; // Null if not yet processed
}

/**
 * Recording list item (lighter response)
 */
export interface RecordingListItem {
  id: string;
  title: string;
  quality: string;
  duration: number | null;
  status: 'uploading' | 'uploaded' | 'processing' | 'completed' | 'failed';
  processing_progress: number;
  original_filename: string;
  file_size_bytes: number;
  has_audio: boolean;
  error_message?: string;
  created_at: string;
  // Optional analysis preview fields
  analysis?: {
    transcription_num_speakers?: number;
    has_summary?: boolean;
    has_action_items?: boolean;
    has_key_points?: boolean;
  };
}

export interface UploadCompleteResponse {
  status: string;
  recording: Recording;
}

export interface ApiError {
  error?: string;
  detail?: string;
  message?: string;
  [key: string]: any;
}

