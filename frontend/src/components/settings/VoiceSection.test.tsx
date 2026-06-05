import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import VoiceSection from "./VoiceSection";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async (path: string) => {
      if (path === "/api/brand") {
        return { ok: true, status: 200, data: { voice_id: "voice-1" } };
      }
      if (path === "/api/voice/voices") {
        return {
          ok: true,
          status: 200,
          data: {
            voices: [
              { voice_id: "voice-1", name: "Headless Hero Narrator" },
              { voice_id: "voice-2", name: "Adam Greene" },
            ],
          },
        };
      }
      return {
        ok: true,
        status: 200,
        data: {
          ELEVENLABS_TTS_MODEL: { masked: "eleven_multilingual_v2" },
          ELEVENLABS_STABILITY: { masked: "0.5" },
          ELEVENLABS_STYLE: { masked: "0.0" },
          ELEVENLABS_SPEED: { masked: "1.0" },
          AUDIO_FILTER_HIGHPASS: { masked: "true" },
          AUDIO_FILTER_NOISE_REDUCTION: { masked: "true" },
          AUDIO_FILTER_COMPRESSOR: { masked: "true" },
        },
      };
    }),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("VoiceSection layout", () => {
  it("keeps narration choice items unboxed under boxed section titles", async () => {
    render(<VoiceSection panel="voice" showHeader={false} />);

    const modelButton = await screen.findByRole("button", { name: /v2 - steady production voice/i });
    expect(modelButton).toHaveClass("border-l-2", "border-violet-400");
    expect(modelButton).not.toHaveClass("rounded-lg", "border", "bg-violet-500/15");

    const presetButton = screen.getByRole("button", { name: "Steady" });
    expect(presetButton).toHaveClass("border-l-2", "border-violet-400");
    expect(presetButton).not.toHaveClass("rounded-lg", "border", "bg-violet-500/15");
  });

  it("keeps recording filter rows unboxed while switches remain explicit controls", async () => {
    render(<VoiceSection panel="voice" showHeader={false} />);

    const lowCutSwitch = await screen.findByRole("switch", { name: /Low-cut filter/i });
    const row = lowCutSwitch.closest("label");
    expect(row).toHaveClass("border-l-2", "border-violet-400");
    expect(row).not.toHaveClass("rounded-lg", "border", "bg-neutral-800/50");
    expect(lowCutSwitch).toHaveClass("rounded-full");
  });
});
