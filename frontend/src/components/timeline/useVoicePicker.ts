import { useEffect, useRef, useState } from "react";
import api from "../../api";
import type { VoiceInfo, VoiceListResponse } from "../../types/audio";

interface UseVoicePickerResult {
  voices: VoiceInfo[];
  selectedVoiceId: string;
  setSelectedVoiceId: (id: string) => void;
  showVoicePicker: boolean;
  setShowVoicePicker: (show: boolean) => void;
  voicePickerRef: React.RefObject<HTMLDivElement | null>;
}

export function useVoicePicker(): UseVoicePickerResult {
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  const [showVoicePicker, setShowVoicePicker] = useState(false);
  const voicePickerRef = useRef<HTMLDivElement>(null);

  // Fetch default brand voice
  useEffect(() => {
    api.get("/api/brand").then((res) => {
      if (res.ok) {
        const b = res.data as { voice_id: string };
        if (b.voice_id) setSelectedVoiceId(b.voice_id);
      }
    });
  }, []);

  // Fetch available voices
  useEffect(() => {
    api.get("/api/voice/voices").then((res) => {
      if (res.ok) {
        const data = res.data as VoiceListResponse;
        const sorted = [...data.voices].sort((a, b) => {
          const priority = (v: VoiceInfo) => {
            const n = v.name.toLowerCase();
            if (n.startsWith("ben")) return 0;
            if (n.startsWith("liam")) return 1;
            return 2;
          };
          return priority(a) - priority(b) || a.name.localeCompare(b.name);
        });
        setVoices(sorted);
        // Default to brand voice, then "Social Media" voice, then first voice
        setSelectedVoiceId((prev) => {
          if (!prev && data.voices.length > 0) {
            const social = data.voices.find((v) =>
              v.name.toLowerCase().includes("social media"),
            );
            return social?.voice_id ?? data.voices[0].voice_id;
          }
          return prev;
        });
      }
    });
  }, []);

  // Close voice picker on outside click
  useEffect(() => {
    if (!showVoicePicker) return;
    const handler = (e: MouseEvent) => {
      if (voicePickerRef.current && !voicePickerRef.current.contains(e.target as Node)) {
        setShowVoicePicker(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showVoicePicker]);

  return {
    voices,
    selectedVoiceId,
    setSelectedVoiceId,
    showVoicePicker,
    setShowVoicePicker,
    voicePickerRef,
  };
}
