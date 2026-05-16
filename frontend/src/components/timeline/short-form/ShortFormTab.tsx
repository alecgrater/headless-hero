import { useCallback, useEffect, useState } from "react";
import { getRenderedShortsStatus, getShortFormUploadStatus } from "../../../api";
import api from "../../../api";
import type { OAuthStatusResponse, ShortUploadStatus } from "../../../types/publish";
import type { ShortFormSEOMetadata } from "../../../types/render";
import RenderShortsCard from "./RenderShortsCard";

interface Props {
  scriptId: string;
  segments: { name: string }[];
  shortFormSeoMetadata: ShortFormSEOMetadata | null;
}

export default function ShortFormTab({
  scriptId,
  segments,
  shortFormSeoMetadata,
}: Props) {
  const [renderedUrls, setRenderedUrls] = useState<Record<number, string | undefined>>({});
  const [downloadsUrls, setDownloadsUrls] = useState<Record<number, string | undefined>>({});
  const [connections, setConnections] = useState<OAuthStatusResponse | null>(null);
  const [uploadStatuses, setUploadStatuses] = useState<Record<number, ShortUploadStatus>>({});

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

  const refreshUploadStatuses = useCallback(async () => {
    const found = await getShortFormUploadStatus(scriptId);
    setUploadStatuses(found);
    return found;
  }, [scriptId]);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      try {
        const found = await probeRenderedShorts();
        if (!cancelled) {
          setRenderedUrls(found);
          setDownloadsUrls(found);
        }
      } catch {
        if (!cancelled) {
          setRenderedUrls({});
          setDownloadsUrls({});
        }
      }
    }
    probe();
    return () => {
      cancelled = true;
    };
  }, [probeRenderedShorts]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [connectionRes, statuses] = await Promise.all([
        api.get("/api/publish/oauth/status"),
        getShortFormUploadStatus(scriptId).catch(() => ({})),
      ]);
      if (cancelled) return;
      if (connectionRes.ok) setConnections(connectionRes.data as OAuthStatusResponse);
      setUploadStatuses(statuses);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [scriptId]);

  return (
    <div className="space-y-4">
      <RenderShortsCard
        scriptId={scriptId}
        segments={segments}
        renderedUrls={renderedUrls}
        downloadsUrls={downloadsUrls}
        connections={connections}
        uploadStatuses={uploadStatuses}
        shortFormSeoMetadata={shortFormSeoMetadata}
        onRefreshRendered={refreshRenderedShorts}
        onRefreshUploads={refreshUploadStatuses}
        onRenderComplete={(idx, url) => {
          setRenderedUrls((prev) => ({ ...prev, [idx]: url }));
          setDownloadsUrls((prev) => ({ ...prev, [idx]: url }));
        }}
      />
    </div>
  );
}
