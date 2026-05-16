import { useCallback, useEffect, useState } from "react";
import { getRenderedShortsStatus } from "../../../api";
import RenderShortsCard from "./RenderShortsCard";

interface Props {
  scriptId: string;
  segments: { name: string }[];
}

export default function ShortFormTab({
  scriptId,
  segments,
}: Props) {
  const [renderedUrls, setRenderedUrls] = useState<Record<number, string | undefined>>({});
  const [downloadsUrls, setDownloadsUrls] = useState<Record<number, string | undefined>>({});

  const probeRenderedShorts = useCallback(async () => {
    const status = await getRenderedShortsStatus(scriptId);
    return status.paths;
  }, [scriptId]);

  const refreshRenderedShorts = useCallback(async () => {
    const found = await probeRenderedShorts();
    setRenderedUrls(found);
    setDownloadsUrls(found);
    return found;
  }, [probeRenderedShorts]);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      const found = await probeRenderedShorts();
      if (!cancelled) {
        setRenderedUrls(found);
        setDownloadsUrls(found);
      }
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
        downloadsUrls={downloadsUrls}
        onRefreshRendered={refreshRenderedShorts}
        onRenderComplete={(idx, url) => {
          setRenderedUrls((prev) => ({ ...prev, [idx]: url }));
          setDownloadsUrls((prev) => ({ ...prev, [idx]: url }));
        }}
      />
    </div>
  );
}
