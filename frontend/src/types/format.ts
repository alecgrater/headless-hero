export interface VideoFormat {
  id: string;
  display_name: string;
  short_description: string;
  level_count_min: number;
  level_count_max: number;
  level_label: string;        // "segment" | "level"
  supports_cold_open: boolean;
  supports_hook_scoring: boolean;
  supports_segmented_generation: boolean;
  title_card_strategy_kind: "composite-grid" | "cinematic-chapters";
}
