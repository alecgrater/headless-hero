import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";

import api from "../../api";
import SettingsSectionHeader from "./SettingsSectionHeader";
import { useDebouncedAutosave } from "./useDebouncedAutosave";

export type Modality = "text" | "image" | "voice";
export type ModalityMode = "auto" | "local" | "cloud";

const MODALITIES: Modality[] = ["text", "image", "voice"];
const MODES: ModalityMode[] = ["auto", "local", "cloud"];

const MODE_KEYS: Record<Modality, string> = {
  text: "LOCAL_TEXT_MODE",
  image: "LOCAL_IMAGE_MODE",
  voice: "LOCAL_VOICE_MODE",
};

const MODEL_KEYS: Record<Modality, string> = {
  text: "LOCAL_TEXT_MODEL",
  image: "LOCAL_IMAGE_MODEL",
  voice: "LOCAL_VOICE_MODEL",
};

const MODALITY_LABELS: Record<Modality, string> = {
  text: "Text",
  image: "Images",
  voice: "Voice",
};

const MODALITY_HINTS: Record<Modality, string> = {
  text: "Scripts, ideas, SEO, scene routing, and every other LLM call.",
  image: "Scene images, frames, thumbnails, character references, and cutouts.",
  voice: "Narration for every scene. Word timings come from local Whisper alignment.",
};

const MODE_LABELS: Record<ModalityMode, string> = {
  auto: "Auto",
  local: "Local",
  cloud: "Cloud",
};

export interface LocalModelInfo {
  id: string;
  label: string;
  description: string;
  backend: string;
  license: string;
  approx_resident_gb: number;
  requires_attribution: boolean;
  attribution_text: string;
}

export interface LocalModelsStatus {
  enabled: boolean;
  modalities: Record<string, { source: string; active_model: string }>;
  catalog: Record<string, LocalModelInfo[]>;
  daemons: Record<string, { healthy: boolean; url: string }>;
}

export interface LocalModeState {
  enabled: boolean;
  modes: Record<Modality, ModalityMode>;
  models: Record<Modality, string>;
}

type KeyRow = { masked?: string };

/** Map a /api/settings/keys response into Local Mode state.
 *
 * `fallbacks` come from /api/local-models, i.e. the backend registry — the
 * defaults are never duplicated here, because a stale copy would silently
 * select (and then autosave) a model the benchmarks rejected.
 */
export function localModeFromResponse(
  data: Record<string, KeyRow>,
  fallbacks: Partial<Record<Modality, string>> = {},
): LocalModeState {
  const readMode = (modality: Modality): ModalityMode => {
    const raw = data[MODE_KEYS[modality]]?.masked ?? "";
    return (MODES as string[]).includes(raw) ? (raw as ModalityMode) : "auto";
  };
  const readModel = (modality: Modality): string =>
    data[MODEL_KEYS[modality]]?.masked || fallbacks[modality] || "";

  return {
    enabled: data.LOCAL_MODELS_ENABLED?.masked === "true",
    modes: { text: readMode("text"), image: readMode("image"), voice: readMode("voice") },
    models: { text: readModel("text"), image: readModel("image"), voice: readModel("voice") },
  };
}

/** Build the /api/settings/keys payload for Local Mode state. */
export function localModePayload(state: LocalModeState): Record<string, string> {
  return {
    LOCAL_MODELS_ENABLED: state.enabled ? "true" : "false",
    LOCAL_TEXT_MODE: state.modes.text,
    LOCAL_IMAGE_MODE: state.modes.image,
    LOCAL_VOICE_MODE: state.modes.voice,
    LOCAL_TEXT_MODEL: state.models.text,
    LOCAL_IMAGE_MODEL: state.models.image,
    LOCAL_VOICE_MODEL: state.models.voice,
  };
}

/** Resolve what a modality will actually use, given the master switch. */
export function effectiveSource(state: LocalModeState, modality: Modality): "local" | "cloud" {
  const mode = state.modes[modality];
  if (mode === "auto") return state.enabled ? "local" : "cloud";
  return mode;
}

