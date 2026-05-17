/** TypeScript interfaces for publishing API. */

export interface PlatformConnection {
  platform: string;
  platform_user_id: string;
  platform_user_name: string;
  connected: boolean;
}

export interface OAuthStatusResponse {
  youtube: PlatformConnection;
  tiktok: PlatformConnection;
  instagram: PlatformConnection;
}

export interface ConnectResponse {
  auth_url: string;
}

export interface PublishRecord {
  id: string;
  script_id: string;
  brand_id: string;
  platform: string;
  status: "pending" | "uploading" | "scheduled" | "published" | "failed" | "not_uploaded";
  platform_content_id: string;
  platform_url: string;
  asset_kind: "long_form" | "short_form";
  short_index?: number | null;
  upload_batch_id: string;
  file_path: string;
  schedule_at?: string;
  published_at?: string;
  error: string;
  created_at: string;
}

export interface ShortUploadPlatformStatus {
  platform: string;
  status: "pending" | "uploading" | "scheduled" | "published" | "failed" | "not_uploaded";
  platform_url: string;
  error: string;
  published_at?: string | null;
}

export interface ShortUploadStatus {
  short_index: number;
  platforms: Record<string, ShortUploadPlatformStatus>;
}
