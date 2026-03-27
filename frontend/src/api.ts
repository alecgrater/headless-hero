export interface ApiResponse<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
}

interface ApiClient {
  get: (path: string) => Promise<ApiResponse>;
  post: (path: string, body?: unknown) => Promise<ApiResponse>;
  put: (path: string, body?: unknown) => Promise<ApiResponse>;
  delete: (path: string) => Promise<ApiResponse>;
  request: (method: string, path: string, body?: unknown) => Promise<ApiResponse>;
}

declare global {
  interface Window {
    api: ApiClient;
  }
}

// In Electron, window.api is injected by preload.js
// For dev without Electron, fall back to direct fetch
const api: ApiClient = window.api ?? {
  request: async (method: string, path: string, body?: unknown) => {
    const options: RequestInit = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (body && method !== "GET") {
      options.body = JSON.stringify(body);
    }
    const response = await fetch(`http://localhost:8420${path}`, options);
    const data = await response.json();
    return { ok: response.ok, status: response.status, data };
  },
  get: (path: string) => api.request("GET", path),
  post: (path: string, body?: unknown) => api.request("POST", path, body),
  put: (path: string, body?: unknown) => api.request("PUT", path, body),
  delete: (path: string) => api.request("DELETE", path),
};

export default api;

/** Clone a voice by uploading audio samples to ElevenLabs via the backend. */
export async function cloneVoice(
  name: string,
  files: File[],
  description?: string,
): Promise<{ voice_id: string }> {
  const formData = new FormData();
  formData.append("name", name);
  if (description) formData.append("description", description);
  for (const file of files) {
    formData.append("files", file);
  }

  const baseUrl = window.api ? "" : "http://localhost:8420";
  const response = await fetch(`${baseUrl}/api/voice/clone`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Clone failed" }));
    throw new Error(err.detail || "Voice cloning failed");
  }

  return response.json();
}

/** Prepend the backend origin to a static asset path (e.g. /static/projects/...). */
export function assetUrl(path: string): string {
  // In Electron, window.api exists and assets are proxied; in dev, hit backend directly
  if (window.api) return path;
  return `http://localhost:8420${path}`;
}
