import { useCallback, useEffect, useRef, useState } from "react";
import api, { openInBrowser } from "../../api";
import { cloneVoice } from "../../api";
import type { BrandProfile, BrandProfileCreate } from "../../types/brand";
import type { OAuthStatusResponse } from "../../types/publish";
import { Mic, X } from "lucide-react";

interface Props {
  brand: BrandProfile;
  onUpdate: (data: BrandProfileCreate) => Promise<void>;
  onBack: () => void;
}

/* ---- Icon subcomponents ---- */

function TikTokIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 00-.79-.05A6.34 6.34 0 003.15 15.2a6.34 6.34 0 0010.86 4.46v-7.07a8.16 8.16 0 005.58 2.18v-3.45a4.84 4.84 0 01-3.77-1.86V6.69h3.77z" />
    </svg>
  );
}

function YouTubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
    </svg>
  );
}

export default function BrandSettings({ brand, onUpdate, onBack }: Props) {
  const [saving, setSaving] = useState(false);

  // Voice cloning state
  const [audioFiles, setAudioFiles] = useState<File[]>([]);
  const [cloneName, setCloneName] = useState(brand.name);
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState<string | null>(null);
  const [voiceId, setVoiceId] = useState(brand.voice_id);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Platform state
  const [youtubeChannelId, setYoutubeChannelId] = useState(brand.youtube_channel_id);
  const [tiktokHandle, setTiktokHandle] = useState(brand.tiktok_handle);
  const [instagramHandle, setInstagramHandle] = useState(brand.instagram_handle);

  // YouTube OAuth
  const [ytConnected, setYtConnected] = useState(false);
  const [ytChannelName, setYtChannelName] = useState("");
  const [ytConnecting, setYtConnecting] = useState(false);
  const connectionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchYtStatus = useCallback(async () => {
    const res = await api.get(`/api/publish/oauth/status/${brand.id}`);
    if (res.ok) {
      const data = res.data as OAuthStatusResponse;
      setYtConnected(data.youtube.connected);
      setYtChannelName(data.youtube.platform_user_name);
    }
  }, [brand.id]);

  useEffect(() => {
    fetchYtStatus();
    return () => {
      if (connectionPollRef.current) clearInterval(connectionPollRef.current);
    };
  }, [fetchYtStatus]);

  const handleConnectYouTube = async () => {
    setYtConnecting(true);
    const res = await api.post("/api/publish/oauth/connect", {
      brand_id: brand.id,
      platform: "youtube",
    });
    if (!res.ok) { setYtConnecting(false); return; }
    const { auth_url } = res.data as { auth_url: string };
    openInBrowser(auth_url);

    connectionPollRef.current = setInterval(async () => {
      const sr = await api.get(`/api/publish/oauth/status/${brand.id}`);
      if (!sr.ok) return;
      const d = sr.data as OAuthStatusResponse;
      if (d.youtube.connected) {
        if (connectionPollRef.current) clearInterval(connectionPollRef.current);
        connectionPollRef.current = null;
        setYtConnected(true);
        setYtChannelName(d.youtube.platform_user_name);
        setYtConnecting(false);
      }
    }, 2000);

    setTimeout(() => {
      if (connectionPollRef.current) {
        clearInterval(connectionPollRef.current);
        connectionPollRef.current = null;
        setYtConnecting(false);
      }
    }, 300000);
  };

  const handleDisconnectYouTube = async () => {
    await api.request("DELETE", "/api/publish/oauth/disconnect", {
      brand_id: brand.id,
      platform: "youtube",
    });
    setYtConnected(false);
    setYtChannelName("");
  };

  const removeAudioFile = (index: number) => {
    setAudioFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate({
        name: brand.name,
        voice_id: voiceId,
        youtube_channel_id: youtubeChannelId,
        tiktok_handle: tiktokHandle,
        instagram_handle: instagramHandle,
      });
    } finally {
      setSaving(false);
    }
  };

  const inputCls =
    "w-full h-[44px] rounded-lg bg-[#1a1a24] border border-white/[0.08] px-3 text-[13px] text-white/90 placeholder:text-white/40 placeholder:font-['JetBrains_Mono'] outline-none transition-all duration-200 focus:border-[rgba(124,58,237,0.6)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.15)]";

  const labelCls =
    "block text-[11px] font-medium tracking-[0.08em] uppercase text-white/40 mb-1.5 font-['Sora']";

  return (
    <div className="min-h-screen" style={{ background: "#0a0a0f" }}>
      {/* Sticky Header */}
      <div
        className="sticky top-0 z-50 border-b border-white/[0.06] backdrop-blur-md"
        style={{ background: "rgba(10, 10, 15, 0.85)" }}
      >
        <div className="max-w-[600px] mx-auto px-10 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBack}
              className="px-3 py-2 rounded-lg text-[13px] font-medium text-white/50 hover:text-white/80 border border-white/[0.08] hover:border-white/[0.15] bg-transparent transition-all duration-200"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              &larr; Back
            </button>
            <h1
              className="text-[22px] font-semibold text-white/95"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              {brand.name} Settings
            </h1>
          </div>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-lg text-[13px] font-semibold text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(124,58,237,0.3)]"
            style={{
              fontFamily: "Sora, sans-serif",
              background: "linear-gradient(135deg, #7c3aed, #a855f7)",
            }}
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Radial glow */}
      <div className="relative">
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full pointer-events-none"
          style={{
            background: "radial-gradient(ellipse, rgba(124,58,237,0.06) 0%, transparent 70%)",
          }}
        />

        <div className="max-w-[600px] mx-auto px-10 py-10 relative space-y-6">
          {/* Voice Cloning Card */}
          <div
            className="rounded-xl p-6 space-y-4 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
            style={{
              background: "#111118",
              border: "1px solid rgba(255,255,255,0.06)",
              borderLeft: "3px solid rgba(124,58,237,0.5)",
              animation: "fadeUp 400ms ease both",
            }}
          >
            <div className="flex items-center gap-2">
              <Mic className="w-4 h-4 text-violet-400/70" />
              <h2
                className="text-[15px] font-semibold text-white/80"
                style={{ fontFamily: "Sora, sans-serif" }}
              >
                Voice Cloning
              </h2>
            </div>

            {voiceId ? (
              <div className="flex items-center gap-3">
                <span className="text-[13px] text-emerald-400/90">
                  Cloned voice:{" "}
                  <code className="bg-white/[0.05] px-1.5 py-0.5 rounded text-[11px] font-['JetBrains_Mono']">
                    {voiceId}
                  </code>
                </span>
                <button
                  type="button"
                  onClick={() => setVoiceId("")}
                  className="text-[11px] text-white/30 hover:text-red-400 transition-colors duration-200"
                >
                  Remove
                </button>
              </div>
            ) : (
              <>
                <div>
                  <label className={labelCls}>Voice Name</label>
                  <input
                    value={cloneName}
                    onChange={(e) => setCloneName(e.target.value)}
                    className={inputCls}
                    placeholder={brand.name || "My Brand Voice"}
                  />
                </div>

                <div>
                  <label className={labelCls}>
                    Audio Samples{" "}
                    <span className="normal-case tracking-normal text-white/25">
                      MP3, WAV, or M4A — up to 5 files
                    </span>
                  </label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".mp3,.wav,.m4a"
                    multiple
                    onChange={(e) => {
                      const files = Array.from(e.target.files || []).slice(0, 5);
                      setAudioFiles(files);
                      setCloneError(null);
                    }}
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
                            onClick={() => removeAudioFile(i)}
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
                  onClick={async () => {
                    setCloning(true);
                    setCloneError(null);
                    try {
                      const result = await cloneVoice(
                        cloneName || brand.name || "Cloned Voice",
                        audioFiles,
                      );
                      setVoiceId(result.voice_id);
                      setAudioFiles([]);
                    } catch (err: unknown) {
                      setCloneError(
                        err instanceof Error ? err.message : "Voice cloning failed",
                      );
                    } finally {
                      setCloning(false);
                    }
                  }}
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
              </>
            )}

            <p
              className="text-[12px] text-white/25"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Upload voice samples for a custom ElevenLabs clone, or pick a
              prebuilt voice later.
            </p>
          </div>

          {/* Platform Accounts Card */}
          <div
            className="rounded-xl p-6 space-y-4 transition-all duration-250 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
            style={{
              background: "#111118",
              border: "1px solid rgba(255,255,255,0.06)",
              animation: "fadeUp 400ms ease both",
              animationDelay: "80ms",
            }}
          >
            <h2
              className="text-[15px] font-semibold text-white/80"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Platform Accounts
            </h2>

            {/* YouTube */}
            <div>
              <label className={labelCls}>
                <span className="inline-flex items-center gap-1.5">
                  <YouTubeIcon className="w-3.5 h-3.5 text-red-400/60" />
                  YouTube Channel ID
                </span>
              </label>
              <div className="relative">
                <input
                  value={youtubeChannelId}
                  onChange={(e) => setYoutubeChannelId(e.target.value)}
                  className={inputCls + " font-['JetBrains_Mono']"}
                  placeholder="UCxxxxx"
                />
                {youtubeChannelId && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400/80 font-medium tracking-wide">
                    Connected
                  </span>
                )}
              </div>
            </div>

            {/* TikTok */}
            <div>
              <label className={labelCls}>
                <span className="inline-flex items-center gap-1.5">
                  <TikTokIcon className="w-3.5 h-3.5 text-white/40" />
                  TikTok Handle
                </span>
              </label>
              <input
                value={tiktokHandle}
                onChange={(e) => setTiktokHandle(e.target.value)}
                className={inputCls}
                placeholder="@myhandle"
              />
            </div>

            {/* Instagram */}
            <div>
              <label className={labelCls}>
                <span className="inline-flex items-center gap-1.5">
                  <InstagramIcon className="w-3.5 h-3.5 text-pink-400/50" />
                  Instagram Handle
                </span>
              </label>
              <input
                value={instagramHandle}
                onChange={(e) => setInstagramHandle(e.target.value)}
                className={inputCls}
                placeholder="@myhandle"
              />
            </div>

            {/* YouTube OAuth */}
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
          </div>
        </div>
      </div>
    </div>
  );
}
