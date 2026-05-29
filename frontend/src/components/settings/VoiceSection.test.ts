import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  DELIVERY_PRESETS,
  deliveryPresetForSettings,
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
          data: { voices: [{ voice_id: "voice-1", name: "Narrator", category: "cloned" }] },
        };
      }
      return { ok: true, status: 200, data: {} };
    }),
    post: vi.fn(),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("ElevenLabs delivery presets", () => {
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
      ELEVENLABS_TTS_MODEL: "eleven_v3",
      ELEVENLABS_STABILITY: "0.4",
      ELEVENLABS_STYLE: "0.2",
      ELEVENLABS_SPEED: "0.96",
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

  it("shows helper notes and applies the More Human preset to advanced controls", async () => {
    render(createElement(VoiceSection, { panel: "voice" }));

    expect(await screen.findByLabelText("Delivery preset")).toBeTruthy();
    expect(screen.getByText("Presets fill the advanced controls below; manual edits switch this to Custom.")).toBeTruthy();
    expect(screen.getByText("Uses Eleven v2 with neutral delivery settings. Best when consistency matters more than extra emotion.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Delivery preset"), { target: { value: "more_human" } });

    await waitFor(() => {
      expect(screen.getByText("More Human")).toBeTruthy();
      expect(screen.getByText("Keeps Eleven v2, slightly lowers stability, adds light style, and slows delivery a touch for more natural pacing.")).toBeTruthy();
    });
    expect(screen.getByLabelText("Model (advanced)")).toHaveValue("eleven_multilingual_v2");
    expect(screen.getByLabelText("Stability")).toHaveValue("0.45");
    expect(screen.getByLabelText("Style exaggeration")).toHaveValue("0.15");
    expect(screen.getByLabelText("Speed")).toHaveValue("0.97");
  });
});
