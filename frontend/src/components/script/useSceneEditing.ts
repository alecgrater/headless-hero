import { useState } from "react";
import api from "../../api";
import { useOperationProgress } from "../../hooks/useOperationProgress";
import type { Scene, ScriptContent } from "../../types/script";

interface Params {
  script: ScriptContent | null;
  scriptId: string | null;
  setScript: (s: ScriptContent) => void;
}

export interface SceneEditingState {
  editingKey: string | null;
  editNarration: string;
  editHookText: string;
  editedScenes: Set<string>;
  refiningScene: string | null;
  saving: boolean;
  setEditNarration: (v: string) => void;
  setEditHookText: (v: string) => void;
  startEditScene: (si: number, scene: Scene) => void;
  cancelEdit: () => void;
  saveSceneEdit: (si: number, sceneId: string) => Promise<void>;
  startEditIntro: () => void;
  saveIntroEdit: () => Promise<void>;
  startEditOutro: () => void;
  saveOutroEdit: () => Promise<void>;
  refineScene: (si: number, sceneId: string) => Promise<void>;
  refineProgress: { estimatedSeconds: number | null; active: boolean };
}

export default function useSceneEditing({ script, scriptId, setScript }: Params): SceneEditingState {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editNarration, setEditNarration] = useState("");
  const [editHookText, setEditHookText] = useState("");
  const [editedScenes, setEditedScenes] = useState<Set<string>>(new Set());
  const [refiningScene, setRefiningScene] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const refineProgressHook = useOperationProgress("scene_refinement");

  const saveScript = async (updated: ScriptContent) => {
    if (!scriptId) return;
    setSaving(true);
    await api.put(`/api/scripts/${scriptId}`, { script: updated });
    setSaving(false);
  };

  const startEditScene = (si: number, scene: Scene) => {
    const key = `${si}-${scene.id}`;
    setEditingKey(key);
    setEditNarration(scene.narration);
  };

  const cancelEdit = () => {
    setEditingKey(null);
  };

  const saveSceneEdit = async (si: number, sceneId: string) => {
    if (!script) return;
    const updated = structuredClone(script);
    const scene = updated.segments[si].scenes.find((s) => s.id === sceneId);
    if (!scene) return;
    scene.narration = editNarration;
    setScript(updated);
    setEditingKey(null);
    setEditedScenes((prev) => new Set(prev).add(sceneId));
    await saveScript(updated);
  };

  const startEditIntro = () => {
    if (!script) return;
    setEditingKey("intro");
    setEditHookText(script.intro_hook);
  };

  const saveIntroEdit = async () => {
    if (!script) return;
    const updated = { ...script, intro_hook: editHookText };
    setScript(updated);
    setEditingKey(null);
    await saveScript(updated);
  };

  const startEditOutro = () => {
    if (!script) return;
    setEditingKey("outro");
    setEditHookText(script.outro_cta);
  };

  const saveOutroEdit = async () => {
    if (!script) return;
    const updated = { ...script, outro_cta: editHookText };
    setScript(updated);
    setEditingKey(null);
    await saveScript(updated);
  };

  const refineScene = async (si: number, sceneId: string) => {
    if (!script || !scriptId) return;
    setRefiningScene(sceneId);
    refineProgressHook.start();
    try {
      const res = await api.post(`/api/scripts/${scriptId}/refine-scene`, {
        segment_index: si,
        scene_id: sceneId,
      });
      if (res.ok) {
        const { scene } = res.data as { scene: Scene };
        const updated = structuredClone(script);
        const idx = updated.segments[si].scenes.findIndex((s) => s.id === sceneId);
        if (idx !== -1) {
          updated.segments[si].scenes[idx] = scene;
          setScript(updated);
          setEditedScenes((prev) => {
            const next = new Set(prev);
            next.delete(sceneId);
            return next;
          });
          await saveScript(updated);
        }
      }
    } finally {
      setRefiningScene(null);
      refineProgressHook.end();
    }
  };

  return {
    editingKey,
    editNarration,
    editHookText,
    editedScenes,
    refiningScene,
    saving,
    setEditNarration,
    setEditHookText,
    startEditScene,
    cancelEdit,
    saveSceneEdit,
    startEditIntro,
    saveIntroEdit,
    startEditOutro,
    saveOutroEdit,
    refineScene,
    refineProgress: { estimatedSeconds: refineProgressHook.estimatedSeconds, active: refineProgressHook.active },
  };
}
