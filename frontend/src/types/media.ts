export interface FetchMediaResponse {
  scene_id: string;
  video_clip_url?: string;
  image_url?: string;
}

export interface BatchFetchResponse {
  results: { scene_id: string; video_clip_url?: string; image_url?: string; error?: string }[];
}
