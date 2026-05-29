import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import TestLabControls, { settingsWithVisualTreatmentDefaults } from "./TestLabControls";
import type { TestLabPreset, TestLabScenes, TestLabSettings } from "../../types/testLab";

const preset: TestLabPreset = {
  id: "coffee-brain",
  title: "Coffee Brain",
  description: "Preset",
  format_id: "youtube-listicle",
  segment_name: "Segment",
  narration: "Default narration.",
  visual_prompt: "Default prompt.",
  background_color: "#111111",
  visual_mode: "full_frame",
  caption_text: "",
  caption_emphasis: "",
  duration_estimate_seconds: 7,
  main_character: null,
};

const defaults: TestLabScenes["visual_treatment_defaults"] = {
  multi_frame: {
    narration: "First the warning signs were tiny, then they were everywhere.",
    visual_prompt: "[CONTRAST] Escalating warning signs.",
  },
  captions: {
    narration: "Spending big in one area can hide how far behind you are in another.",
    visual_prompt: "A receipt beside overdue bills.",
    caption_text: "Spending big while falling behind",
    caption_emphasis: "falling behind",
  },
};

const baseSettings: TestLabSettings = {
  stages: {
    audio: true,
    visual: true,
    treatment_assets: false,
    fx: true,
    render: true,
  },
  eli_enabled: false,
  style_preset_enabled: true,
  visual_mode: "full_frame",
  visual_layers: [],
  narration: "Custom narration.",
  visual_prompt: "Custom prompt.",
  segment_timer_enabled: true,
  subtitle_highlight_enabled: true,
  subtitle_style: "auto",
};

const voiceSummary = {
  voice_id: "voice-default",
  voice_name: "Headless Hero Narrator",
  model_id: "eleven_multilingual_v2",
  model_label: "Eleven v2",
  delivery_preset: "More Human",
  visible_settings: [{ label: "Delivery preset", value: "More Human" }],
};

function renderControls(settings: TestLabSettings = baseSettings) {
  return render(
    <TestLabControls
      preset={preset}
      defaultMainCharacter={null}
      visualTreatmentDefaults={defaults}
      settings={settings}
      voiceSummary={voiceSummary}
      onChange={() => undefined}
    />,
  );
}

describe("settingsWithVisualTreatmentDefaults", () => {
  it("does not inject canned caption text when switching custom narration to captions", () => {
    const settings: TestLabSettings = {
      stages: {
        audio: true,
        visual: true,
        treatment_assets: false,
        fx: true,
        render: true,
      },
      eli_enabled: false,
      style_preset_enabled: true,
      visual_mode: "captions",
      visual_layers: [],
      narration: "The tiny crack spreads across the wall until the whole room feels like it is holding its breath.",
      visual_prompt: "[CLOSE-UP] A cracked cartoon wall.",
      caption_text: undefined,
      caption_emphasis: undefined,
      segment_timer_enabled: true,
      subtitle_highlight_enabled: true,
      subtitle_style: "auto",
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "captions", defaults);

    expect(next.narration).toBe(settings.narration);
    expect(next.caption_text).toBeUndefined();
    expect(next.caption_emphasis).toBeUndefined();
  });

  it("does not replace preset narration or visual prompt when switching visual modes", () => {
    const settings: TestLabSettings = {
      stages: {
        audio: true,
        visual: true,
        treatment_assets: false,
        fx: true,
        render: true,
      },
      eli_enabled: false,
      style_preset_enabled: true,
      visual_mode: "multi_frame",
      visual_layers: [],
      narration: preset.narration,
      visual_prompt: preset.visual_prompt,
      segment_timer_enabled: true,
      subtitle_highlight_enabled: true,
      subtitle_style: "auto",
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "multi_frame", defaults);

    expect(next.narration).toBe(preset.narration);
    expect(next.tts_narration).toBeUndefined();
    expect(next.visual_prompt).toBe(preset.visual_prompt);
  });

  it("preserves subtitle style when applying visual treatment defaults", () => {
    const settings: TestLabSettings = {
      stages: {
        audio: true,
        visual: true,
        treatment_assets: false,
        fx: true,
        render: true,
      },
      eli_enabled: false,
      style_preset_enabled: true,
      visual_mode: "full_frame",
      visual_layers: [],
      subtitle_style: "burst",
      segment_timer_enabled: true,
      subtitle_highlight_enabled: true,
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "multi_frame", defaults);

    expect(next.subtitle_style).toBe("burst");
  });

  it("treats comparison board as a layered visual mode without replacing scene text", () => {
    const settings: TestLabSettings = {
      stages: {
        audio: true,
        visual: true,
        treatment_assets: true,
        fx: true,
        render: true,
      },
      eli_enabled: false,
      style_preset_enabled: true,
      visual_mode: "comparison_board",
      visual_layers: [],
      narration: "Custom human versus Neanderthal line.",
      visual_prompt: "Custom split comparison prompt.",
      segment_timer_enabled: true,
      subtitle_highlight_enabled: true,
      subtitle_style: "auto",
    };

    const next = settingsWithVisualTreatmentDefaults(
      settings,
      null,
      "comparison_board",
      {},
    );

    expect(next.narration).toBe("Custom human versus Neanderthal line.");
    expect(next.visual_prompt).toBe("Custom split comparison prompt.");
    expect(next.stages.treatment_assets).toBe(true);
  });
});

