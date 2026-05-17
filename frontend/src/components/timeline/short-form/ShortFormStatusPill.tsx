import { useEffect, useState } from "react";
import { getRenderedShortsStatus } from "../../../api";

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
      try {
        const status = await getRenderedShortsStatus(scriptId);
        if (!cancelled) setRenderedCount(status.rendered_indices.length);
      } catch {
        if (!cancelled) setRenderedCount(0);
      }
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
      className="inline-flex h-7 shrink-0 items-center whitespace-nowrap text-xs px-3 bg-neutral-800 hover:bg-neutral-700 rounded-md text-neutral-300 transition-colors"
    >
      Short Form: {renderedCount}/{segmentCount} rendered
    </button>
  );
}
