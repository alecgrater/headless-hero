import { useEffect, useState } from "react";
import api from "../../api";
import type { VoiceInfo, VoiceListResponse } from "../../types/audio";
import { Mic, X } from "lucide-react";
import useVoiceCloning from "./useVoiceCloning";

interface Props {
  brandName: string;
  onVoiceSelected: (voiceId: string) => void;
  onClose: () => void;
}

export default function VoiceSetupModal({ brandName, onVoiceSelected, onClose }: Props) {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState("");
  const [tab, setTab] = useState<"select" | "clone">("select");

  const {
    audioFiles, cloneName, setCloneName, cloning, cloneError,
    fileInputRef, addFiles, removeFile, handleClone, maxFiles,
  } = useVoiceCloning({
    defaultName: brandName,
    onCloned: (voiceId) => onVoiceSelected(voiceId),
  });

  useEffect(() => {
    api.get("/api/voice/voices").then((res) => {
      if (res.ok) {
        const data = res.data as VoiceListResponse;
        const sorted = [...data.voices].sort((a, b) => {
          const priority = (v: VoiceInfo) => {
            const n = v.name.toLowerCase();
            if (n.startsWith("ben")) return 0;
            if (n.startsWith("liam")) return 1;
            return 2;
          };
          return priority(a) - priority(b) || a.name.localeCompare(b.name);
        });
        setVoices(sorted);
        if (data.voices.length > 0) {
          setSelectedVoiceId(data.voices[0].voice_id);
        } else {
          setTab("clone");
        }
      }
    });
  }, []);

  const handleSelectAndContinue = () => {
    if (selectedVoiceId) {
      onVoiceSelected(selectedVoiceId);
    }
  };

  const handleCloneClick = () => handleClone(brandName);

  const inputCls =
    "w-full h-[44px] rounded-lg bg-neutral-900 border border-white/[0.08] px-3 text-[13px] text-white/90 placeholder:text-white/40 outline-none transition-all duration-200 focus:border-violet-600/60 focus:ring-3 focus:ring-violet-500/15";

  const labelCls =
    "block text-[11px] font-medium tracking-[0.08em] uppercase text-white/40 mb-1.5 font-['Sora']";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-[480px] rounded-xl overflow-hidden border border-white/[0.08] shadow-[0_20px_60px_rgba(0,0,0,0.5)] bg-[#111118]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <Mic className="w-4 h-4 text-violet-400/70" />
            <h2
              className="text-[16px] font-semibold text-white/90"
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Voice Setup
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-white/30 hover:text-white/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded-md"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p
          className="px-6 pt-4 text-[13px] text-white/50"
          style={{ fontFamily: "Sora, sans-serif" }}
        >
          Select a voice or clone a new one to generate audio.
        </p>

        {/* Tab bar */}
        <div className="flex gap-1 px-6 pt-4">
          {voices.length > 0 && (
            <button
              type="button"
              onClick={() => setTab("select")}
              className={`px-4 py-1.5 rounded-lg text-[12px] font-medium transition-all duration-200 ${
                tab === "select"
                  ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                  : "text-white/40 hover:text-white/60 border border-transparent"
              }`}
              style={{ fontFamily: "Sora, sans-serif" }}
            >
              Select Voice
            </button>
          )}
          <button
            type="button"
            onClick={() => setTab("clone")}
            className={`px-4 py-1.5 rounded-lg text-[12px] font-medium transition-all duration-200 ${
              tab === "clone"
                ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                : "text-white/40 hover:text-white/60 border border-transparent"
            }`}
            style={{ fontFamily: "Sora, sans-serif" }}
          >
            Clone Voice
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-4">
          {tab === "select" && voices.length > 0 && (
            <>
              <div>
                <label className={labelCls}>Available Voices</label>
                <select
                  value={selectedVoiceId}
                  onChange={(e) => setSelectedVoiceId(e.target.value)}
                  className={inputCls + " cursor-pointer"}
                >
                  {voices.map((v) => (
                    <option key={v.voice_id} value={v.voice_id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={handleSelectAndContinue}
                disabled={!selectedVoiceId}
                className="w-full px-5 py-2.5 rounded-lg text-[13px] font-semibold text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 hover:scale-[1.01] bg-gradient-to-br from-violet-600 to-violet-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
                style={{ fontFamily: "Sora, sans-serif" }}
              >
                Use This Voice
              </button>
            </>
          )}

          {tab === "clone" && (
            <>
              <div>
                <label className={labelCls}>Voice Name</label>
                <input
                  value={cloneName}
                  onChange={(e) => setCloneName(e.target.value)}
                  className={inputCls}
                  placeholder={brandName || "My Brand Voice"}
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
                onClick={handleCloneClick}
                className="w-full relative overflow-hidden px-5 py-2.5 rounded-lg text-[13px] font-semibold text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 hover:scale-[1.01]"
                style={{
                  fontFamily: "Sora, sans-serif",
                  background: "linear-gradient(135deg, #7c3aed, #a855f7)",
                }}
              >
                <span className="relative z-10">
                  {cloning ? "Cloning..." : "Clone & Continue"}
                </span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
