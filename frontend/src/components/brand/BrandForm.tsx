import { useCallback, useEffect, useRef, useState } from "react";
import type { BrandProfileCreate, ContentModifierMeta } from "../../types/brand";
import type { OAuthStatusResponse } from "../../types/publish";
import api, { fetchModifiers, openInBrowser } from "../../api";
import { Mic, X } from "lucide-react";
import useVoiceCloning from "./useVoiceCloning";

const OAUTH_POLL_INTERVAL_MS = 2000;
const OAUTH_CONNECT_TIMEOUT_MS = 300_000; // 5 minutes

const EMPTY_FORM: BrandProfileCreate = {
  name: "",
  content_modifiers: "",
  voice_id: "",
  youtube_channel_id: "",
};

interface Voice {
  voice_id: string;
  name: string;
}

interface Props {
  onSave: (brand: BrandProfileCreate) => Promise<void>;
  onCancel: () => void;
  initial?: BrandProfileCreate;
  saving?: boolean;
  brandId?: string;
}

/* ---- Icon subcomponents ---- */

function YouTubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function BrandForm({ onSave, onCancel, initial, saving, brandId }: Props) {
  const [form, setForm] = useState<BrandProfileCreate>(initial ? { ...EMPTY_FORM, ...initial } : EMPTY_FORM);
  const [modifiers, setModifiers] = useState<ContentModifierMeta[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);

  // Voice cloning via shared hook
  const {
    audioFiles, cloneName, setCloneName, cloning, cloneError,
    fileInputRef, addFiles, removeFile, handleClone, maxFiles,
  } = useVoiceCloning({
    defaultName: form.name,
    onCloned: async (voiceId) => {
      set("voice_id", voiceId);
      // Refresh voices list so the cloned voice appears in the dropdown
      const res = await api.get("/api/voice/voices");
      if (res.ok && res.data) {
        const voices = (res.data as { voices: Voice[] }).voices;
        if (Array.isArray(voices)) {
          setVoices(voices);
        }
      }
    },
  });

  // YouTube OAuth state
  const [ytConnected, setYtConnected] = useState(false);
  const [ytChannelName, setYtChannelName] = useState("");
  const [ytConnecting, setYtConnecting] = useState(false);
  const connectionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isEditing = !!brandId;

  useEffect(() => {
    fetchModifiers().then((res) => {
      if (res.ok && Array.isArray(res.data)) {
        setModifiers(res.data as ContentModifierMeta[]);
      }
    });

    api.get("/api/voice/voices").then((res) => {
      if (res.ok && res.data) {
        const voices = (res.data as { voices: Voice[] }).voices;
        if (Array.isArray(voices)) {
          setVoices(voices);
        }
      }
    });
  }, []);

  // Fetch YouTube OAuth status when editing
  const fetchYtStatus = useCallback(async () => {
    if (!brandId) return;
    const res = await api.get(`/api/publish/oauth/status/${brandId}`);
    if (res.ok) {
      const data = res.data as OAuthStatusResponse;
      setYtConnected(data.youtube.connected);
      setYtChannelName(data.youtube.platform_user_name);
    }
  }, [brandId]);

  useEffect(() => {
    fetchYtStatus();
    return () => {
      if (connectionPollRef.current) clearInterval(connectionPollRef.current);
    };
  }, [fetchYtStatus]);

  const handleConnectYouTube = async () => {
    if (!brandId) return;
    setYtConnecting(true);
    const res = await api.post("/api/publish/oauth/connect", {
      brand_id: brandId,
      platform: "youtube",
    });
    if (!res.ok) { setYtConnecting(false); return; }
    const { auth_url } = res.data as { auth_url: string };
    openInBrowser(auth_url);

    connectionPollRef.current = setInterval(async () => {
      const sr = await api.get(`/api/publish/oauth/status/${brandId}`);
      if (!sr.ok) return;
      const d = sr.data as OAuthStatusResponse;
      if (d.youtube.connected) {
        if (connectionPollRef.current) clearInterval(connectionPollRef.current);
        connectionPollRef.current = null;
        setYtConnected(true);
        setYtChannelName(d.youtube.platform_user_name);
        setYtConnecting(false);
      }
    }, OAUTH_POLL_INTERVAL_MS);

    setTimeout(() => {
      if (connectionPollRef.current) {
        clearInterval(connectionPollRef.current);
        connectionPollRef.current = null;
        setYtConnecting(false);
      }
    }, OAUTH_CONNECT_TIMEOUT_MS);
  };

  const handleDisconnectYouTube = async () => {
    if (!brandId) return;
    await api.request("DELETE", "/api/publish/oauth/disconnect", {
      brand_id: brandId,
      platform: "youtube",
    });
    setYtConnected(false);
    setYtChannelName("");
  };

  // Parse active modifier IDs from the JSON string
  const activeModifierIds: string[] = (() => {
    try {
      const parsed = JSON.parse(form.content_modifiers || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  })();

  const toggleModifier = (id: string) => {
    const next = activeModifierIds.includes(id)
      ? activeModifierIds.filter((m) => m !== id)
      : [...activeModifierIds, id];
    setForm((prev) => ({ ...prev, content_modifiers: JSON.stringify(next) }));
  };

  const set = (field: keyof BrandProfileCreate, value: string) =>
    setForm((prev: BrandProfileCreate) => ({ ...prev, [field]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
  };

  const inputCls =
    "w-full h-[44px] rounded-lg bg-[#1a1a24] border border-white/[0.08] px-3 text-[13px] text-white/90 placeholder:text-white/40 placeholder:font-['JetBrains_Mono'] outline-none transition-all duration-200 focus:border-[rgba(124,58,237,0.6)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.15)]";

  const labelCls =
    "block text-[11px] font-medium tracking-[0.08em] uppercase text-white/40 mb-1.5 font-['Sora']";

  return (
    <form
      onSubmit={handleSubmit}
      className="min-h-screen"
      style={{ background: "#0a0a0f" }}
    >
      {/* ===== Sticky Header ===== */}
      <div
        className="sticky top-0 z-50 border-b border-white/[0.06] backdrop-blur-md"
        style={{ background: "rgba(10, 10, 15, 0.85)" }}
      >
        <div className="max-w-[600px] mx-auto px-10 py-4 flex items-center justify-between">
          <h1
            className="text-[22px] font-semibold text-white/95"
            style={{ fontFamily: "Sora, sans-serif" }}
          >
            {isEditing ? "Edit Brand Profile" : "Create Brand Profile"}
          </h1>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="px-5 py-2 rounded-lg text-[13px] font-medium text-white/50 hover:text-white/80 border border-white/[0.08] hover:border-white/[0.15] bg-transparent transition-all duration-200"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !form.name.trim()}
              className="px-5 py-2 rounded-lg text-[13px] font-semibold text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(124,58,237,0.3)]"
              style={{
                fontFamily: "Sora, sans-serif",
                background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              }}
            >
              {saving ? "Saving..." : "Save Brand"}
            </button>
          </div>
        </div>
      </div>

      {/* ===== Radial glow ===== */}
      <div className="relative">
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full pointer-events-none"
          style={{
            background: "radial-gradient(ellipse, rgba(124,58,237,0.06) 0%, transparent 70%)",
          }}
        />

        {/* ===== Single-column centered layout ===== */}
        <div className="max-w-[600px] mx-auto px-10 py-10 relative space-y-6">
          {/* ===== Brand Identity Card ===== */}
          <div
            className="rounded-xl p-6 space-y-6 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
            style={{
              background: "#111118",
              border: "1px solid rgba(255,255,255,0.06)",
              animation: "fadeUp 400ms ease both",
            }}
          >
            <h2
              className="text-[15px] font-semibold text-white/80 mb-1"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Brand Identity
            </h2>

            {/* Name */}
            <div>
              <label className={labelCls}>
                Brand / Channel Name <span className="text-red-400/80">*</span>
              </label>
              <input
                required
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                className={inputCls}
                placeholder="Everything Professor"
              />
            </div>
          </div>

          {/* ===== Default Voice Card ===== */}
          <div
            className="rounded-xl p-6 space-y-4 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
            style={{
              background: "#111118",
              border: "1px solid rgba(255,255,255,0.06)",
              borderLeft: "3px solid rgba(124,58,237,0.5)",
              animation: "fadeUp 400ms ease both",
              animationDelay: "60ms",
            }}
          >
            <div className="flex items-center gap-2">
              <Mic className="w-4 h-4 text-violet-400/70" />
              <h2
                className="text-[15px] font-semibold text-white/80"
                style={{ fontFamily: "Sora, sans-serif" }}
              >
                Default Voice
              </h2>
            </div>

            {/* Voice Dropdown */}
            <div>
              <label className={labelCls}>Voice</label>
              <select
                value={form.voice_id || ""}
                onChange={(e) => set("voice_id", e.target.value)}
                className={inputCls + " cursor-pointer"}
                style={{ appearance: "auto" }}
              >
                <option value="">Select a voice...</option>
                {voices.map((v) => (
                  <option key={v.voice_id} value={v.voice_id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Voice Cloning */}
            <div className="pt-3 border-t border-white/[0.06] space-y-4">
              <p className="text-[12px] text-white/35 leading-relaxed">
                Or clone a custom voice from audio samples:
              </p>

              <div>
                <label className={labelCls}>Voice Name</label>
                <input
                  value={cloneName}
                  onChange={(e) => setCloneName(e.target.value)}
                  className={inputCls}
                  placeholder={form.name || "My Brand Voice"}
                />
              </div>

              <div>
                <label className={labelCls}>
                  Audio Samples{" "}
                  <span className="normal-case tracking-normal text-white/25">
                    MP3, WAV, or M4A — up to {maxFiles} files
                  </span>
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mp3,.wav,.m4a"
                  multiple
                  onChange={(e) => addFiles(e.target.files)}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2.5 rounded-lg text-[12px] text-white/50 border border-dashed border-white/[0.15] hover:border-violet-400/40 hover:text-white/70 bg-transparent transition-all duration-200"
                  style={{ fontFamily: "Sora, sans-serif" }}
                >
                  Choose Files
                </button>

                {audioFiles.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {audioFiles.map((f, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.05] border border-white/[0.08] text-[11px] text-white/60"
                      >
                        <span className="truncate max-w-[120px]">{f.name}</span>
                        <button
                          type="button"
                          onClick={() => removeFile(i)}
                          className="text-white/30 hover:text-red-400 transition-colors"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {cloneError && (
                <p className="text-[12px] text-red-400/80">{cloneError}</p>
              )}

              <button
                type="button"
                disabled={cloning || audioFiles.length === 0}
                onClick={() => handleClone(form.name)}
                className="relative overflow-hidden px-5 py-2.5 rounded-lg text-[13px] font-semibold text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(124,58,237,0.3)]"
                style={{
                  fontFamily: "Sora, sans-serif",
                  background: "linear-gradient(135deg, #7c3aed, #a855f7)",
                }}
              >
                <span className="relative z-10">
                  {cloning ? "Cloning..." : "Clone Voice"}
                </span>
                {!cloning && audioFiles.length > 0 && (
                  <span
                    className="absolute inset-0 z-0"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.1) 50%, transparent 100%)",
                      backgroundSize: "200% 100%",
                      animation: "shimmer 2s infinite",
                    }}
                  />
                )}
              </button>
            </div>
          </div>

          {/* ===== Content Modifiers Card ===== */}
          {modifiers.length > 0 && (
            <div
              className="rounded-xl p-6 space-y-4 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
              style={{
                background: "#111118",
                border: "1px solid rgba(255,255,255,0.06)",
                animation: "fadeUp 400ms ease both",
                animationDelay: "120ms",
              }}
            >
              <h2
                className="text-[15px] font-semibold text-white/80 mb-1"
                style={{ fontFamily: "Sora, sans-serif" }}
              >
                Content Modifiers
              </h2>
              <p className="text-[12px] text-white/35 leading-relaxed">
                Enable plugins that change how scripts are generated and videos are rendered.
              </p>
              <div className="grid gap-3">
                {modifiers.map((mod) => {
                  const active = activeModifierIds.includes(mod.id);
                  return (
                    <button
                      key={mod.id}
                      type="button"
                      onClick={() => toggleModifier(mod.id)}
                      className={`flex items-start gap-3 p-3.5 rounded-lg border text-left transition-all duration-200 ${
                        active
                          ? "border-violet-500/40 bg-violet-500/[0.08]"
                          : "border-white/[0.06] bg-[#1a1a24] hover:border-white/[0.12]"
                      }`}
                    >
                      <span className="text-xl leading-none mt-0.5">{mod.icon}</span>
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-[13px] font-semibold ${
                            active ? "text-violet-300" : "text-white/80"
                          }`}
                          style={{ fontFamily: "Sora, sans-serif" }}
                        >
                          {mod.name}
                        </p>
                        <p className="text-[11px] text-white/35 mt-0.5 leading-relaxed">
                          {mod.description}
                        </p>
                      </div>
                      <div
                        className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 mt-0.5 transition-all duration-200 ${
                          active
                            ? "border-violet-500 bg-violet-500"
                            : "border-white/20 bg-transparent"
                        }`}
                      >
                        {active && (
                          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* ===== Platform Accounts Card ===== */}
          <div
            className="rounded-xl p-6 space-y-4 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
            style={{
              background: "#111118",
              border: "1px solid rgba(255,255,255,0.06)",
              animation: "fadeUp 400ms ease both",
              animationDelay: "180ms",
            }}
          >
            <h2
              className="text-[15px] font-semibold text-white/80"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Platform Accounts
            </h2>

            {/* YouTube Channel ID */}
            <div>
              <label className={labelCls}>
                <span className="inline-flex items-center gap-1.5">
                  <YouTubeIcon className="w-3.5 h-3.5 text-red-400/60" />
                  YouTube Channel ID
                </span>
              </label>
              <div className="relative">
                <input
                  value={form.youtube_channel_id || ""}
                  onChange={(e) => set("youtube_channel_id", e.target.value)}
                  className={inputCls + " font-['JetBrains_Mono']"}
                  placeholder="UCxxxxx"
                />
                {form.youtube_channel_id && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400/80 font-medium tracking-wide">
                    Connected
                  </span>
                )}
              </div>
            </div>

            {/* YouTube OAuth (only in edit mode) */}
            {isEditing && (
              <div className="pt-3 border-t border-white/[0.06]">
                <label className={labelCls}>
                  <span className="inline-flex items-center gap-1.5">
                    <YouTubeIcon className="w-3.5 h-3.5 text-red-400/60" />
                    YouTube Account
                  </span>
                </label>
                {ytConnected ? (
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center gap-1.5 text-[13px] text-emerald-400/90">
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                      {ytChannelName}
                    </span>
                    <button
                      type="button"
                      onClick={handleDisconnectYouTube}
                      className="text-[11px] text-white/30 hover:text-red-400 transition-colors duration-200"
                    >
                      Disconnect
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={handleConnectYouTube}
                    disabled={ytConnecting}
                    className="px-4 py-2.5 rounded-lg text-[12px] font-medium text-white transition-all duration-200 flex items-center gap-2 hover:opacity-90 disabled:opacity-50"
                    style={{
                      fontFamily: "Sora, sans-serif",
                      background: "#dc2626",
                    }}
                  >
                    {ytConnecting ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                        Connecting...
                      </>
                    ) : (
                      <>
                        <YouTubeIcon className="w-4 h-4" />
                        Connect YouTube Account
                      </>
                    )}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}
