import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";

import api from "../../api";
import {
  DELIVERY_PRESETS,
  defaultVoiceIdForNarration,
  deliveryPresetForSettings,
  settingsPayloadForVisibleControls,
  sortVoicesForNarration,
  type TtsSettings,
} from "./VoiceSection";
import VoiceSection from "./VoiceSection";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async (path: string) => {
      if (path === "/api/brand") {
        return { ok: true, status: 200, data: { voice_id: "voice-1" } };
      }
      if (path === "/api/settings/keys") {
        return {
          ok: true,
          status: 200,
          data: {
            ELEVENLABS_TTS_MODEL: { masked: "eleven_multilingual_v2" },
            ELEVENLABS_STABILITY: { masked: "0.5" },
            ELEVENLABS_STYLE: { masked: "0.0" },
            ELEVENLABS_SPEED: { masked: "1.0" },
          },
        };
      }
      if (path === "/api/voice/voices") {
        return {
          ok: true,
          status: 200,
          data: {
            voices: [
              { voice_id: "other", name: "Unused Voice", category: "cloned" },
              { voice_id: "headless", name: "Headless Hero Narrator", category: "cloned" },
              { voice_id: "liam", name: "Liam - Viral Short-Form Storyteller", category: "cloned" },
              { voice_id: "adam", name: "Adam Greene - Clear, Friendly & Engaging", category: "cloned" },
            ],
          },
        };
      }
      return { ok: true, status: 200, data: {} };
    }),
    post: vi.fn(),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("ElevenLabs delivery presets", () => {
  it("prefers the custom Headless Hero narrator before fallback voices", () => {
    const voices = [
      { voice_id: "other", name: "Unused Voice", category: "cloned" },
      { voice_id: "adam", name: "Adam Greene - Clear, Friendly & Engaging", category: "cloned" },
      { voice_id: "liam", name: "Liam - Viral Short-Form Storyteller", category: "cloned" },
      { voice_id: "headless", name: "Headless Hero Narrator", category: "cloned" },
    ];

    expect(sortVoicesForNarration(voices).map((voice) => voice.voice_id)).toEqual([
      "headless",
      "liam",
      "adam",
    ]);
    expect(defaultVoiceIdForNarration(voices)).toBe("headless");
  });

  it("maps conservative preset names to concrete TTS settings", () => {
    expect(DELIVERY_PRESETS.steady.settings).toEqual({
      ELEVENLABS_TTS_MODEL: "eleven_multilingual_v2",
      ELEVENLABS_STABILITY: "0.5",
      ELEVENLABS_STYLE: "0.0",
      ELEVENLABS_SPEED: "1.0",
    });
    expect(DELIVERY_PRESETS.more_human.settings).toEqual({
      ELEVENLABS_TTS_MODEL: "eleven_multilingual_v2",
      ELEVENLABS_STABILITY: "0.45",
      ELEVENLABS_STYLE: "0.15",
      ELEVENLABS_SPEED: "0.97",
    });
    expect(DELIVERY_PRESETS.dramatic.settings).toEqual({
      ELEVENLABS_TTS_MODEL: "eleven_multilingual_v2",
      ELEVENLABS_STABILITY: "0.35",
      ELEVENLABS_STYLE: "0.25",
      ELEVENLABS_SPEED: "0.95",
    });
  });

  it("detects matching presets and falls back to custom after manual edits", () => {
    expect(deliveryPresetForSettings(DELIVERY_PRESETS.more_human.settings)).toBe("more_human");

    const custom: TtsSettings = {
      ...DELIVERY_PRESETS.more_human.settings,
      ELEVENLABS_SPEED: "0.98",
    };

    expect(deliveryPresetForSettings(custom)).toBe("custom");
  });

  it("saves only the controls visible for the selected model", () => {
    const settings: TtsSettings = {
      ELEVENLABS_TTS_MODEL: "eleven_v3",
      ELEVENLABS_STABILITY: "0.5",
      ELEVENLABS_STYLE: "0.99",
      ELEVENLABS_SPEED: "0.7",
    };

    expect(settingsPayloadForVisibleControls(settings)).toEqual({
      ELEVENLABS_TTS_MODEL: "eleven_v3",
      ELEVENLABS_STABILITY: "0.5",
    });
    expect(settingsPayloadForVisibleControls(DELIVERY_PRESETS.more_human.settings)).toEqual(
      DELIVERY_PRESETS.more_human.settings,
    );
  });

  it("shows helper notes and applies the More Human preset to advanced controls", async () => {
    render(createElement(VoiceSection, { panel: "voice" }));

    expect(await screen.findByText("Recommended: Headless Hero Narrator for the main channel voice. Liam is a stronger shorts-style fallback; Adam is a friendlier backup.")).toBeTruthy();
    expect(screen.getByLabelText("Default Voice")).toHaveTextContent("Headless Hero Narrator");
    expect(screen.queryByText("Unused Voice")).toBeNull();
    expect(await screen.findByText("Delivery preset")).toBeTruthy();
    expect(screen.getByText("For v2 only. Presets fill the saved delivery settings; choose Custom to tune sliders manually.")).toBeTruthy();
    expect(screen.getByText("Uses Eleven v2 with neutral delivery settings. Best when consistency matters more than extra emotion.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "More Human" }));

    await waitFor(() => {
      expect(screen.getAllByText("More Human").length).toBeGreaterThan(0);
      expect(screen.getByText("Keeps Eleven v2, slightly lowers stability, adds light style, and slows delivery a touch for more natural pacing.")).toBeTruthy();
    });
    expect(screen.queryByLabelText("Stability")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Custom" }));
    expect(screen.getByLabelText("Stability")).toHaveValue("0.45");
    expect(screen.getByLabelText("Style exaggeration")).toHaveValue("0.15");
    expect(screen.getByLabelText("Speed")).toHaveValue("0.97");
  });

  it("shows only v3 stability and saves no hidden v2-only settings when v3 is selected", async () => {
    render(createElement(VoiceSection, { panel: "voice" }));

    fireEvent.click(await screen.findByRole("button", { name: "v3 - expressive voice with hidden tags" }));

    expect(screen.queryByText("Delivery preset")).toBeNull();
    expect(screen.getByLabelText("Stability")).toHaveValue("0.5");
    expect(screen.queryByLabelText("Style exaggeration")).toBeNull();
    expect(screen.queryByLabelText("Speed")).toBeNull();

    fireEvent.change(screen.getByLabelText("Stability"), { target: { value: "0.4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save delivery settings" }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith("/api/settings/keys", {
        ELEVENLABS_TTS_MODEL: "eleven_v3",
        ELEVENLABS_STABILITY: "0.4",
      });
    });
  });
});
