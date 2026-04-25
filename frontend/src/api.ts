import { showToast } from "./components/ToastContainer";
import { BACKEND_PORT } from "./constants";

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
  downloadFile?: (url: string, defaultFilename: string) => Promise<{ canceled: boolean; filePath?: string }>;
  showItemInFolder?: (fullPath: string) => Promise<void>;
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
const SILENT_PATHS = ["/api/health", "/api/render/status/", "/api/visuals/title-cards-status/", "/api/character/status/", "/api/scripts/generate-status/", "/api/scripts/cold-opens-status/", "/api/scripts/refine-hook-status/", "/api/trending/refresh-status/", "/api/eli/generate-status/"];

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
      signal: AbortSignal.timeout(20 * 60 * 1000), // 20 minutes — segmented script gen can take 7+min
    };
    if (body && method !== "GET") {
      options.body = JSON.stringify(body);
    }
    const response = await fetch(`http://localhost:${BACKEND_PORT}${path}`, options);
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

  const baseUrl = `http://localhost:${BACKEND_PORT}`;
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
  return `http://localhost:${BACKEND_PORT}${path}`;
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

/** Fetch the total estimated cost for a script. */
export async function fetchScriptCost(scriptId: string): Promise<{ total_cost: number }> {
  const res = await api.get(`/api/scripts/${scriptId}/cost`);
  if (res.ok) {
    return res.data as { total_cost: number };
  }
  return { total_cost: 0 };
}

/** Generate FX assignments for all scenes in a script via Claude. */
export async function generateFX(scriptId: string, missingOnly = false) {
  return api.post("/api/fx/generate", { script_id: scriptId, missing_only: missingOnly });
}

/** Regenerate FX for a single scene via Claude. */
export async function regenerateFX(scriptId: string, sceneId: string) {
  return api.post("/api/fx/regenerate", { script_id: scriptId, scene_id: sceneId });
}

/** Generate Eli animation overlays for all scenes in a script via Claude. */
export async function generateEli(scriptId: string, missingOnly = false) {
  return api.post("/api/eli/generate", { script_id: scriptId, missing_only: missingOnly });
}

/** Regenerate Eli overlay for a single scene via Claude. */
export async function regenerateEli(scriptId: string, sceneId: string) {
  return api.post("/api/eli/regenerate", { script_id: scriptId, scene_id: sceneId });
}

/** Split a scene at a specific audio timestamp via the backend. */
export async function splitSceneAtTime(scriptId: string, sceneId: string, splitTimeMs: number) {
  return api.post(`/api/scripts/${scriptId}/split-scene`, {
    scene_id: sceneId,
    split_time_ms: splitTimeMs,
  });
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

/** Poll an Eli generation background job until it completes or fails. */
export async function pollEliJob(jobId: string): Promise<void> {
  const POLL_INTERVAL = 1500;
  const MAX_POLLS = 800; // ~20 minutes max
  for (let i = 0; i < MAX_POLLS; i++) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL));
    const res = await api.get(`/api/eli/generate-status/${jobId}`);
    if (!res.ok) throw new Error("Failed to check Eli job status");
    const job = res.data as { status: string; error: string | null };
    if (job.status === "completed") return;
    if (job.status === "failed") throw new Error(job.error || "Eli generation failed");
  }
  throw new Error("Eli generation timed out");
}

/** Open a URL in the system browser (Electron shell) or a new tab (dev). */
export function openInBrowser(url: string): void {
  if (window.api?.openExternal) {
    window.api.openExternal(url);
  } else {
    window.open(url, "_blank");
  }
}

