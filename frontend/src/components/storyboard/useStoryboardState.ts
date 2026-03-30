import { useCallback, useEffect, useRef, useState } from "react";
import api from "../../api";
import { fetchMedia as apiFetchMedia, fetchMediaBatch } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";
import type { GenerateBatchResponse, GenerateVisualResponse, GenerateTitleCardsResponse } from "../../types/visual";
import type { GenerateAudioResponse, GenerateBatchAudioResponse } from "../../types/audio";
import type { FetchMediaResponse, BatchFetchResponse } from "../../types/media";

type BatchSceneStatus = "idle" | "pending" | "generating" | "done" | "failed";

interface BatchProgress {
  total: number;
  completed: number;
  failed: number;
  currentSceneId: string | null;
  currentSceneName: string | null;
  startedAt: number | null;
  statuses: Map<string, BatchSceneStatus>;
}

const EMPTY_BATCH: BatchProgress = {
  total: 0,
  completed: 0,
  failed: 0,
  currentSceneId: null,
  currentSceneName: null,
  startedAt: null,
  statuses: new Map(),
};

interface StoryboardState {
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
  generateAllImages: () => Promise<void>;

  // Audio generation
  generatingAudioSceneIds: Set<string>;
  batchGeneratingAudio: boolean;
  generateAudio: (sceneId: string, voiceId: string) => Promise<void>;
  generateAllAudio: (voiceId: string) => Promise<void>;

  // Batch progress
  batchImageProgress: BatchProgress;
  batchAudioProgress: BatchProgress;
  batchMediaProgress: BatchProgress;

