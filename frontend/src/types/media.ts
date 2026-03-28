export interface FetchMediaRequest {
  script_id: string;
  scene_id: string;
  media_type: string;
  search_query: string;
  duration?: number;
  force?: boolean;
}

export interface FetchMediaResponse {
  scene_id: string;
  video_clip_url?: string;
  image_url?: string;
}

export interface BatchFetchScene {
  scene_id: string;
  media_type: string;
  search_query: string;
  duration?: number;
}

export interface BatchFetchRequest {
  script_id: string;
  scenes: BatchFetchScene[];
}

export interface BatchFetchResultItem {
  scene_id: string;
  video_clip_url?: string;
  image_url?: string;
  error?: string;
}

export interface BatchFetchResponse {
  results: BatchFetchResultItem[];
}
