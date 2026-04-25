import { useRef, useState } from "react";
import { cloneVoice } from "../../api";
import { useOperationProgress } from "../../hooks/useOperationProgress";

const MAX_VOICE_CLONE_FILES = 5;

interface UseVoiceCloningOptions {
  defaultName?: string;
  onCloned?: (voiceId: string) => void;
}

export default function useVoiceCloning({ defaultName = "", onCloned }: UseVoiceCloningOptions = {}) {
  const [audioFiles, setAudioFiles] = useState<File[]>([]);
  const [cloneName, setCloneName] = useState(defaultName);
  const [cloning, setCloning] = useState(false);
  const [cloneError, setCloneError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cloningProgress = useOperationProgress("voice_cloning");

  const addFiles = (fileList: FileList | null) => {
    const files = Array.from(fileList || []).slice(0, MAX_VOICE_CLONE_FILES);
    setAudioFiles(files);
    setCloneError(null);
  };

  const removeFile = (index: number) => {
    setAudioFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleClone = async (fallbackName?: string) => {
    setCloning(true);
    setCloneError(null);
    cloningProgress.start();
    try {
      const result = await cloneVoice(
        cloneName || fallbackName || "Cloned Voice",
        audioFiles,
      );
      onCloned?.(result.voice_id);
      setAudioFiles([]);
      return result.voice_id;
    } catch (err: unknown) {
      setCloneError(err instanceof Error ? err.message : "Voice cloning failed");
      return null;
    } finally {
      setCloning(false);
      cloningProgress.end();
    }
  };

  return {
    audioFiles,
    cloneName,
    setCloneName,
    cloning,
    cloneError,
    fileInputRef,
    addFiles,
    removeFile,
    handleClone,
    maxFiles: MAX_VOICE_CLONE_FILES,
    cloningProgress: { estimatedSeconds: cloningProgress.estimatedSeconds, active: cloningProgress.active },
  };
}
