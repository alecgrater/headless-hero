export interface ContentModifierMeta {
  id: string;
  name: string;
  description: string;
  icon: string;
}

export interface BrandProfile {
  id: string;
  name: string;
  voice_id: string;
  content_modifiers: string;
  youtube_channel_id: string;
  created_at: string;
  updated_at: string;
}

export interface BrandProfileCreate {
  name: string;
  voice_id?: string;
  content_modifiers?: string;
  youtube_channel_id?: string;
}
