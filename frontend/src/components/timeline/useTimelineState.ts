import { useCallback, useEffect, useRef, useState } from "react";
import api from "../../api";
import { fetchGenerationEstimate, recordDuration, pollTitleCardJob } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";
import type { GenerateVisualResponse, GenerateTitleCardsResponse } from "../../types/visual";
import type { GenerateAudioResponse } from "../../types/audio";

type BatchSceneStatus = "idle" | "pending" | "generating" | "done" | "failed";

interface BatchProgress {
  total: number;
  completed: number;
  failed: number;
  currentSceneId: string | null;
  currentSceneName: string | null;
  startedAt: number | null;
  statuses: Map<string, BatchSceneStatus>;
  initialEstimatedSeconds: number | null;
}

const EMPTY_BATCH: BatchProgress = {
  total: 0,
  completed: 0,
  failed: 0,
  currentSceneId: null,
  currentSceneName: null,
  startedAt: null,
  statuses: new Map(),
  initialEstimatedSeconds: null,
};

interface TimelineState {
  content: ScriptContent;
  isDirty: boolean;
  saveStatus: "saved" | "saving" | "unsaved";
  selectedSceneId: string | null;

  // Selection
  selectScene: (sceneId: string | null) => void;

  // Scene mutations
  updateScene: (sceneId: string, updates: Partial<Scene>) => void;
  moveScene: (
    sceneId: string,
    fromSegmentIdx: number,
    toSegmentIdx: number,
    newIndex: number,
  ) => void;
  splitScene: (sceneId: string) => void;
  mergeWithNext: (sceneId: string) => void;
  duplicateScene: (sceneId: string) => void;

  // Segment mutations
  addSegment: (afterIndex: number) => void;
  removeSegment: (segmentIndex: number) => void;

  // Save
  save: () => Promise<void>;

  // Undo
  undo: () => void;
  canUndo: boolean;

  // Image generation
  generatingSceneIds: Set<string>;
  batchGenerating: boolean;
  generateImage: (sceneId: string) => Promise<void>;
  generateAllImages: (missingOnly?: boolean) => Promise<void>;
  cancelImageGeneration: () => void;

  // Audio generation
  generatingAudioSceneIds: Set<string>;
  batchGeneratingAudio: boolean;
  generateAudio: (sceneId: string, voiceId: string) => Promise<void>;
  generateAllAudio: (voiceId: string, missingOnly?: boolean) => Promise<void>;
  cancelAudioGeneration: () => void;

  // Batch progress
  batchImageProgress: BatchProgress;
  batchAudioProgress: BatchProgress;

  // Title cards
  hasTitleCards: boolean;
  generateTitleCardsStandalone: (force?: boolean) => Promise<void>;

  // External content update (e.g. after FX generation refreshes from server)
  setContent: (content: ScriptContent) => void;

  // Single-item generation estimates
  singleImageEstimate: number | null;
  singleAudioEstimate: number | null;
}

function findScene(
  content: ScriptContent,
  sceneId: string,
): { segIdx: number; sceneIdx: number } | null {
  for (let si = 0; si < content.segments.length; si++) {
    const scIdx = content.segments[si].scenes.findIndex(
      (sc) => sc.id === sceneId,
    );
    if (scIdx !== -1) return { segIdx: si, sceneIdx: scIdx };
  }
  return null;
}

