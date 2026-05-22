import { useState, useRef, useEffect } from "react";
import type { Idea, IdeaStatus } from "../../types/idea";
import { Tooltip } from "../ui/Tooltip";

const STATUS_CONFIG: Record<IdeaStatus, { label: string; color: string; next: IdeaStatus | null }> = {
  idea: { label: "Idea", color: "bg-violet-500/20 text-violet-300 border-violet-500/30", next: "in_progress" },
  in_progress: { label: "In Progress", color: "bg-amber-500/20 text-amber-300 border-amber-500/30", next: "scripted" },
  scripted: { label: "Scripted", color: "bg-sky-500/20 text-sky-300 border-sky-500/30", next: "published" },
  published: { label: "Published", color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30", next: null },
};

const SOURCE_CHIP: Record<string, { label: string; color: string }> = {
  for_you: { label: "For You", color: "bg-violet-500/15 text-violet-400" },
  trending: { label: "Trending", color: "bg-sky-500/15 text-sky-400" },
};

function HookScoreBadge({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <div className="w-10 h-10 rounded-full border-2 border-dashed border-neutral-600 flex items-center justify-center">
        <span className="text-[10px] text-neutral-500">--</span>
      </div>
    );
  }

  const color =
    score >= 80
      ? "border-emerald-500/60 text-emerald-400 bg-emerald-500/10"
      : score >= 50
        ? "border-amber-500/60 text-amber-400 bg-amber-500/10"
        : "border-red-500/60 text-red-400 bg-red-500/10";

  return (
    <Tooltip content={`Hook retention score: ${score}/100`}>
      <div className={`w-10 h-10 rounded-full border-2 flex flex-col items-center justify-center ${color}`}>
        <span className="text-sm font-bold leading-none tabular-nums">{score}</span>
        <span className="text-[7px] font-medium opacity-60 mt-0.5">hook</span>
      </div>
    </Tooltip>
  );
}

interface Props {
  idea: Idea;
  onUpdate: (id: string, updates: { text?: string; rank?: number; status?: IdeaStatus }) => void;
  onDelete: (id: string) => void;
  onGenerateIdeas: (niche: string) => void;
}

export default function SavedIdeaCard({ idea, onUpdate, onDelete, onGenerateIdeas }: Props) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(idea.text);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleSave = () => {
    const trimmed = editText.trim();
    if (trimmed && trimmed !== idea.text) {
      onUpdate(idea.id, { text: trimmed });
    }
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === "Escape") {
      setEditText(idea.text);
      setEditing(false);
    }
  };

  const statusCfg = STATUS_CONFIG[idea.status] || STATUS_CONFIG.idea;
  const sourceChip = SOURCE_CHIP[idea.source];

  const handleStatusClick = () => {
    if (statusCfg.next) {
      onUpdate(idea.id, { status: statusCfg.next });
    }
  };

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-800/50 p-4 hover:border-neutral-600 transition-colors">
      <div className="flex items-start gap-3">
        {/* Hook score badge */}
        <div className="shrink-0 pt-0.5">
          <HookScoreBadge score={idea.hook_score} />
        </div>

        {/* Rank controls */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <Tooltip content="Increase priority">
            <button
              onClick={() => onUpdate(idea.id, { rank: Math.min(100, idea.rank + 10) })}
              className="text-neutral-500 hover:text-neutral-300 transition-colors p-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded"
              aria-label="Increase priority"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
              </svg>
            </button>
          </Tooltip>
          <Tooltip content={`Priority: ${idea.rank}`}>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                idea.rank >= 75
                  ? "bg-violet-500/20 text-violet-300"
                  : idea.rank >= 50
                    ? "bg-sky-500/20 text-sky-300"
                    : "bg-neutral-700 text-neutral-400"
              }`}
            >
              {idea.rank}
            </span>
          </Tooltip>
          <Tooltip content="Decrease priority">
            <button
              onClick={() => onUpdate(idea.id, { rank: Math.max(1, idea.rank - 10) })}
              className="text-neutral-500 hover:text-neutral-300 transition-colors p-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded"
              aria-label="Decrease priority"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          </Tooltip>
        </div>

        {/* Status badge */}
        <button
          onClick={handleStatusClick}
          className={`shrink-0 text-[10px] font-semibold px-2 py-1 rounded-md border transition-colors ${statusCfg.color} ${statusCfg.next ? "hover:brightness-125 cursor-pointer" : "cursor-default"}`}
          title={statusCfg.next ? `Click to advance to "${STATUS_CONFIG[statusCfg.next].label}"` : "Published (final)"}
        >
          {statusCfg.label}
        </button>

        {/* Text content */}
        <div className="flex-1 min-w-0">
          {editing ? (
            <textarea
              ref={inputRef}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onBlur={handleSave}
              onKeyDown={handleKeyDown}
              className="w-full bg-neutral-900 border border-neutral-600 rounded-lg px-3 py-2 text-sm text-neutral-100 resize-none focus:outline-none focus:border-violet-500"
              rows={2}
            />
          ) : (
            <div>
              <button
                onClick={() => setEditing(true)}
                className="text-left text-sm text-neutral-200 hover:text-neutral-100 transition-colors w-full"
              >
                {idea.text}
              </button>
              {idea.description && (
                <p className="text-xs text-neutral-400 mt-0.5 line-clamp-2">{idea.description}</p>
              )}
              <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                {sourceChip && (
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-md ${sourceChip.color}`}>
                    {sourceChip.label}
                  </span>
                )}
                {idea.category && (
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-neutral-700/50 text-neutral-400">
                    {idea.category}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onGenerateIdeas(idea.text)}
            className="text-xs px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition-colors"
          >
            Generate Ideas
          </button>
          <Tooltip content="Delete">
            <button
              onClick={() => onDelete(idea.id)}
              className="text-neutral-500 hover:text-red-400 transition-colors p-1.5 rounded-md hover:bg-neutral-700/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              aria-label="Delete idea"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
              </svg>
            </button>
          </Tooltip>
        </div>
      </div>
    </div>
  );
}
