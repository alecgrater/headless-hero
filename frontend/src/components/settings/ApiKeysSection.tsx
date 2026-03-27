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

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.64 0 8.577 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.64 0-8.577-3.007-9.963-7.178z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function EyeOffIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12c1.292 4.338 5.31 7.5 10.066 7.5.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
    </svg>
  );
}

export default function ApiKeysSection() {
  const [keyStatus, setKeyStatus] = useState<Record<string, KeyInfo>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [visible, setVisible] = useState<Record<string, boolean>>({});
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
      const refresh = await api.get("/api/settings/keys");
      if (refresh.ok) setKeyStatus(refresh.data as Record<string, KeyInfo>);
      setValues({});
      setVisible({});
    }
  };

  const toggleVisible = (key: string) => {
    setVisible((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const hasChanges = Object.values(values).some((v) => v.trim());

  return (
    <div className="px-8 py-8 max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">API Keys</h2>
          <p className="text-neutral-400 text-sm mt-1">
            Keys are stored locally and loaded automatically on startup.
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {loading ? (
        <div className="text-neutral-500 text-sm">Loading...</div>
      ) : (
        SERVICES.map((group, gi) => (
          <div key={gi} className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 space-y-4">
            {group.map((svc) => {
              const info = keyStatus[svc.key];
              const isConfigured = info?.configured;
              const isVisible = visible[svc.key] ?? false;

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
                  <div className="relative flex items-center gap-1">
                    <input
                      type={isVisible ? "text" : "password"}
                      value={values[svc.key] ?? ""}
                      onChange={(e) =>
                        setValues((prev) => ({ ...prev, [svc.key]: e.target.value }))
                      }
                      placeholder={
                        isConfigured
                          ? `Current: ${info.masked}`
                          : svc.placeholder
                      }
                      className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:border-violet-500 transition-colors font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => toggleVisible(svc.key)}
                      className="p-2 text-neutral-500 hover:text-neutral-300 transition-colors"
                      title={isVisible ? "Hide" : "Show"}
                    >
                      {isVisible ? (
                        <EyeOffIcon className="w-4 h-4" />
                      ) : (
                        <EyeIcon className="w-4 h-4" />
                      )}
                    </button>
                    {info?.source === "env" && isConfigured && (
                      <span className="text-[10px] text-neutral-600 shrink-0">
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
  );
}
