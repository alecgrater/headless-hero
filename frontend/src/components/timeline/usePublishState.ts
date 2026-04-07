import { useCallback, useEffect, useRef, useState } from "react";
import api, { openInBrowser } from "../../api";
import type {
  ConnectResponse,
  OAuthStatusResponse,
  PlatformConnection,
  PublishRecord,
} from "../../types/publish";
import type { RenderStatusResponse } from "../../types/render";

export interface PublishState {
  // Connection status
  connections: OAuthStatusResponse | null;
  youtubeConnected: boolean;
  youtubeChannelName: string;
  connectPlatform: (platform: string) => Promise<void>;
  disconnectPlatform: (platform: string) => Promise<void>;
  connecting: boolean;

  // Upload
  publishJobId: string | null;
  publishStatus: RenderStatusResponse | null;
  startPublish: (
    platform: string,
    fileUrl: string,
    metadata: { title: string; description: string; tags: string[] },
    scheduleAt?: string,
  ) => Promise<void>;

  // History
  publishHistory: PublishRecord[];
  refreshHistory: () => Promise<void>;
}

export function usePublishState(scriptId: string, brandId: string): PublishState {
  const [connections, setConnections] = useState<OAuthStatusResponse | null>(null);
  const [connecting, setConnecting] = useState(false);

  const [publishJobId, setPublishJobId] = useState<string | null>(null);
  const [publishStatus, setPublishStatus] = useState<RenderStatusResponse | null>(null);

  const [publishHistory, setPublishHistory] = useState<PublishRecord[]>([]);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const connectionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch connection status
  const fetchConnections = useCallback(async () => {
    if (!brandId) return;
    const res = await api.get(`/api/publish/oauth/status/${brandId}`);
    if (res.ok) {
      setConnections(res.data as OAuthStatusResponse);
    }
  }, [brandId]);

  // Fetch publish history
  const refreshHistory = useCallback(async () => {
    if (!scriptId) return;
    const res = await api.get(`/api/publish/history/${scriptId}`);
    if (res.ok) {
      setPublishHistory(res.data as PublishRecord[]);
    }
  }, [scriptId]);

  // Load on mount
  useEffect(() => {
    fetchConnections();
    refreshHistory();
  }, [fetchConnections, refreshHistory]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (connectionPollRef.current) clearInterval(connectionPollRef.current);
    };
  }, []);

  const connectPlatform = useCallback(
    async (platform: string) => {
      setConnecting(true);
      try {
        const res = await api.post("/api/publish/oauth/connect", {
          brand_id: brandId,
          platform,
        });
        if (!res.ok) return;
        const { auth_url } = res.data as ConnectResponse;
        openInBrowser(auth_url);

        // Poll for connection status every 2s until connected
        if (connectionPollRef.current) clearInterval(connectionPollRef.current);
        connectionPollRef.current = setInterval(async () => {
          const statusRes = await api.get(`/api/publish/oauth/status/${brandId}`);
          if (!statusRes.ok) return;
          const data = statusRes.data as OAuthStatusResponse;
          const conn = data[platform as keyof OAuthStatusResponse] as PlatformConnection;
          if (conn?.connected) {
            if (connectionPollRef.current) {
              clearInterval(connectionPollRef.current);
              connectionPollRef.current = null;
            }
            setConnections(data);
            setConnecting(false);
          }
        }, 2000);

        // Stop polling after 5 minutes
        setTimeout(() => {
          if (connectionPollRef.current) {
            clearInterval(connectionPollRef.current);
            connectionPollRef.current = null;
            setConnecting(false);
          }
        }, 300000);
      } catch {
        setConnecting(false);
      }
    },
    [brandId],
  );

  const disconnectPlatform = useCallback(
    async (platform: string) => {
      await api.request("DELETE", "/api/publish/oauth/disconnect", {
        brand_id: brandId,
        platform,
      });
      await fetchConnections();
    },
    [brandId, fetchConnections],
  );

  const startPublish = useCallback(
    async (
      platform: string,
      fileUrl: string,
      metadata: { title: string; description: string; tags: string[] },
      scheduleAt?: string,
    ) => {
      setPublishStatus(null);
      const res = await api.post("/api/publish/upload", {
        script_id: scriptId,
        brand_id: brandId,
        platform,
        file_url: fileUrl,
        metadata,
        schedule_at: scheduleAt,
      });
      if (!res.ok) return;
      const { job_id } = res.data as { job_id: string };
      setPublishJobId(job_id);

      // Poll for status
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        const statusRes = await api.get(`/api/publish/status/${job_id}`);
        if (!statusRes.ok) return;
        const status = statusRes.data as RenderStatusResponse;
        setPublishStatus(status);
        if (status.status === "completed" || status.status === "failed") {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          // Refresh history after publish completes
          refreshHistory();
        }
      }, 1000);
    },
    [scriptId, brandId, refreshHistory],
  );

  const ytConn = connections?.youtube;

  return {
    connections,
    youtubeConnected: ytConn?.connected ?? false,
    youtubeChannelName: ytConn?.platform_user_name ?? "",
    connectPlatform,
    disconnectPlatform,
    connecting,
    publishJobId,
    publishStatus,
    startPublish,
    publishHistory,
    refreshHistory,
  };
}