export default function LocalModelsSection() {
  const [status, setStatus] = useState<LocalModelsStatus | null>(null);
  const [state, setState] = useState<LocalModeState>({
    enabled: false,
    modes: { text: "auto", image: "auto", voice: "auto" },
    models: { text: "", image: "", voice: "" },
  });
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // Sequential, not parallel: the registry response supplies the per-modality
    // fallbacks used when a key has never been saved.
    void (async () => {
      const statusRes = await api.get("/api/local-models");
      const nextStatus = statusRes.ok ? (statusRes.data as LocalModelsStatus) : null;
      if (nextStatus) setStatus(nextStatus);

      const fallbacks: Partial<Record<Modality, string>> = {};
      for (const modality of MODALITIES) {
        const active = nextStatus?.modalities?.[modality]?.active_model;
        if (active) fallbacks[modality] = active;
      }

      const keysRes = await api.get("/api/settings/keys");
      if (keysRes.ok) {
        setState(localModeFromResponse(keysRes.data as Record<string, KeyRow>, fallbacks));
      }
      setLoaded(true);
    })();
  }, []);

  useDebouncedAutosave(
    loaded,
    async () => {
      setSaving(true);
      const res = await api.put("/api/settings/keys", localModePayload(state));
      setSaving(false);
      setError(res.ok ? "" : "Could not save local model settings.");
      return res.ok;
    },
    [state.enabled, state.modes.text, state.modes.image, state.modes.voice,
      state.models.text, state.models.image, state.models.voice],
  );

  const setMode = (modality: Modality, mode: ModalityMode) =>
    setState((prev) => ({ ...prev, modes: { ...prev.modes, [modality]: mode } }));

  const setModel = (modality: Modality, model: string) =>
    setState((prev) => ({ ...prev, models: { ...prev.models, [modality]: model } }));

  const catalogFor = (modality: Modality): LocalModelInfo[] => status?.catalog?.[modality] ?? [];

  const selectedVoice = catalogFor("voice").find((m) => m.id === state.models.voice);
  const voiceIsLocal = effectiveSource(state, "voice") === "local";
  const showAttribution = Boolean(voiceIsLocal && selectedVoice?.requires_attribution);

  return (
    <div className="space-y-6">
      <SettingsSectionHeader
        title="Local Models"
        description="Run generation on models installed on this machine instead of cloud APIs."
      />

      <div className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-neutral-100">Use local models</p>
            <p className="text-xs leading-relaxed text-neutral-500">
              Switches text, images, and voice to local models in one move. Each modality below can
              still be pinned independently.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={state.enabled}
            aria-label="Use local models"
            onClick={() => setState((prev) => ({ ...prev, enabled: !prev.enabled }))}
            className={`relative h-6 w-11 shrink-0 rounded-full transition-colors hover:opacity-90 ${
              state.enabled ? "bg-violet-500" : "bg-neutral-700"
            }`}
          >
            <span
              className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                state.enabled ? "translate-x-[22px]" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
        <p data-testid="memory-arena-note" className="text-xs leading-relaxed text-amber-300/80">
          Only one local model stays in memory at a time — this machine cannot hold the text, image,
          and voice models plus the renderer at once. Stages run one after another, so a fully local
          video takes longer end to end than a cloud one.
        </p>
      </div>

      <div className="space-y-4">
        {MODALITIES.map((modality) => (
          <div
            key={modality}
            className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-4"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-neutral-100">{MODALITY_LABELS[modality]}</p>
                <p className="text-xs leading-relaxed text-neutral-500">
                  {MODALITY_HINTS[modality]}
                </p>
              </div>
              <div className="flex shrink-0 overflow-hidden rounded-lg border border-neutral-700">
                {MODES.map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setMode(modality, mode)}
                    aria-pressed={state.modes[modality] === mode}
                    className={`px-3 py-1.5 text-xs transition-colors hover:bg-neutral-700 ${
                      state.modes[modality] === mode
                        ? "bg-violet-500/80 text-white"
                        : "bg-neutral-900 text-neutral-400"
                    }`}
                  >
                    {MODE_LABELS[mode]}
                  </button>
                ))}
              </div>
            </div>

            <label className="block space-y-1">
              <span className="text-sm text-neutral-300">
                {MODALITY_LABELS[modality]} model
              </span>
              <select
                value={state.models[modality]}
                onChange={(e) => setModel(modality, e.target.value)}
                className="w-full rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 transition-colors hover:border-neutral-600"
              >
                {catalogFor(modality).map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.label} — {model.approx_resident_gb} GB — {model.license}
                  </option>
                ))}
              </select>
            </label>

            <p className="text-xs text-neutral-500">
              Currently using{" "}
              <span className="text-neutral-300">{effectiveSource(state, modality)}</span>.
            </p>
          </div>
        ))}
      </div>

      {showAttribution && (
        <div
          data-testid="voice-attribution-note"
          className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 text-xs leading-relaxed text-amber-200"
        >
          <p className="font-medium">This voice model requires a credit.</p>
          <p className="mt-1">
            {selectedVoice?.label} is free for monetized video only if you credit its creator, so
            “{selectedVoice?.attribution_text}” is appended to every generated SEO description
            automatically. This cannot be turned off while this model is selected — pick Kokoro or
            Chatterbox instead if you would rather not carry the credit.
          </p>
        </div>
      )}

      <div className="space-y-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
        <p className="text-sm font-medium text-neutral-100">Local services</p>
        {Object.entries(status?.daemons ?? {}).map(([backend, info]) => (
          <div
            key={backend}
            data-testid={`daemon-${backend}`}
            className="flex items-center justify-between gap-4 text-xs"
          >
            <span className="flex items-center gap-2 text-neutral-300">
              <Cpu className="h-3.5 w-3.5 text-neutral-500" />
              {backend}
            </span>
            <span className="text-neutral-500">{info.url}</span>
            <span className={info.healthy ? "text-emerald-400" : "text-red-400"}>
              {info.healthy ? "Healthy" : "Not running"}
            </span>
          </div>
        ))}
        <p className="text-xs leading-relaxed text-neutral-500">
          Install or repair these with <code className="text-neutral-400">scripts/install-local-models.sh</code>.
        </p>
      </div>

      <p data-testid="video-cloud-note" className="text-xs leading-relaxed text-neutral-500">
        AI video always uses the cloud provider configured in Visuals, even with Local Mode on.
        Local video models are impractically slow on this hardware, so they are deliberately not
        offered. Anchor images for video scenes are still generated locally.
      </p>

      {saving && <p className="text-xs text-neutral-500">Saving…</p>}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
