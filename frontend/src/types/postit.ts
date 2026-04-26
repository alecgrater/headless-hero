export type PostItStatus = "idea" | "in_progress" | "scripted" | "published";
export type PostItSource = "manual" | "for_you" | "trending";

export interface PostIt {
  id: string;
  text: string;
  rank: number;
  status: PostItStatus;
  source: PostItSource;
  created_at: string;
}
