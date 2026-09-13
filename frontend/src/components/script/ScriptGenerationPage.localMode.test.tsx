import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import ScriptGenerationPage from "./ScriptGenerationPage";

const localModeStatus = {
  enabled: true,
  local: { text: true, image: true, voice: true },
  unhealthy: [] as string[],
  loaded: true,
};

vi.mock("../../hooks/useLocalModeStatus", () => ({
  useLocalModeStatus: () => localModeStatus,
}));

const generationState = {
  script: null,
  scriptId: null,
  loading: false,
  error: null,
  selectedModel: "gpt-5-mini",
  segmented: true,
  generationStarted: false,
  settingsLoaded: true,
  estimatedSeconds: null as number | null,
  estimateSource: "measured" as "measured" | "baseline",
  scriptProgress: null,
  elapsedSeconds: null,
  genSegments: null,
  genCompletedSegments: [],
  phase: "idle",
  coldOpenResult: null,
  setScript: vi.fn(),
  handleGenerate: vi.fn(),
  handleCancelGeneration: vi.fn(),
  handleModelChange: vi.fn(),
  handleColdOpenSelect: vi.fn(),
  setSegmented: vi.fn(),
};

vi.mock("./useScriptGeneration", () => ({ default: () => generationState }));

vi.mock("./useSceneEditing", () => ({
  default: () => ({
    editingKey: null,
    editNarration: "",
    editHookText: "",
    editedScenes: new Set<string>(),
    refiningScene: null,
    saving: false,
    setEditNarration: vi.fn(),
    setEditHookText: vi.fn(),
    startEditScene: vi.fn(),
    cancelEdit: vi.fn(),
    saveSceneEdit: vi.fn(),
    startEditIntro: vi.fn(),
    saveIntroEdit: vi.fn(),
    startEditOutro: vi.fn(),
    saveOutroEdit: vi.fn(),
    refineScene: vi.fn(),
  }),
}));

vi.mock("./useTitleCardGeneration", () => ({
  default: () => ({
    titleCardGenerating: false,
    titleCardGenerated: false,
    titleCardError: null,
    titleCardCompleted: [],
    titleCardTotal: 0,
    generateTitleCards: vi.fn(),
  }),
}));

vi.mock("../../api", () => ({
  default: { get: vi.fn().mockResolvedValue({ ok: false, data: {} }) },
  assetUrl: (p: string) => p,
  getFormats: vi.fn().mockResolvedValue({ ok: false, data: [] }),
  getProjectConfig: vi.fn().mockResolvedValue({ ok: false, data: {} }),
}));

function renderPage() {
  return render(
    <ScriptGenerationPage
      brandId="brand-1"
      idea={{
        title: "Five Accidental Inventions",
        description: "Origin stories.",
        format_id: "youtube-listicle",
        segments_est: 8,
        keywords: ["history"],
      }}
      onBack={vi.fn()}
      onContinue={vi.fn()}
    />,
  );
}

describe("ScriptGenerationPage — Local Mode notice", () => {
  beforeEach(() => {
    localModeStatus.enabled = true;
    localModeStatus.local = { text: true, image: true, voice: true };
    localModeStatus.unhealthy = [];
    generationState.estimatedSeconds = null;
    generationState.estimateSource = "measured";
  });

  it("warns before a local run starts", async () => {
    renderPage();
    const notice = await screen.findByTestId("local-mode-generation-notice");
    expect(notice.textContent).toMatch(/Local Mode is on/);
    expect(notice.textContent).toMatch(/written by a model on this machine/);
  });

  it("stays out of the way when nothing is local", async () => {
    localModeStatus.enabled = false;
    localModeStatus.local = { text: false, image: false, voice: false };
    renderPage();
    await screen.findByText("Generate Script");
    expect(screen.queryByTestId("local-mode-generation-notice")).toBeNull();
  });

  it("names only the modalities that are actually local", async () => {
    localModeStatus.local = { text: false, image: true, voice: false };
    renderPage();
    const notice = await screen.findByTestId("local-mode-generation-notice");
    expect(notice.textContent).toMatch(/Local Mode is on for images/);
    expect(notice.textContent).not.toMatch(/and voice/);
    expect(notice.textContent).toMatch(/script still comes from the cloud/);
  });

  it("quotes the measured estimate once there is one", async () => {
    generationState.estimatedSeconds = 3600;
    renderPage();
    const notice = await screen.findByTestId("local-mode-generation-notice");
    expect(notice.textContent).toMatch(/about 60 minutes/);
    expect(notice.textContent).not.toMatch(/no local run measured yet/);
  });

  it("flags an estimate that came from the published baseline", async () => {
    generationState.estimatedSeconds = 5700;
    generationState.estimateSource = "baseline";
    renderPage();
    const notice = await screen.findByTestId("local-mode-generation-notice");
    expect(notice.textContent).toMatch(/no local run measured yet/);
  });

  it("names a daemon that is down, because generation will fail without it", async () => {
    localModeStatus.unhealthy = ["comfyui"];
    renderPage();
    const notice = await screen.findByTestId("local-mode-generation-notice");
    expect(notice.textContent).toMatch(/comfyui/);
    expect(notice.textContent).toMatch(/not responding/);
  });
});
