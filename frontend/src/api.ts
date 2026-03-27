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
