import { useState, useRef, useEffect } from "react";
import { ArrowRight, Trash2 } from "lucide-react";
import type { Idea, IdeaStatus } from "../../types/idea";
import { Tooltip } from "../ui/Tooltip";

const SOURCE_LABEL: Partial<Record<Idea["source"], string>> = {
  for_you: "For You",
  trending: "Trending",
};

interface Props {
  idea: Idea;
  onUpdate: (id: string, updates: { text?: string; status?: IdeaStatus }) => void;
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

  const metaItems = [SOURCE_LABEL[idea.source], idea.category].filter(Boolean);

  return (
    <div className="group border-b border-neutral-800/80 bg-neutral-950/0 px-5 py-4 transition-colors last:border-b-0 hover:bg-neutral-900/70">
      <div className="flex items-center gap-4">
        {/* Text content */}
        <div className="flex-1 min-w-0">
          {editing ? (
            <textarea
              ref={inputRef}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onBlur={handleSave}
              onKeyDown={handleKeyDown}
              className="w-full resize-none rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
              rows={2}
            />
          ) : (
            <div>
              <button
                onClick={() => setEditing(true)}
                className="w-full text-left text-[15px] font-medium leading-snug text-neutral-200 transition-colors hover:text-neutral-50"
              >
                {idea.text}
              </button>
              {idea.description && (
                <p className="mt-1 line-clamp-2 text-sm leading-5 text-neutral-500">{idea.description}</p>
              )}
              {metaItems.length > 0 && (
                <p className="mt-2 text-xs text-neutral-600">{metaItems.join(" / ")}</p>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={() => onGenerateIdeas(idea.text)}
            aria-label="Generate script ideas"
            className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white opacity-90 transition-colors hover:bg-violet-500 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
          >
            Develop
            <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
          <Tooltip content="Delete">
            <button
              onClick={() => onDelete(idea.id)}
              className="rounded-md p-2 text-neutral-600 opacity-0 transition-colors hover:bg-neutral-800 hover:text-red-400 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 group-hover:opacity-100"
              aria-label="Delete idea"
            >
              <Trash2 className="w-4 h-4" strokeWidth={1.5} />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>
  );
}
