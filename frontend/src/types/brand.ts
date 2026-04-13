export interface EliPosition {
  x: number;
  y: number;
}

export interface BrandProfile {
  id: string;
  name: string;
  voice_id: string;
  youtube_channel_id: string;
  eli_position: EliPosition | null;
  created_at: string;
  updated_at: string;
}
