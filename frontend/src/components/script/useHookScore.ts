import { useState, useEffect, useCallback } from "react";
import { scoreHook } from "../../api";
import { useOperationProgress } from "../../hooks/useOperationProgress";
import type { HookScore, ScriptContent } from "../../types/script";

interface UseHookScoreOptions {
  scriptId: string | null;
  script: ScriptContent | null;
}

export default function useHookScore({ scriptId, script }: UseHookScoreOptions) {
  const [hookScore, setHookScore] = useState<HookScore | null>(null);
  const [hookScoreLoading, setHookScoreLoading] = useState(false);
  const [hookScoreError, setHookScoreError] = useState<string | null>(null);
  const hookScoreProgress = useOperationProgress("hook_score");

  const triggerHookScore = useCallback(async () => {
    if (!scriptId) return;
    setHookScoreLoading(true);
    setHookScoreError(null);
    hookScoreProgress.start();
    try {
      const result = await scoreHook(scriptId);
      setHookScore(result);
    } catch (err) {
      setHookScoreError(err instanceof Error ? err.message : "Hook scoring failed");
    } finally {
      setHookScoreLoading(false);
      hookScoreProgress.end();
    }
  }, [scriptId, hookScoreProgress]);

  // Auto-trigger when script loads and has no existing score
  useEffect(() => {
    if (scriptId && script && !script.hook_score && !hookScore && !hookScoreLoading && !hookScoreError) {
      triggerHookScore();
    }
  }, [scriptId, script, hookScore, hookScoreLoading, hookScoreError, triggerHookScore]);

  // Populate from existing score on script load
  useEffect(() => {
    if (script?.hook_score && !hookScore) {
      setHookScore(script.hook_score);
    }
  }, [script, hookScore]);

  return { hookScore, hookScoreLoading, hookScoreError, triggerHookScore, hookScoreProgress: { estimatedSeconds: hookScoreProgress.estimatedSeconds, active: hookScoreProgress.active } };
}
