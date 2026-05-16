import { useEffect, useState } from "react";
import { assetUrl } from "../../../api";
import RenderShortsCard from "./RenderShortsCard";

interface Props {
  scriptId: string;
  segments: { name: string }[];
  initialRenderedUrls?: Record<number, string | undefined>;
}

export default function ShortFormTab({
  scriptId,
  segments,
  initialRenderedUrls,
}: Props) {
  const [renderedUrls, setRenderedUrls] = useState<Record<number, string | undefined>>(
    initialRenderedUrls ?? {},
  );

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
        Renders {segments.length} short form videos, one per segment. 1080×1920 9:16 30FPS.
      </p>

      <RenderShortsCard
        scriptId={scriptId}
        segments={segments}
        renderedUrls={renderedUrls}
        onRenderComplete={(idx, url) =>
          setRenderedUrls((prev) => ({ ...prev, [idx]: url }))
        }
      />
    </div>
  );
}
