// Single source of truth for the backend URL.
// Must be "localhost" (not 127.0.0.1) to match the frontend's host —
// otherwise the browser treats them as different sites and won't send cookies.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

/** fetch() to the backend that always sends the session cookie. */
export function apiFetch(path: string, init: RequestInit = {}) {
  return fetch(`${API_URL}${path}`, { ...init, credentials: "include" })
}