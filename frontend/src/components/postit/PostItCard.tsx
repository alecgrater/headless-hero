import { useState, useRef, useEffect } from "react";
import type { PostIt } from "../../types/postit";

interface Props {
  postit: PostIt;
  onUpdate: (id: string, updates: { text?: string; rank?: number }) => void;
  onDelete: (id: string) => void;
  onGenerateIdeas: (niche: string) => void;
}

export default function PostItCard({ postit, onUpdate, onDelete, onGenerateIdeas }: Props) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(postit.text);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const handleSave = () => {
    const trimmed = editText.trim();
    if (trimmed && trimmed !== postit.text) {
      onUpdate(postit.id, { text: trimmed });
    }
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === "Escape") {
      setEditText(postit.text);
      setEditing(false);
    }
  };

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-800/50 p-4 hover:border-neutral-600 transition-colors">
      <div className="flex items-start gap-3">
        {/* Rank badge */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          <button
            onClick={() => onUpdate(postit.id, { rank: Math.min(100, postit.rank + 10) })}
            className="text-neutral-500 hover:text-neutral-300 transition-colors p-0.5"
            title="Increase priority"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
            </svg>
          </button>
          <span
            className={`text-xs font-bold px-2 py-0.5 rounded-full ${
              postit.rank >= 75
                ? "bg-violet-500/20 text-violet-300"
                : postit.rank >= 50
                  ? "bg-sky-500/20 text-sky-300"
                  : "bg-neutral-700 text-neutral-400"
            }`}
            title={`Priority: ${postit.rank}`}
          >
            {postit.rank}
          </span>
          <button
            onClick={() => onUpdate(postit.id, { rank: Math.max(1, postit.rank - 10) })}
            className="text-neutral-500 hover:text-neutral-300 transition-colors p-0.5"
            title="Decrease priority"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
        </div>

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
            <button
              onClick={() => setEditing(true)}
              className="text-left text-sm text-neutral-200 hover:text-neutral-100 transition-colors w-full"
            >
              {postit.text}
            </button>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onGenerateIdeas(postit.text)}
            className="text-xs px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition-colors"
          >
            Generate Ideas
          </button>
          <button
            onClick={() => onDelete(postit.id)}
            className="text-neutral-500 hover:text-red-400 transition-colors p-1.5 rounded-md hover:bg-neutral-700/50"
            title="Delete"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
