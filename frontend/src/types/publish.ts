/** TypeScript interfaces for publishing API. */

export interface PlatformConnection {
  platform: string;
  platform_user_id: string;
  platform_user_name: string;
  connected: boolean;
}

export interface OAuthStatusResponse {
  youtube: PlatformConnection;
}

export interface ConnectResponse {
  auth_url: string;
}

export interface PublishRecord {
  id: string;
  script_id: string;
  brand_id: string;
  platform: string;
  status: "pending" | "uploading" | "scheduled" | "published" | "failed";
  platform_content_id: string;
  platform_url: string;
  schedule_at?: string;
  published_at?: string;
  error: string;
  created_at: string;
}
