import { useCallback, useEffect, useRef, useState } from "react";
import api, { openInBrowser } from "../../api";
import { usePollJob } from "../../hooks/usePollJob";
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

export function usePublishState(scriptId: string): PublishState {
  const [connections, setConnections] = useState<OAuthStatusResponse | null>(null);
  const [connecting, setConnecting] = useState(false);

  const [publishJobId, setPublishJobId] = useState<string | null>(null);
  const [publishStatus, setPublishStatus] = useState<RenderStatusResponse | null>(null);

  const [publishHistory, setPublishHistory] = useState<PublishRecord[]>([]);

  const connectionPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch connection status (no brand_id needed — backend auto-resolves)
  const fetchConnections = useCallback(async () => {
    const res = await api.get("/api/publish/oauth/status");
    if (res.ok) {
      setConnections(res.data as OAuthStatusResponse);
    }
  }, []);

  // Fetch publish history
  const refreshHistory = useCallback(async () => {
    if (!scriptId) return;
    const res = await api.get(`/api/publish/history/${scriptId}`);
    if (res.ok) {
      setPublishHistory(res.data as PublishRecord[]);
    }
  }, [scriptId]);

  const { startPolling: startPublishPolling } = usePollJob<RenderStatusResponse>({
    pollFn: async (jobId) => {
      const res = await api.get(`/api/publish/status/${jobId}`);
      if (!res.ok) return null;
      return res.data as RenderStatusResponse;
    },
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (status) => {
      setPublishStatus(status);
      if (status.status === "completed" || status.status === "failed") {
        refreshHistory();
      }
    },
    onConnectionLost: () => {
      setPublishStatus({
        job_id: publishJobId ?? "",
        status: "failed",
        progress: 0,
        current_step: "",
        output_urls: [],
        error: "Lost connection to the publish job. The backend may have restarted.",
      });
    },
  });

  // Load on mount
  useEffect(() => {
    const loadTimer = window.setTimeout(() => {
      void fetchConnections();
      void refreshHistory();
    }, 0);

    return () => window.clearTimeout(loadTimer);
  }, [fetchConnections, refreshHistory]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (connectionPollRef.current) clearInterval(connectionPollRef.current);
    };
  }, []);

  const connectPlatform = useCallback(
    async (platform: string) => {
      setConnecting(true);
      try {
        const res = await api.post("/api/publish/oauth/connect", {
          platform,
        });
        if (!res.ok) return;
        const { auth_url } = res.data as ConnectResponse;
        openInBrowser(auth_url);

        // Poll for connection status every 2s until connected
        if (connectionPollRef.current) clearInterval(connectionPollRef.current);
        connectionPollRef.current = setInterval(async () => {
          const statusRes = await api.get("/api/publish/oauth/status");
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
    [],
  );

  const disconnectPlatform = useCallback(
    async (platform: string) => {
      await api.request("DELETE", "/api/publish/oauth/disconnect", {
        platform,
      });
      await fetchConnections();
    },
    [fetchConnections],
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
        platform,
        file_url: fileUrl,
        metadata,
        schedule_at: scheduleAt,
      });
      if (!res.ok) return;
      const { job_id } = res.data as { job_id: string };
      setPublishJobId(job_id);
      startPublishPolling(job_id);
    },
    [scriptId, startPublishPolling],
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
