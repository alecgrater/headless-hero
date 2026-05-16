import { useEffect, useState } from "react";
import { assetUrl } from "../../../api";

interface Props {
  scriptId: string;
  segmentCount: number;
  onClick: () => void;
}

export default function ShortFormStatusPill({
  scriptId,
  segmentCount,
  onClick,
}: Props) {
  const [renderedCount, setRenderedCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      let count = 0;
      for (let i = 0; i < segmentCount; i++) {
        const path = `/static/projects/${scriptId}/renders/shorts/${i}.mp4`;
        try {
          const r = await fetch(assetUrl(path), { method: "HEAD" });
          if (r.ok) count++;
        } catch {
          /* ignore */
        }
      }
      if (!cancelled) setRenderedCount(count);
    }
    probe();
    return () => {
      cancelled = true;
    };
  }, [scriptId, segmentCount]);

  return (
    <button
      onClick={onClick}
      title="Open short-form export"
      className="text-xs px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300 transition-colors"
    >
      Short Form: {renderedCount}/{segmentCount} rendered
    </button>
  );
}
