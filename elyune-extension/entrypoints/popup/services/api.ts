/**
 * Elyune API Client
 * Centralized API client for all backend communication
 */

import type {
  LoginRequest,
  SignupRequest,
  AuthResponse,
  TokenRefreshResponse,
  RecordingMetadata,
  UploadUrlResponse,
  UploadCompleteRequest,
  UploadCompleteResponse,
  ApiError,
} from '../types/api.types';
import { getBackendUrl, getAuthState, setAuthState, clearAuthState } from './storage';

class ApiClient {
  private baseUrl: string = '';
  private authToken: string | null = null;
  private refreshToken: string | null = null;
  private isRefreshing: boolean = false;

  /**
   * Initialize the API client with backend URL and auth tokens
   */
  async initialize(): Promise<void> {
    this.baseUrl = await getBackendUrl();
    const authState = await getAuthState();
    this.authToken = authState.authToken;
    this.refreshToken = authState.refreshToken;
  }

  /**
   * Set the backend URL
   */
  setBackendUrl(url: string): void {
    this.baseUrl = url.endsWith('/') ? url.slice(0, -1) : url;
  }

  /**
   * Set authentication tokens
   */
  setAuthTokens(accessToken: string | null, refreshToken: string | null): void {
    this.authToken = accessToken;
    this.refreshToken = refreshToken;
  }

  /**
   * Generic request method with automatic token refresh
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    // Ensure client is initialized
    if (!this.baseUrl) {
      await this.initialize();
    }

    const url = `${this.baseUrl}${endpoint}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // Add authorization header if token exists
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle 401 Unauthorized - try to refresh token
      if (response.status === 401 && !this.isRefreshing && this.refreshToken) {
        this.isRefreshing = true;

        try {
          // Attempt token refresh
          await this.refreshAccessToken();
          this.isRefreshing = false;

          // Retry original request with new token
          headers['Authorization'] = `Bearer ${this.authToken}`;
          const retryResponse = await fetch(url, {
            ...options,
            headers,
          });

          return await this.handleResponse<T>(retryResponse);
        } catch (refreshError) {
          this.isRefreshing = false;
          // Refresh failed - clear auth state
          await clearAuthState();
          this.authToken = null;
          this.refreshToken = null;
          throw new Error('Session expired. Please login again.');
        }
      }

      return await this.handleResponse<T>(response);
    } catch (error) {
      // Network error or other fetch errors
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Network error. Please check your connection.');
    }
  }

  /**
   * Handle response and parse JSON
   */
  private async handleResponse<T>(response: Response): Promise<T> {
    const contentType = response.headers.get('content-type');
    const isJson = contentType?.includes('application/json');

    if (!response.ok) {
      if (isJson) {
        const errorData: ApiError = await response.json();
        const errorMessage =
          errorData.error ||
          errorData.detail ||
          errorData.message ||
          `Request failed with status ${response.status}`;
        throw new Error(errorMessage);
      } else {
        throw new Error(`Request failed with status ${response.status}`);
      }
    }

    if (isJson) {
      return await response.json();
    }

    // Non-JSON response (e.g., for PUT to presigned URL)
    return {} as T;
  }

  /**
   * Login user
   */
  async login(username: string, password: string): Promise<AuthResponse> {
    const data: LoginRequest = { username, password };

    const response = await this.request<AuthResponse>('/api/auth/login/', {
      method: 'POST',
      body: JSON.stringify(data),
    });

    // Store tokens
    this.setAuthTokens(response.tokens.access, response.tokens.refresh);
    await setAuthState(response.tokens.access, response.tokens.refresh, response.user);

    return response;
  }

  /**
   * Signup new user
   */
  async signup(signupData: SignupRequest): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/api/auth/signup/', {
      method: 'POST',
      body: JSON.stringify(signupData),
    });

    // Store tokens
    this.setAuthTokens(response.tokens.access, response.tokens.refresh);
    await setAuthState(response.tokens.access, response.tokens.refresh, response.user);

    return response;
  }

  /**
   * Refresh access token
   */
  async refreshAccessToken(): Promise<void> {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${this.baseUrl}/api/auth/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh: this.refreshToken }),
    });

    if (!response.ok) {
      throw new Error('Token refresh failed');
    }

    const data: TokenRefreshResponse = await response.json();

    // Update auth token
    this.authToken = data.access;

    // Update storage
    const authState = await getAuthState();
    if (authState.user && authState.refreshToken) {
      await setAuthState(data.access, authState.refreshToken, authState.user);
    }
  }

  /**
   * Request upload URL for a recording
   */
  async requestUpload(metadata: RecordingMetadata): Promise<UploadUrlResponse> {
    return await this.request<UploadUrlResponse>('/api/v1/recordings/request-upload/', {
      method: 'POST',
      body: JSON.stringify(metadata),
    });
  }

  /**
   * Upload file to presigned URL
   */
  async uploadToPresignedUrl(url: string, blob: Blob): Promise<void> {
    console.log('[API] Uploading to presigned URL:', url);
    console.log('[API] Blob type:', blob.type, 'Size:', blob.size);
    
    try {
      const response = await fetch(url, {
        method: 'PUT',
        body: blob,
        headers: {
          'Content-Type': 'video/webm',
        },
      });

      if (!response.ok) {
        const text = await response.text();
        console.error('[API] Upload failed status:', response.status);
        console.error('[API] Upload failed body:', text);
        throw new Error(`Failed to upload to S3: ${response.status}`);
      }
    } catch (error) {
      console.error('[API] Upload fetch error:', error);
      throw error;
    }
  }

  /**
   * Notify backend that upload is complete
   */
  async notifyUploadComplete(
    recordingId: string,
    s3Key: string
  ): Promise<UploadCompleteResponse> {
    const data: UploadCompleteRequest = { s3_key: s3Key };

    return await this.request<UploadCompleteResponse>(
      `/api/v1/recordings/${recordingId}/upload-complete/`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  /**
   * Test connection to backend
   */
  async testConnection(): Promise<boolean> {
    try {
      // Try to fetch the login endpoint with OPTIONS (doesn't require auth)
      const response = await fetch(`${this.baseUrl}/api/auth/login/`, {
        method: 'OPTIONS',
      });

      return response.ok || response.status === 200 || response.status === 204;
    } catch {
      return false;
    }
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
