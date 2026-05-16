import { useCallback, useEffect, useState } from "react";
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

  const probeRenderedShorts = useCallback(async () => {
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
    return found;
  }, [scriptId, segments.length]);

  const refreshRenderedShorts = useCallback(async () => {
    const found = await probeRenderedShorts();
    setRenderedUrls(found);
    return found;
  }, [probeRenderedShorts]);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      const found = await probeRenderedShorts();
      if (!cancelled) setRenderedUrls(found);
    }
    probe();
    return () => {
      cancelled = true;
    };
  }, [probeRenderedShorts]);

  return (
    <div className="space-y-4">
      <RenderShortsCard
        scriptId={scriptId}
        segments={segments}
        renderedUrls={renderedUrls}
        onRefreshRendered={refreshRenderedShorts}
        onRenderComplete={(idx, url) =>
          setRenderedUrls((prev) => ({ ...prev, [idx]: url }))
        }
      />
    </div>
  );
}
