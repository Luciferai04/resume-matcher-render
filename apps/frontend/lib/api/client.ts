/**
 * Centralized API Client
 *
 * Single source of truth for API configuration and base fetch utilities.
 */

import { getUserId } from './auth';

const getApiUrl = () => {
  let url = process.env.NEXT_PUBLIC_API_URL ?? '';
  
  if (typeof window !== 'undefined') {
    // If URL is protocol-relative (//example.com), use current protocol
    if (url.startsWith('//')) {
      url = window.location.protocol + url;
    }
    // If we're on a secure page, force HTTPS for absolute URLs
    if (window.location.protocol === 'https:' && url.startsWith('http:')) {
      url = url.replace('http:', 'https:');
    }
  }

  // Normalize: remove trailing slash and strip /api/v1 if redundant
  url = url.replace(/\/+$/, '');
  if (url.endsWith('/api/v1')) {
    url = url.slice(0, -7);
  }
  
  return url;
};

export const API_URL = getApiUrl();
export const API_BASE = `${API_URL}/api/v1`;

export async function apiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
  // Determine if we need to prepend API_BASE
  // Don't prepend if:
  // 1. It's a full URL (starts with http)
  // 2. It already starts with API_BASE
  // 3. It already starts with /api/v1 (redundancy check)
  let url = endpoint;
  if (!endpoint.startsWith('http')) {
    const basePrefix = API_BASE.replace(/\/+$/, '');
    if (!endpoint.startsWith(basePrefix) && !endpoint.startsWith('/api/v1')) {
      url = `${basePrefix}${endpoint}`;
    }
  }
  
  // Inject X-User-ID header for multi-tenancy
  const headers = new Headers(options?.headers);
  headers.set('X-User-ID', getUserId());

  return fetch(url, {
    cache: 'no-store',
    ...options,
    headers,
  });
}

/**
 * POST request with JSON body.
 */
export async function apiPost<T>(endpoint: string, body: T): Promise<Response> {
  return apiFetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * PATCH request with JSON body.
 */
export async function apiPatch<T>(endpoint: string, body: T): Promise<Response> {
  return apiFetch(endpoint, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * PUT request with JSON body.
 */
export async function apiPut<T>(endpoint: string, body: T): Promise<Response> {
  return apiFetch(endpoint, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * DELETE request.
 */
export async function apiDelete(endpoint: string): Promise<Response> {
  return apiFetch(endpoint, { method: 'DELETE' });
}

/**
 * Builds the full upload URL for file uploads.
 */
export function getUploadUrl(parentId?: string): string {
  const base = `${API_BASE}/resumes/upload`;
  return parentId ? `${base}?parent_id=${parentId}` : base;
}
