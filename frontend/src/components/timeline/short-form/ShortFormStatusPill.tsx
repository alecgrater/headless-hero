import type { ShortIntro } from "../../../types/render";

interface Props {
  segments: { name: string }[];
  intros: ShortIntro[] | null | undefined;
  renderedCount: number;
  onClick: () => void;
}

export default function ShortFormStatusPill({
  segments,
  intros,
  renderedCount,
  onClick,
}: Props) {
  const total = segments.length;
  const introsCount = intros?.length ?? 0;
  const introsDone = introsCount === total;
  const rendersDone = renderedCount === total;
  const allDone = introsDone && rendersDone;
  const color = allDone
    ? "text-emerald-400 border-emerald-700/50 bg-emerald-900/20"
    : introsDone
      ? "text-violet-400 border-violet-700/50 bg-violet-900/20"
      : "text-neutral-400 border-neutral-700 bg-neutral-800/40";

  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors hover:opacity-90 ${color}`}
      title="Open short-form export"
    >
      Short Form: intros {introsCount}/{total} · renders {renderedCount}/{total}
    </button>
  );
}