describe("TestLabControls layout", () => {
  it("renders accordion sections in the requested order", () => {
    renderControls();

    const headings = screen.getAllByRole("button", { expanded: true }).map((button) => button.textContent);

    expect(headings).toEqual([
      expect.stringContaining("Visual Mode"),
      expect.stringContaining("Character"),
      expect.stringContaining("Audio"),
      expect.stringContaining("Pipeline Stages"),
      expect.stringContaining("Miscellaneous"),
    ]);
  });

  it("collapses sections to a title row", () => {
    renderControls();

    fireEvent.click(screen.getByRole("button", { name: /Audio/i }));

    expect(screen.getByRole("button", { name: /Audio/i })).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/Headless Hero Narrator/i)).not.toBeInTheDocument();
  });

  it("keeps render-level controls out of Visual Mode and in Miscellaneous", () => {
    renderControls();

    const visualMode = screen.getByTestId("test-lab-section-visual-mode");
    expect(within(visualMode).queryByText(/Canvas color/i)).not.toBeInTheDocument();
    expect(within(visualMode).queryByText(/Subtitle style/i)).not.toBeInTheDocument();
    expect(within(visualMode).queryByText(/Segment timer/i)).not.toBeInTheDocument();

    const misc = screen.getByTestId("test-lab-section-miscellaneous");
    expect(within(misc).getByText(/Canvas color/i)).toBeInTheDocument();
    expect(within(misc).getByText(/Subtitle style/i)).toBeInTheDocument();
    expect(within(misc).getByText(/Segment timer/i)).toBeInTheDocument();
  });

  it("shows flip-flop state controls inside Visual Mode", () => {
    renderControls({ ...baseSettings, visual_mode: "flipflop" });

    const visualMode = screen.getByTestId("test-lab-section-visual-mode");
    expect(within(visualMode).getByText(/State A/i)).toBeInTheDocument();
    expect(within(visualMode).getByText(/State B/i)).toBeInTheDocument();
  });

  it("keeps the scene prompt in continuous frame prompts", () => {
    renderControls({ ...baseSettings, visual_mode: "continuous" });

    const visualMode = screen.getByTestId("test-lab-section-visual-mode");

    expect(within(visualMode).getByDisplayValue(/Opening frame.*Custom prompt/i)).toBeInTheDocument();
    expect(within(visualMode).getByDisplayValue(/Middle frame.*Custom prompt/i)).toBeInTheDocument();
    expect(within(visualMode).getByDisplayValue(/Final frame.*Custom prompt/i)).toBeInTheDocument();
  });

  it("shows read-only audio settings from Settings Voices", () => {
    renderControls();

    const audio = screen.getByTestId("test-lab-section-audio");
    expect(within(audio).getByText(/Headless Hero Narrator/i)).toBeInTheDocument();
    expect(within(audio).getByText(/Settings.*Voices/i)).toBeInTheDocument();
    expect(within(audio).queryByLabelText(/Voice ID/i)).not.toBeInTheDocument();
  });

  it("does not expose Character or editable Eli toggles in Pipeline Stages", () => {
    renderControls({ ...baseSettings, eli_enabled: true });

    const pipeline = screen.getByTestId("test-lab-section-pipeline-stages");
    expect(within(pipeline).queryByRole("button", { name: /Character/i })).not.toBeInTheDocument();
    expect(within(pipeline).queryByRole("button", { name: /^Eli$/i })).not.toBeInTheDocument();
    expect(within(pipeline).getByText(/Eli animation/i)).toBeInTheDocument();
  });

  it("does not expose layered asset generation as a pipeline option", () => {
    renderControls({ ...baseSettings, visual_mode: "flipflop" });

    const pipeline = screen.getByTestId("test-lab-section-pipeline-stages");
    expect(within(pipeline).queryByRole("button", { name: /Animation assets/i })).not.toBeInTheDocument();
    expect(within(pipeline).queryByText(/Animation assets/i)).not.toBeInTheDocument();
  });
});
