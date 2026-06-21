export type BlinkReviewStatus = "unreviewed" | "enabled" | "disabled" | "rejected";

export interface BlinkReviewCandidate {
  scene_id: string;
  scene_label: string;
  image_url: string;
  eligible: boolean;
  reason: string;
  anchor?: Record<string, unknown> | null;
  fingerprint: string;
  review_status: BlinkReviewStatus;
  enabled: boolean;
}

export interface BlinkReviewSummary {
  script_id: string;
  candidates: BlinkReviewCandidate[];
  eligible_count: number;
  unreviewed_count: number;
  enabled_count: number;
  disabled_count: number;
  complete: boolean;
  review_enabled: boolean;
}
