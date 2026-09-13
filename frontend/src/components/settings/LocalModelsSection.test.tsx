import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../api";
import LocalModelsSection, { localModeFromResponse, localModePayload } from "./LocalModelsSection";

const CATALOG = {
  enabled: false,
  modalities: {
    text: { source: "cloud", active_model: "qwen3.8-27b" },
    image: { source: "cloud", active_model: "qwen-image-edit-2511" },
    voice: { source: "cloud", active_model: "higgs-tts-3-4b" },
  },
  catalog: {
    text: [
      {
        id: "qwen3.8-27b",
        label: "Qwen3.8 27B (Q4_K_M)",
        description: "d",
        backend: "ollama",
        license: "Apache-2.0",
        approx_resident_gb: 17,
        requires_attribution: false,
        attribution_text: "",
      },
    ],
    image: [
      {
        id: "qwen-image-edit-2511",
        label: "Qwen-Image-Edit 2511 (Q4_K_M)",
        description: "d",
        backend: "comfyui",
        license: "Apache-2.0",
        approx_resident_gb: 13.2,
        requires_attribution: false,
        attribution_text: "",
      },
      {
        id: "flux2-klein-4b",
        label: "FLUX.2 klein 4B",
        description: "d",
        backend: "comfyui",
        license: "Apache-2.0",
        approx_resident_gb: 13,
        requires_attribution: false,
        attribution_text: "",
      },
    ],
    voice: [
      {
        id: "higgs-tts-3-4b",
        label: "Higgs TTS 3 (4B)",
        description: "d",
        backend: "mlx-audio",
        license: "Boson",
        approx_resident_gb: 4,
        requires_attribution: true,
        attribution_text: "Voice: Boson AI Higgs Audio",
      },
      {
        id: "kokoro-82m",
        label: "Kokoro 82M",
        description: "d",
        backend: "mlx-audio",
        license: "Apache-2.0",
        approx_resident_gb: 0.5,
        requires_attribution: false,
        attribution_text: "",
      },
    ],
  },
  daemons: {
    ollama: { healthy: true, url: "http://127.0.0.1:11434" },
    comfyui: { healthy: false, url: "http://127.0.0.1:8188" },
    "mlx-audio": { healthy: true, url: "http://127.0.0.1:8770" },
  },
};

const KEYS = {
  LOCAL_MODELS_ENABLED: { masked: "false" },
  LOCAL_TEXT_MODE: { masked: "auto" },
  LOCAL_IMAGE_MODE: { masked: "auto" },
  LOCAL_VOICE_MODE: { masked: "auto" },
  LOCAL_TEXT_MODEL: { masked: "qwen3.8-27b" },
  LOCAL_IMAGE_MODEL: { masked: "qwen-image-edit-2511" },
  LOCAL_VOICE_MODEL: { masked: "higgs-tts-3-4b" },
};

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

function mockKeys(overrides: Record<string, { masked: string }> = {}) {
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path === "/api/local-models") {
      return { ok: true, status: 200, data: CATALOG };
    }
    return { ok: true, status: 200, data: { ...KEYS, ...overrides } };
  });
}

beforeEach(() => {
  mockKeys();
  vi.mocked(api.put).mockResolvedValue({ ok: true, status: 200, data: {} });
});

