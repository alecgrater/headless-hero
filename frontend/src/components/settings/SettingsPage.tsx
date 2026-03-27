import { useEffect, useState } from "react";
import api from "../../api";
import { showToast } from "../ToastContainer";

interface KeyInfo {
  configured: boolean;
  masked: string;
  source: "db" | "env" | "none";
}

interface ServiceConfig {
  key: string;
  label: string;
  description: string;
  placeholder: string;
}

const SERVICES: ServiceConfig[][] = [
  [
    {
      key: "ANTHROPIC_API_KEY",
      label: "Anthropic",
      description: "Powers idea generation, script writing, and SEO metadata via Claude.",
      placeholder: "sk-ant-...",
    },
  ],
  [
    {
      key: "FAL_KEY",
      label: "fal.ai",
      description: "Generates images for scenes and thumbnails via Flux.",
      placeholder: "fal-...",
    },
  ],
  [
    {
      key: "ELEVENLABS_API_KEY",
      label: "ElevenLabs",
      description: "Text-to-speech voiceover and voice cloning.",
      placeholder: "xi-...",
    },
  ],
  [
    {
      key: "GOOGLE_CLIENT_ID",
      label: "Google Client ID",
      description: "OAuth client ID for YouTube uploads.",
      placeholder: "123456789.apps.googleusercontent.com",
    },
    {
      key: "GOOGLE_CLIENT_SECRET",
      label: "Google Client Secret",
      description: "OAuth client secret for YouTube uploads.",
      placeholder: "GOCSPX-...",
    },
  ],
];

interface Props {
  onBack: () => void;
}

export default function SettingsPage({ onBack }: Props) {
  const [keyStatus, setKeyStatus] = useState<Record<string, KeyInfo>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        setKeyStatus(res.data as Record<string, KeyInfo>);
      }
      setLoading(false);
    });
  }, []);

  const handleSave = async () => {
    // Only send keys that the user actually typed something into
    const toSave: Record<string, string> = {};
    for (const [k, v] of Object.entries(values)) {
      if (v.trim()) toSave[k] = v.trim();
    }
    if (Object.keys(toSave).length === 0) {
      showToast("No changes to save", "info");
      return;
    }

    setSaving(true);
    const res = await api.put("/api/settings/keys", toSave);
    setSaving(false);

    if (res.ok) {
      showToast("API keys saved", "success");
      // Refresh status
      const refresh = await api.get("/api/settings/keys");
      if (refresh.ok) setKeyStatus(refresh.data as Record<string, KeyInfo>);
      setValues({});
    }
  };

  const hasChanges = Object.values(values).some((v) => v.trim());

  return (
    <div className="flex flex-col h-full">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-neutral-950 border-b border-neutral-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="text-neutral-400 hover:text-neutral-200 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-8 max-w-2xl mx-auto w-full space-y-6">
        <p className="text-neutral-400 text-sm">
          Enter your API keys below. Keys are stored locally in the app database and loaded automatically on startup.
        </p>

        {loading ? (
          <div className="text-neutral-500 text-sm">Loading...</div>
        ) : (
          SERVICES.map((group, gi) => (
            <div key={gi} className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-4">
              {group.map((svc) => {
                const info = keyStatus[svc.key];
                const isConfigured = info?.configured;

                return (
                  <div key={svc.key} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-medium text-neutral-100">{svc.label}</h3>
                        <p className="text-xs text-neutral-500">{svc.description}</p>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          isConfigured
                            ? "bg-emerald-500/10 text-emerald-400"
                            : "bg-red-500/10 text-red-400"
                        }`}
                      >
                        {isConfigured ? "Configured" : "Missing"}
                      </span>
                    </div>
                    <div className="relative">
                      <input
                        type="password"
                        value={values[svc.key] ?? ""}
                        onChange={(e) =>
                          setValues((prev) => ({ ...prev, [svc.key]: e.target.value }))
                        }
                        placeholder={
                          isConfigured
                            ? `Current: ${info.masked}`
                            : svc.placeholder
                        }
                        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 transition-colors font-mono"
                      />
                      {info?.source === "env" && isConfigured && (
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-neutral-600">
                          from env
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