  // Media fetching (real clips/images)
  fetchingMediaSceneIds: Set<string>;
  batchFetchingMedia: boolean;
  fetchMedia: (sceneId: string) => Promise<void>;
  fetchAllMedia: () => Promise<void>;
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

export function useStoryboardState(
  scriptId: string,
  initialContent: ScriptContent,
): StoryboardState {
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
  const [fetchingMediaSceneIds, setFetchingMediaSceneIds] = useState<Set<string>>(new Set());
  const [batchFetchingMedia, setBatchFetchingMedia] = useState(false);
  const [batchMediaProgress, setBatchMediaProgress] = useState<BatchProgress>(EMPTY_BATCH);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const contentRef = useRef(content);
  contentRef.current = content;

  // Immediate save — used after generation to ensure persistence
  const immediateFlush = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    // Use a microtask so React state updates settle first
    queueMicrotask(() => {
      doSave(contentRef.current);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scriptId]);

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
          text_overlay: current.text_overlay || next.text_overlay,
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
          image_url_b: undefined,
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
              text_overlay: "",
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
            setContent((prev) => ({
              ...prev,
              segments: prev.segments.map((seg) => ({
                ...seg,
                scenes: seg.scenes.map((sc) =>
                  data.image_urls[sc.id]
                    ? { ...sc, image_url: data.image_urls[sc.id] }
                    : sc,
                ),
              })),
            }));
            immediateFlush();
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
          is_animated: scene.is_animated || false,
          visual_prompt_b: scene.visual_prompt_b || "",
          frame_prompts: scene.frame_prompts || [],
          frame_seed: scene.frame_seed ?? null,
        });
        if (res.ok) {
          const data = res.data as GenerateVisualResponse;
          // Update scene without pushing to undo stack (server already persisted)
          setContent((prev) => ({
            ...prev,
            segments: prev.segments.map((seg) => ({
              ...seg,
              scenes: seg.scenes.map((sc) =>
                sc.id === sceneId
                  ? {
                      ...sc,
                      image_url: data.image_url,
                      image_url_b: data.image_url_b || sc.image_url_b,
                      frame_urls: data.frame_urls || sc.frame_urls,
                    }
                  : sc,
              ),
            })),
          }));
          immediateFlush();
        }
      } finally {
        setGeneratingSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(sceneId);
          return next;
        });
      }
    },
    [scriptId, immediateFlush],
  );

  const generateAllImages = useCallback(
    async () => {
      // Collect AI-generated scenes
      const scenes: { scene_id: string; visual_prompt: string; name: string; is_animated: boolean; visual_prompt_b: string; frame_prompts: string[]; frame_seed: number | null }[] = [];
      // Collect title card scene IDs for progress tracking
      let hasTitleCards = false;
      for (const seg of contentRef.current.segments) {
        for (const sc of seg.scenes) {
          if (sc.is_title_card) {
            hasTitleCards = true;
          } else if (sc.visual_prompt && (!sc.media_type || sc.media_type === "ai_generated")) {
            scenes.push({
              scene_id: sc.id,
              visual_prompt: sc.visual_prompt,
              name: sc.text_overlay || sc.narration.slice(0, 40) || sc.id,
              is_animated: sc.is_animated || false,
              visual_prompt_b: sc.visual_prompt_b || "",
              frame_prompts: sc.frame_prompts || [],
              frame_seed: sc.frame_seed ?? null,
            });
          }
        }
      }
      if (scenes.length === 0 && !hasTitleCards) return;

      setBatchGenerating(true);
      const statuses = new Map<string, BatchSceneStatus>();
      scenes.forEach((s) => statuses.set(s.scene_id, "pending"));
      setBatchImageProgress({
        total: scenes.length,
        completed: 0,
        failed: 0,
        currentSceneId: null,
        currentSceneName: null,
        startedAt: Date.now(),
        statuses: new Map(statuses),
      });

      let completed = 0;
      let failed = 0;

      // Generate title cards first (instant, local FFmpeg)
      if (hasTitleCards) {
        try {
          const res = await api.post("/api/visuals/generate-title-cards", {
            script_id: scriptId,
          });
          if (res.ok) {
            const data = res.data as GenerateTitleCardsResponse;
            setContent((prev) => ({
              ...prev,
              segments: prev.segments.map((seg) => ({
                ...seg,
                scenes: seg.scenes.map((sc) =>
                  data.image_urls[sc.id]
                    ? { ...sc, image_url: data.image_urls[sc.id] }
                    : sc,
                ),
              })),
            }));
          }
        } catch {
          // Title card generation failure shouldn't block AI image generation
        }
      }

      for (const scene of scenes) {
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
            is_animated: scene.is_animated,
            visual_prompt_b: scene.visual_prompt_b,
            frame_prompts: scene.frame_prompts,
            frame_seed: scene.frame_seed,
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
                        image_url: data.image_url,
                        image_url_b: data.image_url_b || sc.image_url_b,
                        frame_urls: data.frame_urls || sc.frame_urls,
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
      immediateFlush();
      // Keep progress visible briefly, then clear
      setTimeout(() => setBatchImageProgress(EMPTY_BATCH), 3000);
    },
    [scriptId, immediateFlush],
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
          const data = res.data as GenerateAudioResponse;
          setContent((prev) => ({
            ...prev,
            segments: prev.segments.map((seg) => ({
              ...seg,
              scenes: seg.scenes.map((sc) =>
                sc.id === sceneId
                  ? { ...sc, audio_url: data.audio_url, audio_duration_seconds: data.duration_seconds }
                  : sc,
              ),
            })),
          }));
          immediateFlush();
        }
      } finally {
        setGeneratingAudioSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(sceneId);
          return next;
        });
      }
    },
    [scriptId, immediateFlush],
  );

  const generateAllAudio = useCallback(
    async (voiceId: string) => {
      const scenes: { scene_id: string; narration: string; name: string }[] = [];
      for (const seg of contentRef.current.segments) {
        for (const sc of seg.scenes) {
          if (sc.narration) {
            scenes.push({
              scene_id: sc.id,
              narration: sc.narration,
              name: sc.text_overlay || sc.narration.slice(0, 40) || sc.id,
            });
          }
        }
      }
      if (scenes.length === 0) return;

      setBatchGeneratingAudio(true);
      const statuses = new Map<string, BatchSceneStatus>();
      scenes.forEach((s) => statuses.set(s.scene_id, "pending"));
      setBatchAudioProgress({
        total: scenes.length,
        completed: 0,
        failed: 0,
        currentSceneId: null,
        currentSceneName: null,
        startedAt: Date.now(),
        statuses: new Map(statuses),
      });

      let completed = 0;
      let failed = 0;

      for (const scene of scenes) {
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
      immediateFlush();
      setTimeout(() => setBatchAudioProgress(EMPTY_BATCH), 3000);
    },
    [scriptId, immediateFlush],
  );

  const fetchMediaForScene = useCallback(
    async (sceneId: string) => {
      const scene = (() => {
        for (const seg of contentRef.current.segments) {
          const found = seg.scenes.find((s) => s.id === sceneId);
          if (found) return found;
        }
        return null;
      })();
      if (!scene || !scene.search_query || !scene.media_type || scene.media_type === "ai_generated") return;

      setFetchingMediaSceneIds((prev) => new Set(prev).add(sceneId));
      try {
        const res = await apiFetchMedia(
          scriptId,
          sceneId,
          scene.media_type,
          scene.search_query,
          scene.audio_duration_seconds || scene.duration_estimate_seconds,
        );
        if (res.ok) {
          const data = res.data as FetchMediaResponse;
          setContent((prev) => ({
            ...prev,
            segments: prev.segments.map((seg) => ({
              ...seg,
              scenes: seg.scenes.map((sc) =>
                sc.id === sceneId
                  ? {
                      ...sc,
                      ...(data.video_clip_url ? { video_clip_url: data.video_clip_url } : {}),
                      ...(data.image_url ? { image_url: data.image_url } : {}),
                    }
                  : sc,
              ),
            })),
          }));
          immediateFlush();
        }
      } finally {
        setFetchingMediaSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(sceneId);
          return next;
        });
      }
    },
    [scriptId, immediateFlush],
  );

  const fetchAllMediaScenes = useCallback(
    async () => {
      const scenes: { scene_id: string; media_type: string; search_query: string; duration: number; name: string }[] = [];
      for (const seg of contentRef.current.segments) {
        for (const sc of seg.scenes) {
          if (sc.media_type && sc.media_type !== "ai_generated" && sc.search_query) {
            scenes.push({
              scene_id: sc.id,
              media_type: sc.media_type,
              search_query: sc.search_query,
              duration: sc.audio_duration_seconds || sc.duration_estimate_seconds,
              name: sc.text_overlay || sc.narration.slice(0, 40) || sc.id,
            });
          }
        }
      }
      if (scenes.length === 0) return;

      setBatchFetchingMedia(true);
      const statuses = new Map<string, BatchSceneStatus>();
      scenes.forEach((s) => statuses.set(s.scene_id, "pending"));
      setBatchMediaProgress({
        total: scenes.length,
        completed: 0,
        failed: 0,
        currentSceneId: null,
        currentSceneName: null,
        startedAt: Date.now(),
        statuses: new Map(statuses),
      });

      let completed = 0;
      let failed = 0;

      for (const scene of scenes) {
        statuses.set(scene.scene_id, "generating");
        setFetchingMediaSceneIds((prev) => new Set(prev).add(scene.scene_id));
        setBatchMediaProgress((prev) => ({
          ...prev,
          currentSceneId: scene.scene_id,
          currentSceneName: scene.name,
          statuses: new Map(statuses),
        }));

        try {
          const res = await apiFetchMedia(
            scriptId,
            scene.scene_id,
            scene.media_type,
            scene.search_query,
            scene.duration,
          );
          if (res.ok) {
            const data = res.data as FetchMediaResponse;
            setContent((prev) => ({
              ...prev,
              segments: prev.segments.map((seg) => ({
                ...seg,
                scenes: seg.scenes.map((sc) =>
                  sc.id === scene.scene_id
                    ? {
                        ...sc,
                        ...(data.video_clip_url ? { video_clip_url: data.video_clip_url } : {}),
                        ...(data.image_url ? { image_url: data.image_url } : {}),
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

        setFetchingMediaSceneIds((prev) => {
          const next = new Set(prev);
          next.delete(scene.scene_id);
          return next;
        });
        setBatchMediaProgress((prev) => ({
          ...prev,
          completed,
          failed,
          statuses: new Map(statuses),
        }));
      }

      setFetchingMediaSceneIds(new Set());
      setBatchFetchingMedia(false);
      immediateFlush();
      setTimeout(() => setBatchMediaProgress(EMPTY_BATCH), 3000);
    },
    [scriptId, immediateFlush],
  );

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
    generatingAudioSceneIds,
    batchGeneratingAudio,
    generateAudio,
    generateAllAudio,
    batchImageProgress,
    batchAudioProgress,
    batchMediaProgress,
    fetchingMediaSceneIds,
    batchFetchingMedia,
    fetchMedia: fetchMediaForScene,
    fetchAllMedia: fetchAllMediaScenes,
  };
}
