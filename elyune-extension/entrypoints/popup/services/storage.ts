/**
 * Chrome Storage Utilities
 * Helper functions for interacting with chrome.storage.local
 */

import { browser } from 'wxt/browser';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
}

export interface AuthState {
  authToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  user: User | null;
}

export interface StorageData extends AuthState {
  backendUrl: string;
  // Existing recording state fields
  recording?: boolean;
  recordingMode?: 'offscreen' | 'tab';
  microphoneEnabled?: boolean;
  selectedMicrophoneDeviceId?: string | null;
  activeTab?: number | null;
}

/**
 * Get authentication state from storage
 */
export async function getAuthState(): Promise<AuthState> {
  const data = await browser.storage.local.get([
    'authToken',
    'refreshToken',
    'isAuthenticated',
    'user',
  ]);

  return {
    authToken: data.authToken || null,
    refreshToken: data.refreshToken || null,
    isAuthenticated: data.isAuthenticated || false,
    user: data.user || null,
  };
}

/**
 * Set authentication state in storage
 */
export async function setAuthState(
  authToken: string,
  refreshToken: string,
  user: User
): Promise<void> {
  await browser.storage.local.set({
    authToken,
    refreshToken,
    isAuthenticated: true,
    user,
  });
}

/**
 * Clear authentication state from storage
 */
export async function clearAuthState(): Promise<void> {
  await browser.storage.local.remove([
    'authToken',
    'refreshToken',
    'isAuthenticated',
    'user',
  ]);
}

/**
 * Get backend URL from storage
 */
export async function getBackendUrl(): Promise<string> {
  const data = await browser.storage.local.get('backendUrl');
  return data.backendUrl || 'http://localhost:8000';
}

/**
 * Set backend URL in storage
 */
export async function setBackendUrl(url: string): Promise<void> {
  // Ensure URL doesn't have trailing slash
  const cleanUrl = url.endsWith('/') ? url.slice(0, -1) : url;
  await browser.storage.local.set({ backendUrl: cleanUrl });
}

/**
 * Initialize default values in storage if not present
 */
export async function initializeStorage(): Promise<void> {
  const data = await browser.storage.local.get(['backendUrl', 'isAuthenticated']);

  if (!data.backendUrl) {
    await setBackendUrl('http://localhost:8000');
  }

  if (data.isAuthenticated === undefined) {
    await browser.storage.local.set({ isAuthenticated: false });
  }
}
