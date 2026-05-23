import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getActiveStylePreset, type StylePreset } from "../api";

type StylePresetContextValue = {
  activePreset: StylePreset | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

const StylePresetContext = createContext<StylePresetContextValue>({
  activePreset: null,
  loading: false,
  refresh: async () => {},
});

export function StylePresetProvider({ children }: { children: ReactNode }) {
  const [activePreset, setActivePreset] = useState<StylePreset | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const preset = await getActiveStylePreset();
      setActivePreset(preset);
    } catch (err) {
      console.error("Failed to load active style preset", err);
      setActivePreset(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <StylePresetContext.Provider value={{ activePreset, loading, refresh }}>
      {children}
    </StylePresetContext.Provider>
  );
}

export function useStylePreset() {
  return useContext(StylePresetContext);
}
