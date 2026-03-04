/**
 * Lightweight Auth Utility for Multi-tenancy MVP
 * 
 * Manages the current X-User-ID in localStorage.
 */

const USER_ID_KEY = 'resume_matcher_user_id';
const DEFAULT_USER_ID = 'student_001'; // Default for MVP

/**
 * Gets the current user ID from localStorage.
 * Falls back to a default ID if none is set.
 */
export function getUserId(): string {
    if (typeof window === 'undefined') return DEFAULT_USER_ID;
    return localStorage.getItem(USER_ID_KEY) || DEFAULT_USER_ID;
}

/**
 * Sets the current user ID in localStorage.
 */
export function setUserId(userId: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem(USER_ID_KEY, userId);
    // Reload the page to ensure all API calls use the new ID
    window.location.reload();
}
