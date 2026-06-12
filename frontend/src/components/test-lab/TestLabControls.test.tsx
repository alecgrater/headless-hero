import { describe, expect, it, vi } from "vitest";
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

const subtitleSummary = {
  coverage_label: "All scenes",
  enabled_style_labels: ["Clean", "Kinetic Cards"],
};

const blankPreset: TestLabPreset = {
  id: "blank",
  title: "Blank",
  description: "Write your own test script",
  format_id: "youtube-listicle",
  segment_name: "Custom scene",
  narration: "",
  visual_prompt: "",
  background_color: "#111111",
  visual_mode: "full_frame",
  caption_text: "",
  caption_emphasis: "",
  duration_estimate_seconds: 7,
  main_character: null,
};

function renderControls(settings: TestLabSettings = baseSettings) {
  const onOpenSettingsSection = vi.fn();
  return render(
    <TestLabControls
      preset={preset}
      defaultMainCharacter={null}
      visualTreatmentDefaults={defaults}
      settings={settings}
      voiceSummary={voiceSummary}
      subtitleSummary={subtitleSummary}
      onChange={() => undefined}
      onOpenSettingsSection={onOpenSettingsSection}
    />,
  );
}

describe("settingsWithVisualTreatmentDefaults", () => {
  it("derives caption text from custom narration when switching to captions", () => {
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
      subtitle_style: "auto",
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "captions", defaults);

    expect(next.narration).toBe(settings.narration);
    expect(next.caption_text).toBe("The tiny crack spreads across the wall until the whole room feels like it is holding its breath");
    expect(next.caption_emphasis).toBe("breath");
  });

  it("rederives stale caption text after narration changes", () => {
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
      narration: "The real problem is friction.",
      visual_prompt: "[CLOSE-UP] A messy desk.",
      caption_text: "The old problem was attention",
      caption_emphasis: "attention",
      segment_timer_enabled: true,
      subtitle_style: "auto",
    };

    const next = settingsWithVisualTreatmentDefaults(settings, preset, "captions", defaults);

    expect(next.caption_text).toBe("The real problem is friction");
    expect(next.caption_emphasis).toBe("friction");
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
  it("renders blank preset scene text fields empty", () => {
    render(
      <TestLabControls
        preset={blankPreset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{
          ...baseSettings,
          visual_mode: "full_frame",
          narration: undefined,
          tts_narration: undefined,
          visual_prompt: undefined,
        }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={() => undefined}
      />,
    );

    expect(screen.getByLabelText("Narration")).toHaveValue("");
    expect(screen.getByLabelText("Visual prompt")).toHaveValue("");
  });

  it("renders accordion sections in the requested order", () => {
    renderControls();

    const headings = screen.getAllByRole("button", { expanded: true }).map((button) => button.textContent);

    expect(headings).toEqual([
      expect.stringContaining("Visual Mode"),
      expect.stringContaining("Character"),
      expect.stringContaining("Voices"),
      expect.stringContaining("Pipeline Stages"),
      expect.stringContaining("Miscellaneous"),
    ]);
  });

  it("collapses sections to a title row", () => {
    renderControls();

    fireEvent.click(screen.getByRole("button", { name: /Voices/i }));

    expect(screen.getByRole("button", { name: /Voices/i })).toHaveAttribute("aria-expanded", "false");
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
    expect(within(misc).getAllByText(/Subtitle settings/i).length).toBeGreaterThan(0);
    expect(within(misc).queryByText(/Segment timer/i)).not.toBeInTheDocument();
  });

  it("stacks subtitle setting summaries as coverage then styles", () => {
    renderControls();

    const misc = screen.getByTestId("test-lab-section-miscellaneous");
    const summaryRows = within(misc).getAllByTestId("test-lab-subtitle-summary-row").map((row) => row.textContent);

    expect(summaryRows).toEqual([
      expect.stringContaining("Coverage"),
      expect.stringContaining("Styles"),
    ]);
  });

  it("shows flip-flop state controls inside Visual Mode", () => {
    renderControls({ ...baseSettings, visual_mode: "flipflop" });

    const visualMode = screen.getByTestId("test-lab-section-visual-mode");
    fireEvent.mouseEnter(within(visualMode).getByRole("button", { name: /Flip-flop/i }));

    expect(within(visualMode).getByText(/one neutral transparent cutout and stages deterministic face overlays/i)).toBeInTheDocument();
    expect(within(visualMode).getByLabelText("Flip-flop action")).toBeInTheDocument();
    expect(within(visualMode).getByLabelText("Scene context")).toBeInTheDocument();
  });

  it("shows the flip-flop action selector only for flip-flop mode", () => {
    const { rerender } = render(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "flipflop", flipflop_action: "blink" }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={() => undefined}
        onOpenSettingsSection={() => undefined}
      />,
    );

    expect(screen.getByLabelText("Flip-flop action")).toHaveValue("blink");
    expect(screen.getByLabelText("Scene context")).toHaveValue("plain");

    rerender(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "full_frame", flipflop_action: "" }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={() => undefined}
        onOpenSettingsSection={() => undefined}
      />,
    );

    expect(screen.queryByLabelText("Flip-flop action")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Scene context")).not.toBeInTheDocument();
  });

  it("updates renderer context without rewriting scene text", () => {
    const onChange = vi.fn();
    render(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "flipflop", renderer_context: "desk" }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={onChange}
        onOpenSettingsSection={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("Scene context"), {
      target: { value: "office" },
    });

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        renderer_context: "office",
        narration: "Custom narration.",
        visual_prompt: "Custom prompt.",
      }),
    );
  });

  it("updates flip-flop action without rewriting scene text", () => {
    const onChange = vi.fn();
    render(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "flipflop", flipflop_action: "blink" }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={onChange}
        onOpenSettingsSection={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("Flip-flop action"), {
      target: { value: "eye_glance" },
    });

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        flipflop_action: "eye_glance",
        narration: "Custom narration.",
        visual_prompt: "Custom prompt.",
      }),
    );
  });

  it("leaves flip-flop layers empty when switching modes so backend action prompts can fill them", () => {
    const onChange = vi.fn();
    render(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "full_frame", visual_layers: [] }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={onChange}
        onOpenSettingsSection={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Flip-flop/i }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        visual_mode: "flipflop",
        visual_layers: [],
      }),
    );
  });

  it("preserves the last selected flip-flop action when toggling modes back to flip-flop", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "flipflop", flipflop_action: "eye_glance" }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={onChange}
        onOpenSettingsSection={() => undefined}
      />,
    );

    rerender(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "full_frame", flipflop_action: "" }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={onChange}
        onOpenSettingsSection={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Flip-flop/i }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        visual_mode: "flipflop",
        flipflop_action: "eye_glance",
      }),
    );
  });

  it("does not offer unsupported body-pose actions for deterministic flip-flop overlays", () => {
    renderControls({ ...baseSettings, visual_mode: "flipflop" });

    const actionSelect = screen.getByLabelText("Flip-flop action");

    expect(within(actionSelect).queryByRole("option", { name: /Head nod/i })).not.toBeInTheDocument();
    expect(within(actionSelect).getByRole("option", { name: "Blink" })).toBeInTheDocument();
    expect(within(actionSelect).getByRole("option", { name: "Speaking mouth" })).toBeInTheDocument();
    expect(within(actionSelect).getByRole("option", { name: "Eye glance" })).toBeInTheDocument();
    expect(within(actionSelect).getByRole("option", { name: "Eyebrow raise" })).toBeInTheDocument();
  });

  it("does not expose editable State A/State B prompts for flip-flop (action-derived in backend)", () => {
    render(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={{ ...baseSettings, visual_mode: "flipflop", visual_layers: [] }}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={() => undefined}
        onOpenSettingsSection={() => undefined}
      />,
    );

    expect(screen.queryByLabelText("State A")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("State B")).not.toBeInTheDocument();
    expect(
      screen.getByText(/renderer-supported face actions/i),
    ).toBeInTheDocument();
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

    const voices = screen.getByTestId("test-lab-section-voices");
    expect(within(voices).getByText(/Default voice/i)).toBeInTheDocument();
    expect(within(voices).getByText(/Headless Hero Narrator/i)).toBeInTheDocument();
    expect(within(voices).getByText(/Settings.*Voices/i)).toBeInTheDocument();
    expect(within(voices).queryByLabelText(/Voice ID/i)).not.toBeInTheDocument();
    expect(within(voices).queryByRole("heading", { name: /Headless Hero Narrator/i })).not.toBeInTheDocument();
  });

  it("links directly to voice and subtitle settings", () => {
    const onOpenSettingsSection = vi.fn();
    render(
      <TestLabControls
        preset={preset}
        defaultMainCharacter={null}
        visualTreatmentDefaults={defaults}
        settings={baseSettings}
        voiceSummary={voiceSummary}
        subtitleSummary={subtitleSummary}
        onChange={() => undefined}
        onOpenSettingsSection={onOpenSettingsSection}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Open voice settings/i }));
    fireEvent.click(screen.getByRole("button", { name: /Open subtitle settings/i }));

    expect(onOpenSettingsSection).toHaveBeenNthCalledWith(1, "voice");
    expect(onOpenSettingsSection).toHaveBeenNthCalledWith(2, "subtitles");
  });

  it("does not expose subtitle highlight as a Test Lab option", () => {
    renderControls();

    expect(screen.queryByText(/Subtitle highlight/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Highlight:/i)).not.toBeInTheDocument();
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
