import { showToast } from "./components/ToastContainer";
import { BACKEND_PORT } from "./constants";
import type { UploadTracking } from "./types/script";

export interface ApiResponse<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
}

interface ApiClient {
  get: <T = unknown>(path: string) => Promise<ApiResponse<T>>;
  post: <T = unknown>(path: string, body?: unknown) => Promise<ApiResponse<T>>;
  put: <T = unknown>(path: string, body?: unknown) => Promise<ApiResponse<T>>;
  delete: <T = unknown>(path: string) => Promise<ApiResponse<T>>;
  request: <T = unknown>(method: string, path: string, body?: unknown) => Promise<ApiResponse<T>>;
  openExternal?: (url: string) => Promise<void>;
  openUploadShortsWindows?: () => Promise<void>;
  openYouTubeUploadWindow?: () => Promise<void>;
  downloadFile?: (url: string, defaultFilename: string) => Promise<{ canceled: boolean; filePath?: string }>;
  saveToDownloads?: (url: string, folderName: string, filename: string) => Promise<{ filePath: string }>;
  selectFolder?: (title?: string, defaultPath?: string) => Promise<{ canceled: boolean; path?: string }>;
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
    if (typeof d.error === "string") return d.error;
  }
  if (status === 404) return "Resource not found";
  if (status === 422) return "Invalid request data";
  if (status >= 500) return "Server error — please try again";
  return `Request failed (${status})`;
}

/** Paths that should not trigger toast notifications on error. */
const SILENT_PATHS = ["/api/health", "/api/render/status/", "/api/publish/status/", "/api/publish/short-form/status/", "/api/visuals/title-cards-status/", "/api/character/status/", "/api/scripts/generate-status/", "/api/scripts/cold-opens-status/", "/api/scripts/refine-hook-status/", "/api/trending/refresh-status/", "/api/trending/smart-ideas-status/", "/api/eli/generate-status/", "/api/fx/generate-status/", "/api/media/analyze/status/", "/api/idea-board/", "/api/recording/session/", "/api/recording/score-status/", "/api/short-form/jobs/", "/api/short-form/rendered"];

function shouldSilence(path: string): boolean {
  return SILENT_PATHS.some((p) => path.startsWith(p));
}

/** Wrap a request method to intercept non-ok responses and show toasts. */
function withErrorInterceptor(
  requestFn: <T = unknown>(method: string, path: string, body?: unknown) => Promise<ApiResponse<T>>,
): <T = unknown>(method: string, path: string, body?: unknown) => Promise<ApiResponse<T>> {
  return async <T = unknown>(method: string, path: string, body?: unknown) => {
    try {
      const res = await requestFn<T>(method, path, body);
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
      return { ok: false, status: 0, data: {} as T };
    }
  };
}

// In Electron, window.api is injected by preload.js
// For dev without Electron, fall back to direct fetch
const rawApi: ApiClient = window.api ?? {
  request: async (method: string, path: string, body?: unknown) => {
    const isFormData = body instanceof FormData;
    const options: RequestInit = {
      method,
      headers: isFormData ? {} : { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(20 * 60 * 1000), // 20 minutes — segmented script gen can take 7+min
    };
    if (body && method !== "GET") {
      options.body = isFormData ? body : JSON.stringify(body);
    }
    const response = await fetch(`http://localhost:${BACKEND_PORT}${path}`, options);
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text || `HTTP ${response.status}` };
    }
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
  openUploadShortsWindows: rawApi.openUploadShortsWindows,
  openYouTubeUploadWindow: rawApi.openYouTubeUploadWindow,
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

/** Upload a recording take via direct fetch (bypasses IPC for FormData). */
export async function uploadRecordingTake(
  scriptId: string,
  sceneId: string,
  takeNumber: number,
  audioBlob: Blob,
): Promise<{ filename: string; duration_seconds: number }> {
  const formData = new FormData();
  formData.append("script_id", scriptId);
  formData.append("scene_id", sceneId);
  formData.append("take_number", String(takeNumber));
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`http://localhost:${BACKEND_PORT}/api/recording/upload-take`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Take upload failed");
  }
  return response.json();
}

