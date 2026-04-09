import { showToast } from "./components/ToastContainer";

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
  openExternal?: (url: string) => Promise<void>;
}

declare global {
  interface Window {
    api: ApiClient;
  }
}

/** Extract a human-readable error message from a non-ok API response. */
function extractErrorMessage(status: number, data: unknown): string {
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    if (typeof d.message === "string") return d.message;
  }
  if (status === 404) return "Resource not found";
  if (status === 422) return "Invalid request data";
  if (status >= 500) return "Server error — please try again";
  return `Request failed (${status})`;
}

/** Paths that should not trigger toast notifications on error. */
const SILENT_PATHS = ["/api/health", "/api/render/status/", "/api/visuals/title-cards-status/", "/api/character/status/"];

function shouldSilence(path: string): boolean {
  return SILENT_PATHS.some((p) => path.startsWith(p));
}

/** Wrap a request method to intercept non-ok responses and show toasts. */
function withErrorInterceptor(
  requestFn: (method: string, path: string, body?: unknown) => Promise<ApiResponse>,
): (method: string, path: string, body?: unknown) => Promise<ApiResponse> {
  return async (method, path, body) => {
    try {
      const res = await requestFn(method, path, body);
      if (!res.ok && !shouldSilence(path)) {
        showToast(extractErrorMessage(res.status, res.data));
      }
      return res;
    } catch (err) {
      if (!shouldSilence(path)) {
        showToast(
          err instanceof Error ? err.message : "Network error — is the backend running?",
        );
      }
      return { ok: false, status: 0, data: {} as unknown };
    }
  };
}

// In Electron, window.api is injected by preload.js
// For dev without Electron, fall back to direct fetch
const rawApi: ApiClient = window.api ?? {
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
  get: (path: string) => rawApi.request("GET", path),
  post: (path: string, body?: unknown) => rawApi.request("POST", path, body),
  put: (path: string, body?: unknown) => rawApi.request("PUT", path, body),
  delete: (path: string) => rawApi.request("DELETE", path),
};

const interceptedRequest = withErrorInterceptor(rawApi.request.bind(rawApi));

const api: ApiClient = {
  request: interceptedRequest,
  get: (path: string) => interceptedRequest("GET", path),
  post: (path: string, body?: unknown) => interceptedRequest("POST", path, body),
  put: (path: string, body?: unknown) => interceptedRequest("PUT", path, body),
  delete: (path: string) => interceptedRequest("DELETE", path),
  openExternal: rawApi.openExternal,
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
  return `http://localhost:8420${path}`;
}

/** Fetch generation time estimate for a given operation type. */
export async function fetchGenerationEstimate(
  operationType: string,
): Promise<{ average_seconds: number | null; sample_count: number }> {
  const res = await api.get(`/api/generation/estimate?operation_type=${operationType}`);
  if (res.ok) {
    const data = res.data as { average_seconds: number | null; sample_count: number };
    return data;
  }
  return { average_seconds: null, sample_count: 0 };
}

/** Generate FX assignments for all scenes in a script via Claude. */
export async function generateFX(scriptId: string) {
  return api.post("/api/fx/generate", { script_id: scriptId });
}

/** Regenerate FX for a single scene via Claude. */
export async function regenerateFX(scriptId: string, sceneId: string) {
  return api.post("/api/fx/regenerate", { script_id: scriptId, scene_id: sceneId });
}

/** Poll a title card background job until it completes or fails. */
export async function pollTitleCardJob(jobId: string): Promise<void> {
  const POLL_INTERVAL = 1500;
  const MAX_POLLS = 200; // ~5 minutes max
  for (let i = 0; i < MAX_POLLS; i++) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
    const res = await api.get(`/api/visuals/title-cards-status/${jobId}`);
    if (!res.ok) throw new Error("Failed to check title card job status");
    const job = res.data as { status: string; error: string | null };
    if (job.status === "completed") return;
    if (job.status === "failed") throw new Error(job.error || "Title card generation failed");
  }
  throw new Error("Title card generation timed out");
}

/** Open a URL in the system browser (Electron shell) or a new tab (dev). */
export function openInBrowser(url: string): void {
  if (window.api?.openExternal) {
    window.api.openExternal(url);
  } else {
    window.open(url, "_blank");
  }
}

/** Generate reference candidate images for character style selection. */
export async function generateCharacterReferences(): Promise<{ job_id: string }> {
  const res = await api.post("/api/character/generate-references");
  return res.data as { job_id: string };
}

/** Get list of reference candidates and which is selected. */
export async function getCharacterReferences(): Promise<{ references: string[]; selected: string | null }> {
  const res = await api.get("/api/character/references");
  return res.data as { references: string[]; selected: string | null };
}

/** Select a reference candidate as the canonical reference. */
export async function selectCharacterReference(filename: string): Promise<{ selected: string; path: string }> {
  const res = await api.post("/api/character/select-reference", { filename });
  return res.data as { selected: string; path: string };
}

/** Start generating the Eli character frame library. */
export async function generateCharacterFrames(referencePath?: string): Promise<{ job_id: string }> {
  const body = referencePath ? { reference_path: referencePath } : undefined;
  const res = await api.post("/api/character/generate-frames", body);
  return res.data as { job_id: string };
}

/** Get character frame manifest. */
export async function getCharacterFrames() {
  return api.get("/api/character/frames");
}

/** Start generating only missing Eli character frames. */
export async function generateMissingCharacterFrames(): Promise<{ job_id: string }> {
  const res = await api.post("/api/character/generate-missing");
  return res.data as { job_id: string };
}

/** Delete all character frames, references, and manifest. */
export async function clearAllCharacterFrames(): Promise<{ deleted_frames: number; deleted_references: number }> {
  const res = await api.delete("/api/character/clear-all");
  return res.data as { deleted_frames: number; deleted_references: number };
}

/** Poll character frame generation job status. */
export async function getCharacterStatus(jobId: string) {
  return api.get(`/api/character/status/${jobId}`);
}

/** Regenerate a single character frame. */
export async function regenerateCharacterFrame(frameId: string) {
  return api.post("/api/character/regenerate-frame", { frame_id: frameId });
}

/** Generate Eli animation overlays for all scenes. */
export async function generateEli(scriptId: string) {
  return api.post("/api/eli/generate", { script_id: scriptId });
}

/** Regenerate Eli animation for a single scene. */
export async function regenerateEli(scriptId: string, sceneId: string) {
  return api.post("/api/eli/regenerate", { script_id: scriptId, scene_id: sceneId });
}

/** Start export test pipeline (image → audio → FX → Eli → render) for scene 1 only. */
export async function exportTest(scriptId: string): Promise<{ job_id: string }> {
  const res = await api.post("/api/render/export-test", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Export test failed");
  return res.data as { job_id: string };
}
