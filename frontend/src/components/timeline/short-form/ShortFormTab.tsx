import { useEffect, useRef, useState } from "react";
import { assetUrl } from "../../../api";
import type { ShortIntro } from "../../../types/render";
import ShortIntrosCard from "./ShortIntrosCard";
import RenderShortsCard from "./RenderShortsCard";

interface Props {
  scriptId: string;
  videoTitle: string;
  segments: { name: string }[];
  intros: ShortIntro[] | null | undefined;
  onIntrosChanged: () => void;
  initialRenderedUrls?: Record<number, string | undefined>;
  hookSceneCount?: number | null;
}

export default function ShortFormTab({
  scriptId,
  videoTitle,
  segments,
  intros,
  onIntrosChanged,
  initialRenderedUrls,
  hookSceneCount,
}: Props) {
  const introsRef = useRef<HTMLDivElement>(null);
  const [renderedUrls, setRenderedUrls] = useState<Record<number, string | undefined>>(
    initialRenderedUrls ?? {},
  );

  const introsReady =
    !!intros && intros.length === segments.length && segments.length > 0;

  // Hydrate rendered URLs from disk on mount by checking the expected static paths.
  // Uses assetUrl() to build the full http://localhost:PORT URL — required in Electron
  // where the renderer runs from file:// and relative /static/... paths don't resolve.
  useEffect(() => {
    let cancelled = false;
    async function probe() {
      const found: Record<number, string | undefined> = {};
      for (let i = 0; i < segments.length; i++) {
        const path = `/static/projects/${scriptId}/renders/shorts/${i}.mp4`;
        try {
          const r = await fetch(assetUrl(path), { method: "HEAD" });
          if (r.ok) found[i] = path;
        } catch {
          /* ignore */
        }
      }
      if (!cancelled) setRenderedUrls((prev) => ({ ...prev, ...found }));
    }
    probe();
    return () => {
      cancelled = true;
    };
  }, [scriptId, segments.length]);

  return (
    <div className="space-y-4">
      <p className="text-xs text-neutral-500">
        Renders 8 short form videos, corresponding to the 8 segments. 1080x1920 9:16 30FPS
      </p>

      <div ref={introsRef}>
        <ShortIntrosCard
          scriptId={scriptId}
          videoTitle={videoTitle}
          segments={segments}
          intros={intros}
          onIntrosChanged={onIntrosChanged}
          hookSceneCount={hookSceneCount}
        />
      </div>

      <RenderShortsCard
        scriptId={scriptId}
        introsReady={introsReady}
        segments={segments}
        renderedUrls={renderedUrls}
        onRenderComplete={(idx, url) =>
          setRenderedUrls((prev) => ({ ...prev, [idx]: url }))
        }
        onRequestGenerateIntros={() => {
          introsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }}
      />
    </div>
  );
}
