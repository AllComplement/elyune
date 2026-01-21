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

export interface UploadCompleteResponse {
  status: string;
  recording: {
    id: string;
    status: string;
    [key: string]: any;
  };
}

export interface ApiError {
  error?: string;
  detail?: string;
  message?: string;
  [key: string]: any;
}