describe("LocalModelsSection settings mapping", () => {
  it("maps settings rows into local mode state", () => {
    expect(localModeFromResponse({
      LOCAL_MODELS_ENABLED: { masked: "true" },
      LOCAL_TEXT_MODE: { masked: "cloud" },
      LOCAL_IMAGE_MODE: { masked: "auto" },
      LOCAL_VOICE_MODE: { masked: "local" },
      LOCAL_TEXT_MODEL: { masked: "qwen3.8-27b" },
      LOCAL_IMAGE_MODEL: { masked: "flux2-klein-4b" },
      LOCAL_VOICE_MODEL: { masked: "kokoro-82m" },
    })).toEqual({
      enabled: true,
      modes: { text: "cloud", image: "auto", voice: "local" },
      models: { text: "qwen3.8-27b", image: "flux2-klein-4b", voice: "kokoro-82m" },
    });
  });

  it("falls back to safe defaults for unrecognised values", () => {
    expect(localModeFromResponse({
      LOCAL_MODELS_ENABLED: { masked: "" },
      LOCAL_TEXT_MODE: { masked: "sideways" },
    })).toEqual({
      enabled: false,
      modes: { text: "auto", image: "auto", voice: "auto" },
      models: { text: "qwen3.8-27b", image: "qwen-image-edit-2511", voice: "higgs-tts-3-4b" },
    });
  });

  it("builds a save payload", () => {
    expect(localModePayload({
      enabled: true,
      modes: { text: "auto", image: "cloud", voice: "local" },
      models: { text: "qwen3.8-27b", image: "flux2-klein-4b", voice: "kokoro-82m" },
    })).toEqual({
      LOCAL_MODELS_ENABLED: "true",
      LOCAL_TEXT_MODE: "auto",
      LOCAL_IMAGE_MODE: "cloud",
      LOCAL_VOICE_MODE: "local",
      LOCAL_TEXT_MODEL: "qwen3.8-27b",
      LOCAL_IMAGE_MODEL: "flux2-klein-4b",
      LOCAL_VOICE_MODEL: "kokoro-82m",
    });
  });
});

describe("LocalModelsSection", () => {
  it("renders daemon health for each backend", async () => {
    render(createElement(LocalModelsSection));
    await waitFor(() => expect(screen.getByTestId("daemon-comfyui")).toBeTruthy());
    expect(screen.getByTestId("daemon-ollama").textContent).toMatch(/Healthy/i);
    expect(screen.getByTestId("daemon-comfyui").textContent).toMatch(/Not running/i);
  });

  it("saves the master switch when toggled", async () => {
    render(createElement(LocalModelsSection));
    const toggle = await screen.findByRole("switch", { name: /use local models/i });
    fireEvent.click(toggle);
    await waitFor(
      () =>
        expect(api.put).toHaveBeenCalledWith(
          "/api/settings/keys",
          expect.objectContaining({ LOCAL_MODELS_ENABLED: "true" }),
        ),
      { timeout: 3000 },
    );
  });

  it("hides the attribution note while voice is still on the cloud", async () => {
    render(createElement(LocalModelsSection));
    await waitFor(() => expect(screen.getByTestId("video-cloud-note")).toBeTruthy());
    expect(screen.queryByTestId("voice-attribution-note")).toBeNull();
  });

  it("warns that the selected voice model requires attribution", async () => {
    mockKeys({ LOCAL_MODELS_ENABLED: { masked: "true" } });
    render(createElement(LocalModelsSection));
    await waitFor(() => expect(screen.getByTestId("voice-attribution-note")).toBeTruthy());
    expect(screen.getByTestId("voice-attribution-note").textContent).toMatch(/Boson AI Higgs Audio/);
  });

  it("hides the attribution note for a permissive voice model", async () => {
    mockKeys({ LOCAL_MODELS_ENABLED: { masked: "true" } });
    render(createElement(LocalModelsSection));
    await waitFor(() => expect(screen.getByTestId("voice-attribution-note")).toBeTruthy());
    const select = (await screen.findByLabelText(/voice model/i)) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "kokoro-82m" } });
    await waitFor(() => expect(screen.queryByTestId("voice-attribution-note")).toBeNull());
  });

  it("states that AI video stays on the cloud", async () => {
    render(createElement(LocalModelsSection));
    await waitFor(() => expect(screen.getByTestId("video-cloud-note")).toBeTruthy());
  });

  it("explains the one-model-at-a-time memory limit", async () => {
    render(createElement(LocalModelsSection));
    await waitFor(() => expect(screen.getByTestId("memory-arena-note")).toBeTruthy());
  });
});
