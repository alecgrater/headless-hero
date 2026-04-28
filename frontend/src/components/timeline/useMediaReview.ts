import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeMedia, getMediaAnalysisStatus } from "../../api";
import type { MediaAssignment, MediaAnalysisStatus } from "../../api";
import type { ScriptContent } from "../../types/script";

interface UseMediaReviewOptions {
  scriptId: string;
  content: ScriptContent;
}

export function useMediaReview({ scriptId, content }: UseMediaReviewOptions) {
  const [mediaAssignments, setMediaAssignments] = useState<MediaAssignment[] | null>(null);
  const [mediaReviewDismissed, setMediaReviewDismissed] = useState(false);
  const [mediaAnalyzing, setMediaAnalyzing] = useState(false);
  const mediaPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleAnalyzeMedia = useCallback(async () => {
    setMediaAnalyzing(true);
    setMediaAssignments(null);
    setMediaReviewDismissed(false);
    const res = await analyzeMedia(scriptId);
    if (!res.ok) {
      setMediaAnalyzing(false);
      return;
    }
    const jobId = (res.data as { job_id: string }).job_id;
    const poll = setInterval(async () => {
      const statusRes = await getMediaAnalysisStatus(jobId);
      if (!statusRes.ok) return;
      const status = statusRes.data as MediaAnalysisStatus;
      if (status.status === "completed" && status.assignments) {
        clearInterval(poll);
        mediaPollRef.current = null;
        setMediaAssignments(status.assignments as MediaAssignment[]);
        setMediaAnalyzing(false);
      } else if (status.status === "failed") {
        clearInterval(poll);
        mediaPollRef.current = null;
        setMediaAnalyzing(false);
      }
    }, 1000);
    mediaPollRef.current = poll;
  }, [scriptId]);

  useEffect(() => {
    return () => {
      if (mediaPollRef.current) clearInterval(mediaPollRef.current);
    };
  }, []);

  useEffect(() => {
    const allScenes = content.segments.flatMap((s) => s.scenes);
    const hasNonAi = allScenes.some((s) => s.media_source && s.media_source !== "ai");

    if (hasNonAi && !mediaReviewDismissed) {
      const existing: MediaAssignment[] = allScenes.map((s) => ({
        scene_id: s.id,
        media_source: (s.media_source ?? "ai") as "ai" | "gameplay_video" | "stock_photo",
        game_name: s.gameplay_game_override || null,
        search_query: s.media_source === "stock_photo" ? s.visual_prompt : null,
        reasoning: "",
      }));
      setMediaAssignments(existing);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hasPendingReview = !!(mediaAssignments && !mediaReviewDismissed && !mediaAnalyzing);

  return {
    mediaAssignments,
    mediaReviewDismissed,
    setMediaReviewDismissed,
    mediaAnalyzing,
    handleAnalyzeMedia,
    hasPendingReview,
  };
}