function generateId(): string {
  return `scene-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function splitNarrationAtMidpoint(narration: string): [string, string] {
  const sentences = narration.match(/[^.!?]+[.!?]+/g);
  if (!sentences || sentences.length < 2) {
    const mid = Math.floor(narration.length / 2);
    const spaceIdx = narration.indexOf(" ", mid);
    const splitAt = spaceIdx !== -1 ? spaceIdx : mid;
    return [narration.slice(0, splitAt).trim(), narration.slice(splitAt).trim()];
  }
  const midIdx = Math.ceil(sentences.length / 2);
  return [
    sentences.slice(0, midIdx).join("").trim(),
    sentences.slice(midIdx).join("").trim(),
  ];
}

export function useTimelineState(
  scriptId: string,
  initialContent: ScriptContent,
): TimelineState {
  const [content, setContent] = useState<ScriptContent>(initialContent);
  const [isDirty, setIsDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "unsaved">(
    "saved",
  );
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [undoStack, setUndoStack] = useState<ScriptContent[]>([]);
  const [generatingSceneIds, setGeneratingSceneIds] = useState<Set<string>>(new Set());
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [generatingAudioSceneIds, setGeneratingAudioSceneIds] = useState<Set<string>>(new Set());
  const [batchGeneratingAudio, setBatchGeneratingAudio] = useState(false);
  const [batchImageProgress, setBatchImageProgress] = useState<BatchProgress>(EMPTY_BATCH);
  const [batchAudioProgress, setBatchAudioProgress] = useState<BatchProgress>(EMPTY_BATCH);
  const [singleImageEstimate, setSingleImageEstimate] = useState<number | null>(null);
  const [singleAudioEstimate, setSingleAudioEstimate] = useState<number | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const contentRef = useRef(content);
  contentRef.current = content;

  // Cancellation refs for batch operations
  const imagesCancelRef = useRef(false);
  const audioCancelRef = useRef(false);

  useEffect(() => {
    fetchGenerationEstimate("single_image_generation").then((e) => setSingleImageEstimate(e.average_seconds)).catch(() => {});
    fetchGenerationEstimate("single_audio_generation").then((e) => setSingleAudioEstimate(e.average_seconds)).catch(() => {});
  }, []);

  const pushUndo = useCallback(() => {
    setUndoStack((prev) => [...prev.slice(-49), contentRef.current]);
  }, []);

  const mutate = useCallback(
    (updater: (draft: ScriptContent) => ScriptContent) => {
      pushUndo();
      setContent((prev) => {
        const next = updater(prev);
        return next;
      });
      setIsDirty(true);
      setSaveStatus("unsaved");
    },
    [pushUndo],
  );

  // Debounced auto-save
  useEffect(() => {
    if (!isDirty) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      doSave(contentRef.current);
    }, 5000);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty, content]);

  const doSave = async (toSave: ScriptContent) => {
    setSaveStatus("saving");
    try {
      const res = await api.put(`/api/scripts/${scriptId}`, {
        script: toSave,
      });
      if (res.ok) {
        setIsDirty(false);
        setSaveStatus("saved");
      } else {
        setSaveStatus("unsaved");
      }
    } catch {
      setSaveStatus("unsaved");
    }
  };

  const save = useCallback(async () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    await doSave(contentRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scriptId]);

  const replaceContent = useCallback((next: ScriptContent) => {
    contentRef.current = next;
    setContent(next);
  }, []);

  // Beforeunload guard
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        save();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [undoStack.length]);

  const selectScene = useCallback((sceneId: string | null) => {
    setSelectedSceneId(sceneId);
  }, []);

  const updateScene = useCallback(
    (sceneId: string, updates: Partial<Scene>) => {
      mutate((prev) => ({
        ...prev,
        segments: prev.segments.map((seg) => ({
          ...seg,
          scenes: seg.scenes.map((sc) =>
            sc.id === sceneId ? { ...sc, ...updates } : sc,
          ),
        })),
      }));
    },
    [mutate],
  );

  const moveScene = useCallback(
    (
      sceneId: string,
      fromSegmentIdx: number,
      toSegmentIdx: number,
      newIndex: number,
    ) => {
      mutate((prev) => {
        const segments = prev.segments.map((seg) => ({
          ...seg,
          scenes: [...seg.scenes],
        }));
        const fromScenes = segments[fromSegmentIdx].scenes;
        const oldIdx = fromScenes.findIndex((sc) => sc.id === sceneId);
        if (oldIdx === -1) return prev;
        const [scene] = fromScenes.splice(oldIdx, 1);
        segments[toSegmentIdx].scenes.splice(newIndex, 0, scene);
        return { ...prev, segments };
      });
    },
    [mutate],
  );

  const splitScene = useCallback(
    (sceneId: string) => {
      mutate((prev) => {
        const loc = findScene(prev, sceneId);
        if (!loc) return prev;
        const scene = prev.segments[loc.segIdx].scenes[loc.sceneIdx];
        const [firstNarr, secondNarr] = splitNarrationAtMidpoint(
          scene.narration,
        );
        const totalDuration = scene.duration_estimate_seconds;
        const ratio =
          firstNarr.length / (firstNarr.length + secondNarr.length);

        const sceneA: Scene = {
          ...scene,
          narration: firstNarr,
          duration_estimate_seconds: Math.round(totalDuration * ratio * 10) / 10,
        };
        const sceneB: Scene = {
          ...scene,
          id: generateId(),
          narration: secondNarr,
          duration_estimate_seconds:
            Math.round(totalDuration * (1 - ratio) * 10) / 10,
          is_title_card: false,
        };

        const segments = prev.segments.map((seg, si) => {
          if (si !== loc.segIdx) return seg;
          const scenes = [...seg.scenes];
          scenes.splice(loc.sceneIdx, 1, sceneA, sceneB);
          return { ...seg, scenes };
        });
        return { ...prev, segments };
      });
    },
    [mutate],
  );

  const mergeWithNext = useCallback(
    (sceneId: string) => {
      mutate((prev) => {
        const loc = findScene(prev, sceneId);
        if (!loc) return prev;
        const scenes = prev.segments[loc.segIdx].scenes;
        if (loc.sceneIdx >= scenes.length - 1) return prev;

        const current = scenes[loc.sceneIdx];
        const next = scenes[loc.sceneIdx + 1];
        const merged: Scene = {
          ...current,
          narration: current.narration + " " + next.narration,
          duration_estimate_seconds:
            current.duration_estimate_seconds +
            next.duration_estimate_seconds,
        };

        const segments = prev.segments.map((seg, si) => {
          if (si !== loc.segIdx) return seg;
          const newScenes = [...seg.scenes];
          newScenes.splice(loc.sceneIdx, 2, merged);
          return { ...seg, scenes: newScenes };
        });
        return { ...prev, segments };
      });
    },
    [mutate],
  );

  const duplicateScene = useCallback(
    (sceneId: string) => {
      mutate((prev) => {
        const loc = findScene(prev, sceneId);
        if (!loc) return prev;
        const scene = prev.segments[loc.segIdx].scenes[loc.sceneIdx];
        const clone: Scene = {
          ...scene,
          id: generateId(),
          image_url: undefined,
          audio_url: undefined,
          audio_duration_seconds: undefined,
        };

        const segments = prev.segments.map((seg, si) => {
          if (si !== loc.segIdx) return seg;
          const scenes = [...seg.scenes];
          scenes.splice(loc.sceneIdx + 1, 0, clone);
          return { ...seg, scenes };
        });
        setSelectedSceneId(clone.id);
        return { ...prev, segments };
      });
    },
    [mutate],
  );

  const addSegment = useCallback(
    (afterIndex: number) => {
      mutate((prev) => {
        const segments = [...prev.segments];
        segments.splice(afterIndex + 1, 0, {
          name: `New Segment`,
          scenes: [
            {
              id: generateId(),
              narration: "",
              visual_prompt: "",
              duration_estimate_seconds: 8,
              is_title_card: false,
            },
          ],
        });
        return { ...prev, segments };
      });
    },
    [mutate],
  );

  const removeSegment = useCallback(
    (segmentIndex: number) => {
      mutate((prev) => {
        if (prev.segments.length <= 1) return prev;
        const segments = prev.segments.filter((_, i) => i !== segmentIndex);
        return { ...prev, segments };
      });
    },
    [mutate],
  );

  const undo = useCallback(() => {
    setUndoStack((prev) => {
      if (prev.length === 0) return prev;
      const newStack = [...prev];
      const last = newStack.pop()!;
      setContent(last);
      setIsDirty(true);
      setSaveStatus("unsaved");
      return newStack;
    });
  }, []);

  const generateImage = useCallback(
    async (sceneId: string) => {
      // Find the scene to get its visual_prompt
      const scene = (() => {
        for (const seg of contentRef.current.segments) {
          const found = seg.scenes.find((s) => s.id === sceneId);
          if (found) return found;
        }
        return null;
      })();
      if (!scene) return;

      // Title card scenes use the dedicated title cards endpoint
      if (scene.is_title_card) {
        setGeneratingSceneIds((prev) => new Set(prev).add(sceneId));
        try {
          const res = await api.post("/api/visuals/generate-title-cards", {
            script_id: scriptId,
            force: true,
          });
          if (res.ok) {
            const data = res.data as GenerateTitleCardsResponse;
            await pollTitleCardJob(data.job_id);
            // Refresh script from server to get updated image URLs
            const scriptRes = await api.get(`/api/scripts/${scriptId}`);
            if (scriptRes.ok) {
              const scriptData = scriptRes.data as { script: ScriptContent };
              setContent(scriptData.script);
            }
          }
        } finally {
          setGeneratingSceneIds((prev) => {
            const next = new Set(prev);
            next.delete(sceneId);
            return next;
          });
        }
        return;
      }

      if (!scene.visual_prompt) return;

      setGeneratingSceneIds((prev) => new Set(prev).add(sceneId));
      try {
        const res = await api.post("/api/visuals/generate", {
          script_id: scriptId,
          scene_id: sceneId,
          visual_prompt: scene.visual_prompt,
          frame_directives: scene.frame_directives || [],
          contains_person: scene.contains_person || false,
          media_source: scene.media_source || "ai",
          gameplay_game_name: scene.gameplay_game_override || contentRef.current.gameplay_game_name || "",
          gameplay_game_override: scene.gameplay_game_override || "",
          audio_duration_seconds: scene.audio_duration_seconds || 0,
        });
        if (res.ok) {
          // Re-fetch from backend which already persisted the image data
          const scriptRes = await api.get(`/api/scripts/${scriptId}`);
          if (scriptRes.ok) {
            const scriptData = scriptRes.data as { script: ScriptContent };
            setContent(scriptData.script);
          }
        }
      } finally {
        setGeneratingSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(sceneId);
          return next;
        });
      }
    },
    [scriptId],
  );

  const generateAllImages = useCallback(
    async (missingOnly = false) => {
      // Collect AI-generated scenes
      const scenes: { scene_id: string; visual_prompt: string; name: string; frame_directives: any[]; contains_person: boolean; media_source: string; gameplay_game_name: string; gameplay_game_override: string; audio_duration_seconds: number }[] = [];
      let shouldGenerateTitleCards = false;
      for (const seg of contentRef.current.segments) {
        for (const sc of seg.scenes) {
          if (sc.is_title_card) {
            if (!missingOnly || !sc.image_url) shouldGenerateTitleCards = true;
          } else if (sc.visual_prompt && !sc.is_title_card) {
            if (missingOnly && (sc.image_url || sc.video_url || (sc.frame_urls && sc.frame_urls.length > 0))) continue;
            scenes.push({
              scene_id: sc.id,
              visual_prompt: sc.visual_prompt,
              name: sc.narration.slice(0, 40) || sc.id,
              frame_directives: sc.frame_directives || [],
              contains_person: sc.contains_person || false,
              media_source: sc.media_source || "ai",
              gameplay_game_name: sc.gameplay_game_override || contentRef.current.gameplay_game_name || "",
              gameplay_game_override: sc.gameplay_game_override || "",
              audio_duration_seconds: sc.audio_duration_seconds || 0,
            });
          }
        }
      }
      if (scenes.length === 0 && !shouldGenerateTitleCards) return;

      imagesCancelRef.current = false;
      setBatchGenerating(true);
      const statuses = new Map<string, BatchSceneStatus>();
      scenes.forEach((s) => statuses.set(s.scene_id, "pending"));

      const estimate = await fetchGenerationEstimate("batch_image_generation", scenes.length);

      setBatchImageProgress({
        total: scenes.length,
        completed: 0,
        failed: 0,
        currentSceneId: null,
        currentSceneName: null,
        startedAt: Date.now(),
        statuses: new Map(statuses),
        initialEstimatedSeconds: estimate.average_seconds,
      });

      const batchStartTime = Date.now();

      let completed = 0;
      let failed = 0;

      // Generate title cards first (background job)
      if (shouldGenerateTitleCards) {
        try {
          const res = await api.post("/api/visuals/generate-title-cards", {
            script_id: scriptId,
          });
          if (res.ok) {
            const data = res.data as GenerateTitleCardsResponse;
            await pollTitleCardJob(data.job_id);
            // Refresh script from server to get updated image URLs
            const scriptRes = await api.get(`/api/scripts/${scriptId}`);
            if (scriptRes.ok) {
              const scriptData = scriptRes.data as { script: ScriptContent };
              setContent(scriptData.script);
            }
          }
        } catch {
          // Title card generation failure shouldn't block AI image generation
        }
      }

      for (const scene of scenes) {
        if (imagesCancelRef.current) break;

        statuses.set(scene.scene_id, "generating");
        setGeneratingSceneIds((prev) => new Set(prev).add(scene.scene_id));
        setBatchImageProgress((prev) => ({
          ...prev,
          currentSceneId: scene.scene_id,
          currentSceneName: scene.name,
          statuses: new Map(statuses),
        }));

        try {
          const res = await api.post("/api/visuals/generate", {
            script_id: scriptId,
            scene_id: scene.scene_id,
            visual_prompt: scene.visual_prompt,
            frame_directives: scene.frame_directives,
            contains_person: scene.contains_person,
            media_source: scene.media_source,
            gameplay_game_name: scene.gameplay_game_name,
            gameplay_game_override: scene.gameplay_game_override,
            audio_duration_seconds: scene.audio_duration_seconds,
          });
          if (res.ok) {
            const data = res.data as GenerateVisualResponse;
            setContent((prev) => ({
              ...prev,
              segments: prev.segments.map((seg) => ({
                ...seg,
                scenes: seg.scenes.map((sc) =>
                  sc.id === scene.scene_id
                    ? {
                        ...sc,
                        image_url: data.image_url || sc.image_url,
                        video_url: data.video_url || sc.video_url,
                        frame_urls: data.frame_urls || sc.frame_urls,
                        visual_source_metadata: data.visual_source_metadata ?? sc.visual_source_metadata,
                      }
                    : sc,
                ),
              })),
            }));
            statuses.set(scene.scene_id, "done");
            completed++;
          } else {
            statuses.set(scene.scene_id, "failed");
            failed++;
          }
        } catch {
          statuses.set(scene.scene_id, "failed");
          failed++;
        }

        setGeneratingSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(scene.scene_id);
          return next;
        });
        setBatchImageProgress((prev) => ({
          ...prev,
          completed,
          failed,
          statuses: new Map(statuses),
        }));
      }

      setGeneratingSceneIds(new Set());
      setBatchGenerating(false);
      // Re-fetch from backend which already persisted all image data
      const scriptRes = await api.get(`/api/scripts/${scriptId}`);
      if (scriptRes.ok) {
        const scriptData = scriptRes.data as { script: ScriptContent };
        setContent(scriptData.script);
      }
      // Record batch duration for future estimates
      const batchDuration = (Date.now() - batchStartTime) / 1000;
      recordDuration("batch_image_generation", batchDuration, scenes.length);
      // Keep progress visible briefly, then clear
      setTimeout(() => setBatchImageProgress(EMPTY_BATCH), 3000);
    },
    [scriptId],
  );

  const generateAudio = useCallback(
    async (sceneId: string, voiceId: string) => {
      const scene = (() => {
        for (const seg of contentRef.current.segments) {
          const found = seg.scenes.find((s) => s.id === sceneId);
          if (found) return found;
        }
        return null;
      })();
      if (!scene || !scene.narration) return;

      setGeneratingAudioSceneIds((prev) => new Set(prev).add(sceneId));
      try {
        const res = await api.post("/api/voice/generate", {
          script_id: scriptId,
          scene_id: sceneId,
          narration: scene.narration,
          voice_id: voiceId,
        });
        if (res.ok) {
          // Re-fetch from backend which already persisted the audio data
          const scriptRes = await api.get(`/api/scripts/${scriptId}`);
          if (scriptRes.ok) {
            const scriptData = scriptRes.data as { script: ScriptContent };
            setContent(scriptData.script);
          }
        }
      } finally {
        setGeneratingAudioSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(sceneId);
          return next;
        });
      }
    },
    [scriptId],
  );

  // Title card helpers
  const hasTitleCards = content.segments.some((seg) =>
    seg.scenes.some((sc) => sc.is_title_card),
  );

  const generateTitleCardsStandalone = useCallback(
    async (force = false) => {
      try {
        const res = await api.post("/api/visuals/generate-title-cards", {
          script_id: scriptId,
          force,
        });
        if (res.ok) {
          const data = res.data as GenerateTitleCardsResponse;
          await pollTitleCardJob(data.job_id);
          const scriptRes = await api.get(`/api/scripts/${scriptId}`);
          if (scriptRes.ok) {
            const scriptData = scriptRes.data as { script: ScriptContent };
            setContent(scriptData.script);
          }
        }
      } catch {
        // Error toast handled by API interceptor
      }
    },
    [scriptId],
  );

  const generateAllAudio = useCallback(
    async (voiceId: string, missingOnly = false) => {
      const scenes: { scene_id: string; narration: string; name: string }[] = [];
      for (const seg of contentRef.current.segments) {
        for (const sc of seg.scenes) {
          if (sc.narration) {
            if (missingOnly && sc.audio_url) continue;
            scenes.push({
              scene_id: sc.id,
              narration: sc.narration,
              name: sc.narration.slice(0, 40) || sc.id,
            });
          }
        }
      }
      if (scenes.length === 0) return;

      audioCancelRef.current = false;
      setBatchGeneratingAudio(true);
      const statuses = new Map<string, BatchSceneStatus>();
      scenes.forEach((s) => statuses.set(s.scene_id, "pending"));

      const estimate = await fetchGenerationEstimate("batch_audio_generation", scenes.length);

      setBatchAudioProgress({
        total: scenes.length,
        completed: 0,
        failed: 0,
        currentSceneId: null,
        currentSceneName: null,
        startedAt: Date.now(),
        statuses: new Map(statuses),
        initialEstimatedSeconds: estimate.average_seconds,
      });

      const batchStartTime = Date.now();

      let completed = 0;
      let failed = 0;

      for (const scene of scenes) {
        if (audioCancelRef.current) break;

        statuses.set(scene.scene_id, "generating");
        setGeneratingAudioSceneIds((prev) => new Set(prev).add(scene.scene_id));
        setBatchAudioProgress((prev) => ({
          ...prev,
          currentSceneId: scene.scene_id,
          currentSceneName: scene.name,
          statuses: new Map(statuses),
        }));

        try {
          const res = await api.post("/api/voice/generate", {
            script_id: scriptId,
            scene_id: scene.scene_id,
            narration: scene.narration,
            voice_id: voiceId,
          });
          if (res.ok) {
            const data = res.data as GenerateAudioResponse;
            setContent((prev) => ({
              ...prev,
              segments: prev.segments.map((seg) => ({
                ...seg,
                scenes: seg.scenes.map((sc) =>
                  sc.id === scene.scene_id
                    ? { ...sc, audio_url: data.audio_url, audio_duration_seconds: data.duration_seconds }
                    : sc,
                ),
              })),
            }));
            statuses.set(scene.scene_id, "done");
            completed++;
          } else {
            statuses.set(scene.scene_id, "failed");
            failed++;
          }
        } catch {
          statuses.set(scene.scene_id, "failed");
          failed++;
        }

        setGeneratingAudioSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(scene.scene_id);
          return next;
        });
        setBatchAudioProgress((prev) => ({
          ...prev,
          completed,
          failed,
          statuses: new Map(statuses),
        }));
      }

      setGeneratingAudioSceneIds(new Set());
      setBatchGeneratingAudio(false);
      // Re-fetch from backend which already persisted all audio data
      const scriptRes = await api.get(`/api/scripts/${scriptId}`);
      if (scriptRes.ok) {
        const scriptData = scriptRes.data as { script: ScriptContent };
        setContent(scriptData.script);
      }
      // Record batch duration for future estimates
      const batchDuration = (Date.now() - batchStartTime) / 1000;
      recordDuration("batch_audio_generation", batchDuration, scenes.length);
      setTimeout(() => setBatchAudioProgress(EMPTY_BATCH), 3000);
    },
    [scriptId],
  );

  const cancelImageGeneration = useCallback(() => {
    imagesCancelRef.current = true;
  }, []);

  const cancelAudioGeneration = useCallback(() => {
    audioCancelRef.current = true;
  }, []);

  return {
    content,
    isDirty,
    saveStatus,
    selectedSceneId,
    selectScene,
    updateScene,
    moveScene,
    splitScene,
    mergeWithNext,
    duplicateScene,
    addSegment,
    removeSegment,
    save,
    undo,
    canUndo: undoStack.length > 0,
    generatingSceneIds,
    batchGenerating,
    generateImage,
    generateAllImages,
    cancelImageGeneration,
    generatingAudioSceneIds,
    batchGeneratingAudio,
    generateAudio,
    generateAllAudio,
    cancelAudioGeneration,
    batchImageProgress,
    batchAudioProgress,
    hasTitleCards,
    generateTitleCardsStandalone,
    setContent: replaceContent,
    singleImageEstimate,
    singleAudioEstimate,
  };
}
