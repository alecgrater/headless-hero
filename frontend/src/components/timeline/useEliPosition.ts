import { useEffect, useRef, useState } from "react";
import api from "../../api";
import { DEFAULT_ELI_POSITION } from "../../constants";
import type { ScriptContent } from "../../types/script";
import type { EliPosition } from "../../types/brand";

interface UseEliPositionResult {
  showEliPositionPicker: boolean;
  setShowEliPositionPicker: (show: boolean) => void;
  eliPositionMode: "default" | "custom";
  setEliPositionMode: (mode: "default" | "custom") => void;
  brandEliPosition: EliPosition;
  setBrandEliPosition: (pos: EliPosition) => void;
  customEliPosition: EliPosition;
  setCustomEliPosition: (pos: EliPosition) => void;
  eliPositionRef: React.RefObject<HTMLDivElement | null>;
}

export function useEliPosition(initialContent: ScriptContent): UseEliPositionResult {
  const [showEliPositionPicker, setShowEliPositionPicker] = useState(false);
  const [eliPositionMode, setEliPositionMode] = useState<"default" | "custom">("default");
  const [brandEliPosition, setBrandEliPosition] = useState<EliPosition>(DEFAULT_ELI_POSITION);
  const [customEliPosition, setCustomEliPosition] = useState<EliPosition>(DEFAULT_ELI_POSITION);
  const eliPositionRef = useRef<HTMLDivElement>(null);

  // Fetch brand eli_position
  useEffect(() => {
    api.get("/api/brand").then((res) => {
      if (res.ok) {
        const b = res.data as { eli_position: EliPosition | null };
        if (b.eli_position) setBrandEliPosition(b.eli_position);
      }
    });
    // Initialize custom position from script if present
    if (initialContent.eli_position) {
      setEliPositionMode("custom");
      setCustomEliPosition(initialContent.eli_position);
    }
  }, []);

  // Close eli position picker on outside click
  useEffect(() => {
    if (!showEliPositionPicker) return;
    const handler = (e: MouseEvent) => {
      if (eliPositionRef.current && !eliPositionRef.current.contains(e.target as Node)) {
        setShowEliPositionPicker(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showEliPositionPicker]);

  return {
    showEliPositionPicker,
    setShowEliPositionPicker,
    eliPositionMode,
    setEliPositionMode,
    brandEliPosition,
    setBrandEliPosition,
    customEliPosition,
    setCustomEliPosition,
    eliPositionRef,
  };
}
