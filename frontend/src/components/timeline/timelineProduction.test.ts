import { describe, expect, it } from "vitest";

import type { ScriptContent, Scene } from "../../types/script";
import { canPrepareVisualModes, needsVisualModePrep, scenesNeedingVisualModePrep } from "./timelineProduction";

function scene(overrides: Partial<Scene> = {}): Scene {
  return {
    id: "s1",
    narration: "Narration.",
    visual_prompt: "A shot.",
    visual_mode: "full_frame",
    audio_duration_seconds: 5,
    word_timestamps: [{ word: "Narration", start_ms: 0, end_ms: 500 }],
    ...overrides,
  } as Scene;
}

function content(scenes: Scene[], overrides: Partial<ScriptContent> = {}): ScriptContent {
  return {
    title: "Test",
    segments: [{ name: "Segment", scenes }],
    ...overrides,
  } as ScriptContent;
}

describe("needsVisualModePrep", () => {
  it("is true for a script that has never been prepared", () => {
    expect(needsVisualModePrep(content([scene()]))).toBe(true);
  });

  it("is false once the whole-script analysis has been applied", () => {
    expect(needsVisualModePrep(content([scene()], { visual_modes_prepared: true }))).toBe(false);
  });

  it("stays true for a prepared script whose layered assets are still missing", () => {
    const layered = scene({ visual_mode: "popup_sequence", visual_layers: [] });
    expect(needsVisualModePrep(content([layered], { visual_modes_prepared: true }))).toBe(true);
  });

  it("does not depend on the script containing layered modes", () => {
    // The old predicate counted only layered scenes missing assets, so a script
    // with none skipped the stage and never got timing or video eligibility.
    const plain = content([scene(), scene({ id: "s2" })]);
    expect(scenesNeedingVisualModePrep(plain)).toBe(0);
    expect(needsVisualModePrep(plain)).toBe(true);
  });
});

describe("canPrepareVisualModes", () => {
  it("is true once every non-title scene has audio and word timing", () => {
    expect(canPrepareVisualModes(content([scene(), scene({ id: "s2" })]))).toBe(true);
  });

  it("is false while a scene is missing audio duration", () => {
    expect(canPrepareVisualModes(content([scene({ audio_duration_seconds: 0 })]))).toBe(false);
  });

  it("is false while a scene is missing word timing", () => {
    expect(canPrepareVisualModes(content([scene({ word_timestamps: [] })]))).toBe(false);
  });

  it("ignores title cards, which carry no analysed timing", () => {
    const titleCard = scene({ id: "t1", is_title_card: true, audio_duration_seconds: 0, word_timestamps: [] });
    expect(canPrepareVisualModes(content([titleCard, scene()]))).toBe(true);
  });

  it("is false for a script with no non-title scenes", () => {
    expect(canPrepareVisualModes(content([scene({ is_title_card: true })]))).toBe(false);
  });
});
