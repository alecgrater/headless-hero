export interface GenerateAudioResponse {
  audio_url: string;
  duration_seconds: number;
}

export interface VoiceInfo {
  voice_id: string;
  name: string;
  category: string;
}

export interface VoiceListResponse {
  voices: VoiceInfo[];
}

export interface LibraryVoiceInfo {
  voice_id: string;
  name: string;
  public_owner_id: string;
  accent: string;
  gender: string;
  age: string;
  description: string;
  preview_url: string;
  category: string;
  use_case: string;
}

export interface LibrarySearchResponse {
  voices: LibraryVoiceInfo[];
}