/** Import an external audio file as a recording take via direct fetch. */
export async function importRecordingTake(
  scriptId: string,
  sceneId: string,
  file: File,
): Promise<{ filename: string; take_number: number; duration_seconds: number }> {
  const formData = new FormData();
  formData.append("script_id", scriptId);
  formData.append("scene_id", sceneId);
  formData.append("audio", file);

  const response = await fetch(`http://localhost:${BACKEND_PORT}/api/recording/import-take`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Import failed" }));
    throw new Error(err.detail || "Take import failed");
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
  sceneCount?: number,
): Promise<{ average_seconds: number | null; sample_count: number }> {
  let url = `/api/generation/estimate?operation_type=${operationType}`;
  if (sceneCount != null) url += `&scene_count=${sceneCount}`;
  const res = await api.get(url);
  if (res.ok) {
    const data = res.data as { average_seconds: number | null; sample_count: number };
    return data;
  }
  return { average_seconds: null, sample_count: 0 };
}

/** Record a generation duration from the frontend. */
export async function recordDuration(
  operationType: string,
  durationSeconds: number,
  sceneCount?: number,
): Promise<void> {
  await api.post("/api/generation/record-duration", {
    operation_type: operationType,
    duration_seconds: durationSeconds,
    scene_count: sceneCount ?? null,
  });
}

export interface ScriptCostBreakdownItem {
  task: string;
  service: string;
  operation: string;
  model: string;
  call_count: number;
  input_tokens: number;
  output_tokens: number;
  characters: number;
  images: number;
  total_cost: number;
}

export interface ScriptCostResponse {
  total_cost: number;
  breakdown: ScriptCostBreakdownItem[];
}

/** Fetch the total estimated cost for a script. */
export async function fetchScriptCost(scriptId: string): Promise<ScriptCostResponse> {
  const res = await api.get(`/api/scripts/${scriptId}/cost`);
  if (res.ok) {
    const data = res.data as Partial<ScriptCostResponse>;
    return {
      total_cost: data.total_cost ?? 0,
      breakdown: data.breakdown ?? [],
    };
  }
  return { total_cost: 0, breakdown: [] };
}

/** Generate FX assignments for all scenes in a script via the routed LLM provider. */
export async function generateFX(scriptId: string, missingOnly = false) {
  return api.post("/api/fx/generate", { script_id: scriptId, missing_only: missingOnly });
}

/** Regenerate FX for a single scene via the routed LLM provider. */
export async function regenerateFX(scriptId: string, sceneId: string) {
  return api.post("/api/fx/regenerate", { script_id: scriptId, scene_id: sceneId });
}

/** Generate Eli pose selection for all scenes in a script via the routed LLM provider. */
export async function generateEli(scriptId: string, missingOnly = false) {
  return api.post("/api/eli/generate", { script_id: scriptId, missing_only: missingOnly });
}

/** Regenerate Eli pose for a single scene via the routed LLM provider. */
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

const POLL_INTERVAL_MS = 1500;

type BackgroundJobProgress = {
  progress?: number;
  current_step?: string | null;
};

async function pollBackgroundJob(
  jobId: string,
  statusEndpoint: string,
  stallPolls: number,
  failureMessage: string,
  onProgress?: (status: BackgroundJobProgress) => void,
): Promise<void> {
  // Poll until completion. Time out only if the job's progress field stops
  // advancing for `stallPolls` consecutive polls — large scripts (e.g. 200+
  // Eli scenes) can legitimately exceed any fixed total-time budget. Tolerate
  // up to MAX_TRANSIENT_ERRORS consecutive non-404 status failures (network
  // blips, 5xx) before giving up; treat 404 as terminal "job not found".
  const MAX_TRANSIENT_ERRORS = 3;
  let lastProgress = -1;
  let stallCount = 0;
  let transientErrors = 0;
  for (;;) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    const res = await api.get(`${statusEndpoint}${jobId}`);
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`${failureMessage} (job not found)`);
      }
      transientErrors += 1;
      if (transientErrors > MAX_TRANSIENT_ERRORS) {
        throw new Error("Failed to check job status");
      }
      continue;
    }
    transientErrors = 0;
    const job = res.data as { status: string; error: string | null; progress?: number; current_step?: string | null };
    if (onProgress) onProgress({ progress: job.progress, current_step: job.current_step });
    if (job.status === "completed") return;
    if (job.status === "failed") throw new Error(job.error || failureMessage);
    if (job.status === "cancelled") throw new Error(`${failureMessage} (cancelled)`);

    const currentProgress = job.progress ?? 0;
    if (currentProgress > lastProgress) {
      lastProgress = currentProgress;
      stallCount = 0;
    } else if (++stallCount >= stallPolls) {
      const stallSeconds = Math.round((stallPolls * POLL_INTERVAL_MS) / 1000);
      throw new Error(`${failureMessage} (no progress for ${stallSeconds}s)`);
    }
  }
}

