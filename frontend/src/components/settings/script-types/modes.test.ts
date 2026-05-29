import { describe, expect, it } from "vitest";
import type { VideoFormat } from "../../../types/format";
import { allVisualModes, modeChipsForFormat } from "./modes";

function fmt(id: string, modes: string[]): VideoFormat {
  return {
    id,
    display_name: id,
    short_description: "",
    level_count_min: 1,
    level_count_max: 1,
    level_label: "segment",
    supports_cold_open: true,
    supports_hook_scoring: true,
    supports_segmented_generation: true,
    title_card_strategy_kind: "composite-grid",
    supported_visual_modes: modes,
    allowed_visual_beats: [],
    max_consecutive_same_beat: 3,
    target_distribution: {},
    reference_notes: [],
  };
}

describe("mode chip derivation", () => {
  it("builds the ordered universe as the union across formats", () => {
    const formats = [
      fmt("a", ["full_frame", "captions"]),
      fmt("b", ["full_frame", "continuous"]),
    ];
    expect(allVisualModes(formats)).toEqual(["full_frame", "captions", "continuous"]);
  });

  it("splits supported vs disabled against the universe", () => {
    const formats = [
      fmt("listicle", ["full_frame", "captions"]),
      fmt("life", ["full_frame"]),
    ];
    const universe = allVisualModes(formats);
    const life = modeChipsForFormat(formats[1], universe);
    expect(life.supported.map((c) => c.id)).toEqual(["full_frame"]);
    expect(life.disabled.map((c) => c.id)).toEqual(["captions"]);
  });

  it("flags whether a mode has a Visual Modes detail entry", () => {
    const universe = ["full_frame", "dossier"];
    const chips = modeChipsForFormat(fmt("x", ["full_frame", "dossier"]), universe);
    const byId = Object.fromEntries(chips.supported.map((c) => [c.id, c]));
    expect(byId["full_frame"].hasDetail).toBe(true);
    expect(byId["dossier"].hasDetail).toBe(false);
    expect(byId["full_frame"].label).toBe("Full Frame");
  });
});
