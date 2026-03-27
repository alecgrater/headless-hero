export interface BrandProfile {
  id: string;
  name: string;
  art_style: string;
  color_palette: string;
  font: string;
  voice_id: string;
  youtube_channel_id: string;
  tiktok_handle: string;
  instagram_handle: string;
  created_at: string;
  updated_at: string;
}

export interface BrandProfileCreate {
  name: string;
  art_style?: string;
  color_palette?: string;
  font?: string;
  voice_id?: string;
  youtube_channel_id?: string;
  tiktok_handle?: string;
  instagram_handle?: string;
}

export type BrandProfileUpdate = Partial<BrandProfileCreate>;