/** Poll a title card background job until it completes or fails. */
export async function pollTitleCardJob(
  jobId: string,
  onProgress?: (status: BackgroundJobProgress) => void,
): Promise<void> {
  return pollBackgroundJob(jobId, "/api/visuals/title-cards-status/", 200, "Title card generation failed", onProgress);
}

/** Poll a render job until it completes or fails. */
export async function pollRenderJob(jobId: string): Promise<void> {
  return pollBackgroundJob(jobId, "/api/render/status/", 600, "Render failed");
}

/** Poll a short-form background job until it completes or fails. */
export async function pollShortFormJob(
  jobId: string,
  onProgress?: (status: BackgroundJobProgress) => void,
): Promise<void> {
  return pollBackgroundJob(jobId, "/api/short-form/jobs/", 1200, "Short-form job failed", onProgress);
}

/** Poll an Eli generation background job until it completes or fails. */
export async function pollEliJob(
  jobId: string,
  onProgress?: (status: BackgroundJobProgress) => void,
): Promise<void> {
  return pollBackgroundJob(jobId, "/api/eli/generate-status/", 800, "Eli generation failed", onProgress);
}

/** Poll an FX generation background job until it completes or fails. */
export async function pollFXJob(
  jobId: string,
  onProgress?: (status: BackgroundJobProgress) => void,
): Promise<void> {
  return pollBackgroundJob(jobId, "/api/fx/generate-status/", 800, "FX generation failed", onProgress);
}

/** Open a URL in Chrome via Electron, or a new tab in browser-only dev mode. */
export function openInBrowser(url: string): void {
  if (window.api?.openExternal) {
    window.api.openExternal(url).catch((err) => {
      showToast(err instanceof Error ? err.message : "Failed to open link in Chrome");
    });
  } else {
    window.open(url, "_blank");
  }
}

export const YOUTUBE_STUDIO_URL = "https://studio.youtube.com/";
export const YOUTUBE_STUDIO_UPLOAD_URL = "https://studio.youtube.com/channel/UCBLhENZIlxFAQ59owrMSauw/videos/upload?d=ud&filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D";
export const TIKTOK_STUDIO_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=webapp&lang=en&tab=video";
export const INSTAGRAM_URL = "https://www.instagram.com/";

const UPLOAD_SHORTS_URLS = [
  "https://www.instagram.com/watchunranked/",
  "https://www.tiktok.com/tiktokstudio",
  YOUTUBE_STUDIO_UPLOAD_URL,
];

/** Open short-form upload destinations in Chrome windows when Electron is available. */
export function openUploadShortsWindows(): void {
  if (window.api?.openUploadShortsWindows) {
    window.api.openUploadShortsWindows().catch((err) => {
      showToast(err instanceof Error ? err.message : "Failed to open upload windows in Chrome");
    });
    return;
  }

  for (const url of UPLOAD_SHORTS_URLS) {
    window.open(url, "_blank");
  }
}

/** Open the long-form YouTube Studio upload page in a positioned Chrome window. */
export function openYouTubeUploadWindow(): void {
  if (window.api?.openYouTubeUploadWindow) {
    window.api.openYouTubeUploadWindow().catch((err) => {
      showToast(err instanceof Error ? err.message : "Failed to open YouTube Studio in Chrome");
    });
    return;
  }

  window.open(YOUTUBE_STUDIO_UPLOAD_URL, "_blank", "noopener,noreferrer,width=684,height=1203");
}

