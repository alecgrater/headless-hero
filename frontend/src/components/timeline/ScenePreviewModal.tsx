import { useCallback, useEffect, useRef, useState } from "react";
import type { Scene } from "../../types/script";
import { assetUrl, renderScenePreview } from "../../api";
import { usePollJob } from "../../hooks/usePollJob";
import api from "../../api";
import AudioPlayer from "./AudioPlayer";

interface Props {
  scene: Scene;
  sceneIndex: number;
  scriptId: string;
  onClose: () => void;
}

type Tab = "assets" | "playback";

interface RenderStatus {
  status: string;
  progress: number;
  current_step: string;
  output_urls: string[];
  error: string | null;
}

export default function ScenePreviewModal({ scene, sceneIndex, scriptId, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("assets");

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8" onClick={onClose}>
      <div
        className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800">
          <h2 className="text-lg font-semibold text-neutral-100">Preview — Scene {sceneIndex + 1}</h2>
          <button
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-300 transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 px-6 pt-3">
          {(["assets", "playback"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 text-sm rounded-lg transition-colors ${
                tab === t
                  ? "bg-violet-600 text-white font-medium"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
              }`}
            >
              {t === "assets" ? "Assets" : "Playback"}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {tab === "assets" ? (
            <AssetsTab scene={scene} />
          ) : (
            <PlaybackTab scene={scene} scriptId={scriptId} />
          )}
        </div>
      </div>
    </div>
  );
}

function AssetsTab({ scene }: { scene: Scene }) {
  const hasVideo = !!scene.video_url;
  const hasFrames = scene.frame_urls && scene.frame_urls.length > 0;
  const hasImage = !!scene.image_url;
  const hasAudio = !!scene.audio_url;

  return (
    <div className="space-y-4">
      {/* Video */}
      {hasVideo && (
        <div>
          <p className="text-xs text-neutral-500 mb-1.5">Video</p>
          <video
            src={assetUrl(scene.video_url!)}
            controls
            className="w-full rounded-lg bg-black"
          />
        </div>
      )}

      {/* Images */}
      {!hasVideo && hasFrames && (
        <div>
          <p className="text-xs text-neutral-500 mb-1.5">Frames ({scene.frame_urls!.length})</p>
          <div className="grid grid-cols-3 gap-2">
            {scene.frame_urls!.map((url, i) => (
              <img
                key={i}
                src={assetUrl(url)}
                alt={`Frame ${i + 1}`}
                className="rounded-lg bg-neutral-800 aspect-video object-cover w-full"
              />
            ))}
          </div>
        </div>
      )}

      {!hasVideo && !hasFrames && hasImage && (
        <div>
          <p className="text-xs text-neutral-500 mb-1.5">Image</p>
          <img
            src={assetUrl(scene.image_url!)}
            alt="Scene visual"
            className="w-full rounded-lg bg-neutral-800 aspect-video object-cover"
          />
        </div>
      )}

      {/* Audio */}
      {hasAudio && (
        <div>
          <p className="text-xs text-neutral-500 mb-1.5">Audio</p>
          <AudioPlayer src={assetUrl(scene.audio_url!)} duration={scene.audio_duration_seconds} />
        </div>
      )}

      {/* Narration */}
      {scene.narration && (
        <div>
          <p className="text-xs text-neutral-500 mb-1.5">Narration</p>
          <p className="text-sm text-neutral-300 leading-relaxed">{scene.narration}</p>
        </div>
      )}
    </div>
  );
}

function PlaybackTab({ scene, scriptId }: { scene: Scene; scriptId: string }) {
  const hasVideo = !!scene.video_url;
  const hasAudio = !!scene.audio_url;

  const [renderProgress, setRenderProgress] = useState(0);
  const [renderStep, setRenderStep] = useState("");
  const [renderedUrl, setRenderedUrl] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);

  const { startPolling, stopPolling } = usePollJob<RenderStatus>({
    pollFn: async (jobId) => {
      const res = await api.get(`/api/render/status/${jobId}`);
      if (!res.ok) return null;
      return res.data as RenderStatus;
    },
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (s) => {
      setRenderProgress(s.progress);
      setRenderStep(s.current_step);
      if (s.status === "completed" && s.output_urls.length > 0) {
        setRenderedUrl(s.output_urls[0]);
        setRendering(false);
      }
      if (s.status === "failed") {
        setRenderError(s.error || "Render failed");
        setRendering(false);
      }
    },
    onConnectionLost: () => {
      setRenderError("Lost connection to backend");
      setRendering(false);
    },
  });

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const handleRenderHD = async () => {
    setRendering(true);
    setRenderError(null);
    setRenderedUrl(null);
    setRenderProgress(0);
    try {
      const { job_id } = await renderScenePreview(scriptId, scene.id);
      startPolling(job_id);
    } catch (err) {
      setRenderError(err instanceof Error ? err.message : "Failed to start render");
      setRendering(false);
    }
  };

  if (renderedUrl) {
    return (
      <div className="space-y-3">
        <video
          src={assetUrl(renderedUrl)}
          controls
          autoPlay
          className="w-full rounded-lg bg-black"
        />
        <p className="text-xs text-neutral-500">HD render complete</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Crossfade player or video */}
      {hasVideo ? (
        <video
          src={assetUrl(scene.video_url!)}
          controls
          className="w-full rounded-lg bg-black"
        />
      ) : hasAudio ? (
        <CrossfadePlayer scene={scene} />
      ) : (
        <div className="aspect-video bg-neutral-800 rounded-lg flex items-center justify-center">
          <span className="text-sm text-neutral-500">No audio for playback</span>
        </div>
      )}

      {/* Render HD section */}
      <div className="border-t border-neutral-800 pt-4">
        {renderError && (
          <p className="text-xs text-red-400 mb-2">{renderError}</p>
        )}
        {rendering ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-neutral-400">
              <span>{renderStep || "Starting render..."}</span>
              <span>{Math.round(renderProgress * 100)}%</span>
            </div>
            <div className="h-1.5 bg-neutral-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-violet-500 rounded-full transition-[width] duration-300"
                style={{ width: `${renderProgress * 100}%` }}
              />
            </div>
          </div>
        ) : (
          <button
            onClick={handleRenderHD}
            className="px-4 py-2 text-sm bg-violet-600 hover:bg-violet-500 rounded-lg transition-colors text-white font-medium"
          >
            Render HD
          </button>
        )}
      </div>
    </div>
  );
}

function CrossfadePlayer({ scene }: { scene: Scene }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const rafRef = useRef<number>(0);
  const [playing, setPlaying] = useState(false);
  const [activeFrame, setActiveFrame] = useState(0);

  const frames = scene.frame_urls && scene.frame_urls.length > 0
    ? scene.frame_urls
    : scene.image_url
      ? [scene.image_url]
      : [];

  const duration = scene.audio_duration_seconds || 0;
  const timings = scene.frame_timings;

  const getFrameIndex = useCallback((currentTime: number) => {
    if (frames.length <= 1) return 0;
    if (timings && timings.length > 0) {
      for (let i = timings.length - 1; i >= 0; i--) {
        if (currentTime >= timings[i]) return Math.min(i, frames.length - 1);
      }
      return 0;
    }
    if (duration <= 0) return 0;
    const interval = duration / frames.length;
    return Math.min(Math.floor(currentTime / interval), frames.length - 1);
  }, [frames.length, timings, duration]);

  const tick = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || audio.paused) return;
    setActiveFrame(getFrameIndex(audio.currentTime));
    rafRef.current = requestAnimationFrame(tick);
  }, [getFrameIndex]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => setPlaying(false));
      setPlaying(true);
      rafRef.current = requestAnimationFrame(tick);
    } else {
      audio.pause();
      setPlaying(false);
      cancelAnimationFrame(rafRef.current);
    }
  };

  const handleEnded = () => {
    setPlaying(false);
    setActiveFrame(0);
    cancelAnimationFrame(rafRef.current);
  };

  const restart = () => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = 0;
    setActiveFrame(0);
    audio.play().catch(() => setPlaying(false));
    setPlaying(true);
    rafRef.current = requestAnimationFrame(tick);
  };

  useEffect(() => {
    return () => {
      cancelAnimationFrame(rafRef.current);
      audioRef.current?.pause();
    };
  }, []);

  if (frames.length === 0) {
    return (
      <div className="aspect-video bg-neutral-800 rounded-lg flex items-center justify-center">
        <span className="text-sm text-neutral-500">No visuals available</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Visual area */}
      <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
        {frames.map((url, i) => (
          <img
            key={i}
            src={assetUrl(url)}
            alt={`Frame ${i + 1}`}
            className="absolute inset-0 w-full h-full object-cover transition-opacity duration-500"
            style={{ opacity: i === activeFrame ? 1 : 0 }}
          />
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <audio
          ref={audioRef}
          src={assetUrl(scene.audio_url!)}
          preload="auto"
          onEnded={handleEnded}
        />
        <button
          onClick={togglePlay}
          className="w-8 h-8 flex items-center justify-center rounded-full bg-violet-500 hover:bg-violet-400 transition-colors shrink-0"
        >
          {playing ? (
            <svg width="10" height="12" viewBox="0 0 10 12" fill="white">
              <rect x="0" y="0" width="3" height="12" rx="1" />
              <rect x="7" y="0" width="3" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="10" height="12" viewBox="0 0 10 12" fill="white">
              <polygon points="0,0 10,6 0,12" />
            </svg>
          )}
        </button>
        <button
          onClick={restart}
          className="text-xs text-neutral-400 hover:text-neutral-200 transition-colors"
        >
          Restart
        </button>
        {frames.length > 1 && (
          <span className="text-xs text-neutral-500 ml-auto">
            Frame {activeFrame + 1}/{frames.length}
          </span>
        )}
      </div>
    </div>
  );
}