/** Reveal a file or folder in Finder/Explorer (Electron only, no-op in browser). */
export function showInFolder(fullPath: string): void {
  if (window.api?.showItemInFolder) {
    window.api.showItemInFolder(fullPath);
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

/** Start generating body micro-variants for all character frames. */
export async function generateCharacterVariants(): Promise<{ job_id: string }> {
  const res = await api.post("/api/character/generate-variants");
  return res.data as { job_id: string };
}

/** Start reprocessing character frames with green backgrounds. */
export async function reprocessCharacterBackgrounds(): Promise<{ job_id: string }> {
  const res = await api.post("/api/character/reprocess-backgrounds");
  return res.data as { job_id: string };
}

/** Start generating thumbnail expression frames. */
export async function generateThumbnailFrames(): Promise<{ job_id: string }> {
  const res = await api.post("/api/character/generate-thumbnail-frames");
  return res.data as { job_id: string };
}

/** Regenerate a single thumbnail expression frame. */
export async function regenerateThumbnailFrame(frameId: string) {
  return api.post("/api/character/regenerate-thumbnail-frame", { frame_id: frameId });
}

// Thumbnail reference management
export async function getThumbnailReferences(): Promise<{
  references: { filename: string; url: string }[];
}> {
  const res = await api.get("/api/character/thumbnail-references");
  return res.data as { references: { filename: string; url: string }[] };
}

export async function uploadThumbnailReference(file: File): Promise<{ filename: string; url: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const baseUrl = `http://localhost:${BACKEND_PORT}`;
  const response = await fetch(`${baseUrl}/api/character/thumbnail-references`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Thumbnail reference upload failed");
  }

  return response.json();
}

export async function deleteThumbnailReference(filename: string): Promise<{ deleted: string }> {
  const res = await api.delete(`/api/character/thumbnail-references/${encodeURIComponent(filename)}`);
  return res.data as { deleted: string };
}

export interface ExportTestOptions {
  regen_images: boolean;
  regen_audio: boolean;
  regen_fx: boolean;
  regen_eli: boolean;
}

/** Start export test pipeline with selective regeneration for scene 1 only. */
export async function exportTest(scriptId: string, options: ExportTestOptions): Promise<{ job_id: string }> {
  const res = await api.post("/api/render/export-test", { script_id: scriptId, ...options });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Export test failed");
  return res.data as { job_id: string };
}

// ---------------------------------------------------------------------------
// Trending topics
// ---------------------------------------------------------------------------

import type { TrendingTopic, TrendingRefreshStatus, ContentProfile, SmartIdeasResponse } from "./types/trending";
import type { HookScore } from "./types/script";
import type { PostIt } from "./types/postit";
import type { BrainstormResponse } from "./types/brainstorm";

/** Score the first ~30 seconds of a script for viewer retention via Claude. */
export async function scoreHook(scriptId: string): Promise<HookScore> {
  const res = await api.post(`/api/scripts/${scriptId}/hook-score`);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Hook scoring failed");
  return (res.data as { hook_score: HookScore }).hook_score;
}

/** Start a background job to refine the hook for a cold open variant. */
export async function refineHook(body: {
  topic: string;
  description: string;
  cold_open_index: number;
  cold_open_job_id: string;
}): Promise<{ job_id: string }> {
  const res = await api.post("/api/scripts/refine-hook", body);
  if (!res.ok)
    throw new Error(
      (res.data as { detail?: string }).detail || "Hook refinement failed",
    );
  return res.data as { job_id: string };
}

/** Start a background trending topic refresh job. */
export async function refreshTrending(): Promise<{ job_id: string }> {
  const res = await api.post("/api/trending/refresh");
  return res.data as { job_id: string };
}

/** Get status of a trending refresh job. */
export async function getTrendingRefreshStatus(jobId: string): Promise<TrendingRefreshStatus | null> {
  const res = await api.get(`/api/trending/refresh-status/${jobId}`);
  if (!res.ok) return null;
  return res.data as TrendingRefreshStatus;
}

/** Get trending topics, optionally filtered by status. */
export async function getTrendingTopics(status?: string): Promise<TrendingTopic[]> {
  const query = status ? `?status=${status}` : "";
  const res = await api.get(`/api/trending/topics${query}`);
  return (res.ok ? res.data : []) as TrendingTopic[];
}

/** Update a topic's status (dismiss or mark as used). */
export async function updateTopicStatus(id: string, status: "dismissed" | "used"): Promise<void> {
  await api.request("PATCH", `/api/trending/topics/${id}/status`, { status });
}

/** Generate video ideas from a trending topic. */
export async function generateIdeasFromTopic(topicId: string): Promise<{ ideas: Array<{ title: string; segments_est: number; description: string; keywords: string[] }>; niche: string }> {
  const res = await api.post("/api/trending/generate-ideas", { topic_id: topicId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to generate ideas");
  return res.data as { ideas: Array<{ title: string; segments_est: number; description: string; keywords: string[] }>; niche: string };
}

/** Get cached content profile (fast, no Claude call). */
export async function getContentProfile(): Promise<ContentProfile | null> {
  const res = await api.get("/api/trending/content-profile");
  if (!res.ok || !res.data) return null;
  return res.data as ContentProfile;
}

/** Force-regenerate content profile via Claude. */
export async function refreshContentProfile(): Promise<ContentProfile> {
  const res = await api.post("/api/trending/content-profile/refresh");
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to refresh profile");
  return res.data as ContentProfile;
}

/** Generate smart ideas combining profile + trending. */
export async function generateSmartIdeas(count: number = 10): Promise<SmartIdeasResponse> {
  const res = await api.post("/api/trending/smart-ideas", { count });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to generate smart ideas");
  return res.data as SmartIdeasResponse;
}

// ---------------------------------------------------------------------------
// Post-Its
// ---------------------------------------------------------------------------

export async function getPostIts(): Promise<PostIt[]> {
  const res = await api.get("/api/postits");
  return (res.ok ? res.data : []) as PostIt[];
}

export async function createPostIt(text: string, rank?: number): Promise<PostIt> {
  const res = await api.post("/api/postits", { text, rank: rank ?? 50 });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to create post-it");
  return res.data as PostIt;
}

export async function updatePostIt(id: string, updates: { text?: string; rank?: number }): Promise<PostIt> {
  const res = await api.put(`/api/postits/${id}`, updates);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to update post-it");
  return res.data as PostIt;
}

export async function deletePostIt(id: string): Promise<void> {
  await api.delete(`/api/postits/${id}`);
}

// ---------------------------------------------------------------------------
// Brainstorm
// ---------------------------------------------------------------------------

export async function generateBrainstormRecommendations(): Promise<BrainstormResponse> {
  const res = await api.post("/api/brainstorm/generate");
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to generate brainstorm recommendations");
  return res.data as BrainstormResponse;
}
