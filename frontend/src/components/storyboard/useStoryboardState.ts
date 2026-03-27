import { useCallback, useEffect, useRef, useState } from "react";
import api from "../../api";
import type { Scene, ScriptContent } from "../../types/script";

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

  // Segment mutations
  addSegment: (afterIndex: number) => void;
  removeSegment: (segmentIndex: number) => void;

  // Save
  save: () => Promise<void>;

  // Undo
  undo: () => void;
  canUndo: boolean;
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

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const contentRef = useRef(content);
  contentRef.current = content;

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
    addSegment,
    removeSegment,
    save,
    undo,
    canUndo: undoStack.length > 0,
  };
}