/** Reveal a file or folder in Finder/Explorer (Electron only, no-op in browser). */
export function showInFolder(fullPath: string): void {
  if (window.api?.showItemInFolder) {
    window.api.showItemInFolder(fullPath);
  }
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

import type { TrendingTopic, TrendingRefreshStatus, ContentProfile } from "./types/trending";
import type { HookScore } from "./types/script";
import type { Idea, IdeaSource, IdeaStatus } from "./types/idea";


/** Score the first ~30 seconds of a script for viewer retention via the routed LLM provider. */
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

/** Get cached content profile (fast, no LLM call). */
export async function getContentProfile(): Promise<ContentProfile | null> {
  const res = await api.get("/api/trending/content-profile");
  if (!res.ok || !res.data) return null;
  return res.data as ContentProfile;
}

/** Force-regenerate content profile via the routed LLM provider. */
export async function refreshContentProfile(): Promise<ContentProfile> {
  const res = await api.post("/api/trending/content-profile/refresh");
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to refresh profile");
  return res.data as ContentProfile;
}

/** Start smart ideas generation (background job). Returns job_id + trending metadata. */
export async function generateSmartIdeas(count: number = 40): Promise<{
  job_id: string;
  refresh_triggered: boolean;
  refresh_job_id: string | null;
  trending_age_hours: number | null;
}> {
  const res = await api.post("/api/trending/smart-ideas", { count });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start idea generation");
  return res.data as {
    job_id: string;
    refresh_triggered: boolean;
    refresh_job_id: string | null;
    trending_age_hours: number | null;
  };
}

/** Poll smart ideas generation job status. */
export async function getSmartIdeasStatus(jobId: string): Promise<{
  status: string;
  progress: number;
  current_step: string;
  output_data: string | null;
  error: string | null;
} | null> {
  const res = await api.get(`/api/trending/smart-ideas-status/${jobId}`);
  if (!res.ok) return null;
  return res.data as {
    status: string;
    progress: number;
    current_step: string;
    output_data: string | null;
    error: string | null;
  };
}

// ---------------------------------------------------------------------------
// Ideas (idea board)
// ---------------------------------------------------------------------------

export async function getIdeas(sort?: string, category?: string, status?: string): Promise<Idea[]> {
  const params = new URLSearchParams();
  if (sort) params.set("sort", sort);
  if (category) params.set("category", category);
  if (status) params.set("status", status);
  const query = params.toString();
  const res = await api.get(`/api/idea-board${query ? `?${query}` : ""}`);
  return (res.ok ? res.data : []) as Idea[];
}

export async function createIdea(text: string, rank?: number, source?: IdeaSource, description?: string, category?: string): Promise<Idea> {
  const body: Record<string, unknown> = { text, rank: rank ?? 50, source: source ?? "manual" };
  if (description) body.description = description;
  if (category) body.category = category;
  const res = await api.post("/api/idea-board", body);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to create idea");
  return res.data as Idea;
}

export async function updateIdea(id: string, updates: { text?: string; rank?: number; status?: IdeaStatus; description?: string; category?: string }): Promise<Idea> {
  const res = await api.put(`/api/idea-board/${id}`, updates);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to update idea");
  return res.data as Idea;
}

export async function deleteIdea(id: string): Promise<void> {
  await api.delete(`/api/idea-board/${id}`);
}

export async function getIdeaCounts(): Promise<Record<string, number>> {
  const res = await api.get("/api/idea-board/counts");
  if (!res.ok) return { idea: 0, in_progress: 0, scripted: 0, published: 0 };
  return res.data as Record<string, number>;
}

export async function getIdeaColdOpenStatus(id: string): Promise<Record<string, unknown>> {
  const res = await api.get(`/api/idea-board/${id}/cold-open-status`);
  if (!res.ok) throw new Error("Failed to check cold open status");
  return res.data as Record<string, unknown>;
}

export async function selectIdeaColdOpen(id: string, index: number): Promise<{ job_id: string }> {
  const res = await api.post(`/api/idea-board/${id}/select-cold-open`, { index });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to select cold open");
  return res.data as { job_id: string };
}

export async function retryIdeaColdOpen(id: string): Promise<{ job_id: string }> {
  const res = await api.post(`/api/idea-board/${id}/retry-cold-open`);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to retry cold open");
  return res.data as { job_id: string };
}

export async function getIdeaCategories(): Promise<string[]> {
  const res = await api.get("/api/idea-board/categories");
  return (res.ok ? res.data : []) as string[];
}

// ---------------------------------------------------------------------------
// Catalog
// ---------------------------------------------------------------------------

export interface CatalogEntry {
  folder_name: string;
  folder_path: string;
  video_file: string | null;
  thumbnail_file: string | null;
  seo_title: string | null;
  seo_description: string | null;
  seo_tags: string[];
  exported_at: string;
  file_size_mb: number;
  uploaded: boolean;
  youtube_url: string | null;
  script_id: string | null;
}

export async function fetchCatalog(): Promise<CatalogEntry[]> {
  const res = await api.get("/api/catalog");
  if (!res.ok) return [];
  return (res.data as { entries: CatalogEntry[] }).entries;
}

export async function toggleUploaded(folderName: string): Promise<{ uploaded: boolean }> {
  const res = await api.post(`/api/catalog/${encodeURIComponent(folderName)}/toggle-uploaded`);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to toggle uploaded status");
  return res.data as { uploaded: boolean };
}

export interface CatalogUploadOptions {
  folder_name: string;
  title?: string;
  description?: string;
  tags?: string[];
  privacy_status?: string;
}

export async function catalogUpload(options: CatalogUploadOptions): Promise<{ job_id: string }> {
  const res = await api.post("/api/catalog/upload", options);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Upload failed");
  return res.data as { job_id: string };
}

export async function uploadLongformYouTube(
  scriptId: string,
  privacyStatus: "private" | "unlisted" | "public" = "unlisted",
): Promise<{ job_id: string }> {
  const res = await api.post("/api/publish/youtube-longform/upload", {
    script_id: scriptId,
    privacy_status: privacyStatus,
  });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Upload failed");
  return res.data as { job_id: string };
}

export async function syncCatalogYouTube(): Promise<{ matched: number }> {
  const res = await api.post("/api/catalog/sync-youtube");
  if (!res.ok) return { matched: 0 };
  return res.data as { matched: number };
}

export interface YouTubeOAuthStatus {
  youtube: {
    connected: boolean;
    platform_user_name: string;
    platform_user_id: string;
  };
}

export async function getYouTubeOAuthStatus(): Promise<YouTubeOAuthStatus> {
  const res = await api.get("/api/publish/oauth/status");
  if (!res.ok) return { youtube: { connected: false, platform_user_name: "", platform_user_id: "" } };
  return res.data as YouTubeOAuthStatus;
}

export interface PublishJobStatus {
  job_id: string;
  status: string;
  progress: number;
  current_step: string;
  output_urls: string[];
  error: string | null;
}

export async function getPublishStatus(jobId: string): Promise<PublishJobStatus | null> {
  const res = await api.get(`/api/publish/status/${jobId}`);
  if (!res.ok) return null;
  return res.data as PublishJobStatus;
}

export async function uploadSceneMedia(
  scriptId: string,
  sceneId: string,
  file: File,
): Promise<{ url: string; media_type: string }> {
  const formData = new FormData();
  formData.append("script_id", scriptId);
  formData.append("scene_id", sceneId);
  formData.append("file", file);

  const baseUrl = `http://localhost:${BACKEND_PORT}`;
  const response = await fetch(`${baseUrl}/api/media/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Media upload failed");
  }

  return response.json();
}

export interface MediaAssignment {
  scene_id: string;
  media_source: "ai" | "gameplay_video" | "stock_photo";
  game_name: string | null;
  search_query: string | null;
  reasoning: string;
}

export interface MediaAnalysisStatus {
  status: string;
  progress: number;
  error: string | null;
  assignments?: MediaAssignment[];
  summary?: Record<string, number>;
}

export async function analyzeMedia(scriptId: string) {
  return api.post(`/api/media/analyze/${scriptId}`);
}

export async function getMediaAnalysisStatus(jobId: string) {
  return api.get(`/api/media/analyze/status/${jobId}`);
}

export async function applyMediaAssignments(
  scriptId: string,
  assignments: MediaAssignment[],
) {
  return api.post<{ ok: boolean }>(`/api/media/apply/${scriptId}`, { assignments });
}

/** Start a single-scene preview render via Remotion. */
export async function renderScenePreview(scriptId: string, sceneId: string): Promise<{ job_id: string }> {
  const res = await api.post("/api/render/preview-scene", { script_id: scriptId, scene_id: sceneId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Scene preview render failed");
  return res.data as { job_id: string };
}

// ---------------------------------------------------------------------------
// Short-form export
// ---------------------------------------------------------------------------

import type { ShortFormJobStatus } from "./types/render";
import type { ShortUploadStatus } from "./types/publish";

export interface RenderedShortsStatus {
  rendered_indices: number[];
  paths: Record<number, string>;
}

export interface RenderedLongformStatus {
  rendered: boolean;
  path?: string | null;
  url?: string | null;
}

export interface ShortFormThumbnailsStatus {
  generated_indices: number[];
  paths: Record<number, string>;
}

export interface ExportShortFormThumbnailsResponse {
  folder_path: string;
  files: string[];
  paths: Record<number, string>;
}

/** Check which short-form clips exist in the final Downloads destination folder. */
export async function getRenderedShortsStatus(scriptId: string): Promise<RenderedShortsStatus> {
  const res = await api.get(`/api/short-form/rendered?script_id=${encodeURIComponent(scriptId)}`);
  if (!res.ok) throw new Error(`Failed to fetch rendered shorts: ${res.status}`);
  return res.data as RenderedShortsStatus;
}

/** Check whether a long-form YouTube render exists in the project cache or export folder. */
export async function getRenderedLongformStatus(scriptId: string): Promise<RenderedLongformStatus> {
  const res = await api.get(`/api/render/rendered-longform?script_id=${encodeURIComponent(scriptId)}`);
  if (!res.ok) throw new Error(`Failed to fetch rendered long-form video: ${res.status}`);
  return res.data as RenderedLongformStatus;
}

/** Start background render of all short-form clips. */
export async function renderShortAll(scriptId: string): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/render/all", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start render-all");
  return res.data as { job_id: string };
}

/** Start background render of selected short-form clips. */
export async function renderShortBatch(
  scriptId: string,
  segmentIndices: number[],
): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/render/batch", {
    script_id: scriptId,
    segment_indices: segmentIndices,
  });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start render-batch");
  return res.data as { job_id: string };
}

/** Start background render of a single short-form clip. */
export async function renderShortOne(
  scriptId: string,
  segmentIdx: number,
): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/render/one", { script_id: scriptId, segment_idx: segmentIdx });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start render-one");
  return res.data as { job_id: string };
}

/** Poll a short-form background job for its current status. */
export async function getShortFormJobStatus(jobId: string): Promise<ShortFormJobStatus> {
  const res = await api.get(`/api/short-form/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch job status: ${res.status}`);
  return res.data as ShortFormJobStatus;
}

/** Check which short-form thumbnails already exist in the project render folder. */
export async function getShortFormThumbnailsStatus(scriptId: string): Promise<ShortFormThumbnailsStatus> {
  const res = await api.get(`/api/short-form/thumbnails?script_id=${encodeURIComponent(scriptId)}`);
  if (!res.ok) throw new Error(`Failed to fetch short-form thumbnails: ${res.status}`);
  return res.data as ShortFormThumbnailsStatus;
}

/** Start background generation of all short-form thumbnails. */
export async function generateShortFormThumbnailsAll(scriptId: string): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/thumbnails/all", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start thumbnail generation");
  return res.data as { job_id: string };
}

/** Start background generation of selected short-form thumbnails. */
export async function generateShortFormThumbnailsBatch(
  scriptId: string,
  segmentIndices: number[],
): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/thumbnails/batch", {
    script_id: scriptId,
    segment_indices: segmentIndices,
  });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start thumbnail batch");
  return res.data as { job_id: string };
}

/** Start background generation of one short-form thumbnail. */
export async function generateShortFormThumbnailOne(
  scriptId: string,
  segmentIdx: number,
): Promise<{ job_id: string }> {
  const res = await api.post("/api/short-form/thumbnails/one", { script_id: scriptId, segment_idx: segmentIdx });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start thumbnail generation");
  return res.data as { job_id: string };
}

/** Generate missing short-form thumbnails and export them to the configured export folder. */
export async function exportShortFormThumbnails(scriptId: string): Promise<ExportShortFormThumbnailsResponse> {
  const res = await api.post("/api/short-form/thumbnails/export", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to export thumbnails");
  return res.data as ExportShortFormThumbnailsResponse;
}

export interface ExportSEOResponse {
  folder_path: string;
  files: string[];
}

/** Write the long-form SEO markdown file into the project's Downloads folder. */
export async function exportLongFormSEO(scriptId: string): Promise<ExportSEOResponse> {
  const res = await api.post("/api/seo/export-longform", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to export long-form SEO");
  return res.data as ExportSEOResponse;
}

/** Write all short-form SEO markdown files into the project's Downloads folder. */
export async function exportShortFormSEO(scriptId: string): Promise<ExportSEOResponse> {
  const res = await api.post("/api/seo/export-shorts", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to export short-form SEO");
  return res.data as ExportSEOResponse;
}

export interface ExportLongFormThumbnailResponse {
  folder_path: string;
  file: string;
}

/** Copy the composite long-form thumbnail PNG into the project's Downloads folder. */
export async function exportLongFormThumbnail(scriptId: string): Promise<ExportLongFormThumbnailResponse> {
  const res = await api.post("/api/render/export-thumbnail", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to export thumbnail");
  return res.data as ExportLongFormThumbnailResponse;
}

export interface ExportShortFormVideosResponse {
  folder_path: string;
  files: string[];
  paths: Record<number, string>;
}

export interface UploadSuiteShort {
  index: number;
  segment_name: string;
  video_path: string | null;
  seo_markdown: string;
  thumbnail_url: string | null;
}

export interface UploadSuiteStatus {
  ready: boolean;
  project_title: string;
  folder_path: string;
  missing: string[];
  longform_video_path: string | null;
  longform_seo_markdown: string;
  shorts: UploadSuiteShort[];
}

/** Fetch the exported upload suite metadata used by the manual upload modal. */
export async function getUploadSuiteStatus(scriptId: string): Promise<UploadSuiteStatus> {
  const res = await api.get(`/api/upload-suite/status?script_id=${encodeURIComponent(scriptId)}`);
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to check upload suite");
  return res.data as UploadSuiteStatus;
}

/** Copy all rendered short-form videos into the project's Downloads folder. */
export async function exportShortFormVideos(scriptId: string): Promise<ExportShortFormVideosResponse> {
  const res = await api.post("/api/short-form/render/export", { script_id: scriptId });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to export short-form videos");
  return res.data as ExportShortFormVideosResponse;
}

/** Start one-click upload for a rendered short to connected platforms. */
export async function uploadShortForm(scriptId: string, segmentIdx: number): Promise<{ job_id: string }> {
  const res = await api.post("/api/publish/short-form/upload", {
    script_id: scriptId,
    segment_idx: segmentIdx,
  });
  if (!res.ok) throw new Error((res.data as { detail?: string }).detail || "Failed to start short upload");
  return res.data as { job_id: string };
}

/** Fetch latest per-platform upload state for all shorts in a project. */
export async function getShortFormUploadStatus(scriptId: string): Promise<Record<number, ShortUploadStatus>> {
  const res = await api.get(`/api/publish/short-form/status/${scriptId}`);
  if (!res.ok) throw new Error(`Failed to fetch short upload status: ${res.status}`);
  return res.data as Record<number, ShortUploadStatus>;
}

/** Fetch derived upload tracking for a script (auto-detected + manual overrides). */
export async function getUploadTracking(scriptId: string): Promise<UploadTracking> {
  const res = await api.get(`/api/scripts/${encodeURIComponent(scriptId)}/upload-tracking`);
  if (!res.ok) throw new Error(`Failed to fetch upload tracking: ${res.status}`);
  return res.data as UploadTracking;
}

/** Manually set one or more upload tracking flags for a script. */
export async function setUploadTracking(
  scriptId: string,
  patch: Partial<UploadTracking>,
): Promise<UploadTracking> {
  const res = await api.post(`/api/scripts/${encodeURIComponent(scriptId)}/upload-tracking`, patch);
  if (!res.ok) throw new Error(`Failed to set upload tracking: ${res.status}`);
  return res.data as UploadTracking;
}
