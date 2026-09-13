import { useEffect, useState } from "react";

import api from "../api";

export type LocalModality = "text" | "image" | "voice";

interface LocalModelsStatusResponse {
  enabled: boolean;
  modalities: Record<string, { source: string; active_model: string }>;
  daemons: Record<string, { healthy: boolean; url: string }>;
}

export interface LocalModeStatus {
  /** True once any modality resolves to local. */
  enabled: boolean;
  /** Which modalities are running locally right now. */
  local: Record<LocalModality, boolean>;
  /** Backends that are set to local but whose daemon is not answering. */
  unhealthy: string[];
  loaded: boolean;
}

const MODALITY_BACKEND: Record<LocalModality, string> = {
  text: "ollama",
  image: "comfyui",
  voice: "mlx-audio",
};

const EMPTY: LocalModeStatus = {
  enabled: false,
  local: { text: false, image: false, voice: false },
  unhealthy: [],
  loaded: false,
};

/** Read-only view of Local Mode, for screens that need to set expectations.
 *
 * A local stage is minutes-to-hours where the cloud is seconds, so several
 * screens need to say so before the user commits to a run. Failure resolves to
 * "not local" — a missing status must never invent a warning about a mode the
 * user may not even be using.
 */
export function useLocalModeStatus(): LocalModeStatus {
  const [status, setStatus] = useState<LocalModeStatus>(EMPTY);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const res = await api.get("/api/local-models");
      if (cancelled || !res.ok) {
        if (!cancelled) setStatus({ ...EMPTY, loaded: true });
        return;
      }
      const data = res.data as LocalModelsStatusResponse;
      const local = {
        text: data.modalities?.text?.source === "local",
        image: data.modalities?.image?.source === "local",
        voice: data.modalities?.voice?.source === "local",
      };
      const unhealthy = (Object.keys(local) as LocalModality[])
        .filter((m) => local[m] && data.daemons?.[MODALITY_BACKEND[m]]?.healthy === false)
        .map((m) => MODALITY_BACKEND[m]);
      setStatus({
        enabled: local.text || local.image || local.voice,
        local,
        unhealthy,
        loaded: true,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}
