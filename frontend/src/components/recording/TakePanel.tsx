import { useRef, useState } from "react";

export interface Take {
  filename: string;
  takeNumber: number;
  durationSeconds: number;
  sceneId: string;
}

interface Props {
  sceneId: string | null;
  takes: Take[];
  selectedTakeNumber: number | null;
  onSelectTake: (takeNumber: number) => void;
  onDeleteTake: (takeNumber: number) => void;
  onPlayTake: (take: Take) => void;
  onRecordNew: () => void;
  onImport: (file: File) => void;
  playingTakeNumber: number | null;
  trimEndSeconds: number | null;
  onTrimChange: (seconds: number | null) => void;
  showTrim: boolean;
  onToggleTrim: () => void;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}

export default function TakePanel({
  sceneId, takes, selectedTakeNumber, onSelectTake, onDeleteTake, onPlayTake,
  onRecordNew, onImport, playingTakeNumber, trimEndSeconds, onTrimChange, showTrim, onToggleTrim,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const sceneTakes = takes.filter((t) => t.sceneId === sceneId);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && /\.(mp3|wav|m4a|webm|ogg)$/i.test(file.name)) {
      onImport(file);
    }
  };

  if (!sceneId) {
    return (
      <div className="w-[200px] shrink-0 border-l border-neutral-800 flex items-center justify-center">
        <span className="text-xs text-neutral-600">Select a scene</span>
      </div>
    );
  }

  return (
    <div className="w-[200px] shrink-0 border-l border-neutral-800 flex flex-col h-full overflow-hidden">
      <div className="px-3 py-2 border-b border-neutral-800">
        <div className="text-xs font-medium text-neutral-300">Takes</div>
      </div>

      <div
        className={`flex-1 overflow-y-auto ${dragOver ? "bg-violet-500/5 ring-1 ring-inset ring-violet-500/30" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {sceneTakes.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-neutral-600">
            No takes yet. Record or drop an audio file here.
          </div>
        ) : (
          sceneTakes.map((take) => (
            <div
              key={take.takeNumber}
              className={`px-3 py-2 border-b border-neutral-800/50 transition-colors ${
                selectedTakeNumber === take.takeNumber ? "bg-violet-500/10" : "hover:bg-neutral-800/50"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] text-neutral-400 tabular-nums">Take {take.takeNumber}</span>
                <span className="text-[11px] text-neutral-500 tabular-nums">{formatDuration(take.durationSeconds)}</span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => onPlayTake(take)}
                  className={`p-1 rounded transition-colors ${
                    playingTakeNumber === take.takeNumber ? "text-violet-400 bg-violet-500/10" : "text-neutral-500 hover:text-neutral-300"
                  }`}
                  title="Play"
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                    {playingTakeNumber === take.takeNumber ? (
                      <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                    ) : (
                      <path d="M8 5v14l11-7z" />
                    )}
                  </svg>
                </button>
                <button
                  onClick={() => onSelectTake(take.takeNumber)}
                  className={`p-1 rounded transition-colors ${
                    selectedTakeNumber === take.takeNumber ? "text-emerald-400" : "text-neutral-600 hover:text-neutral-300"
                  }`}
                  title="Use this take"
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
                  </svg>
                </button>
                <button
                  onClick={() => onDeleteTake(take.takeNumber)}
                  className="p-1 rounded text-neutral-600 hover:text-red-400 transition-colors"
                  title="Delete"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Trim control */}
      {selectedTakeNumber && (
        <div className="px-3 py-2 border-t border-neutral-800">
          <button
            onClick={onToggleTrim}
            className={`text-[11px] w-full py-1 rounded transition-colors ${
              showTrim ? "bg-violet-500/15 text-violet-300" : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
            }`}
          >
            Trim End {trimEndSeconds !== null ? `(${formatDuration(trimEndSeconds)})` : ""}
          </button>
          {showTrim && (
            <div className="mt-2">
              <input
                type="range"
                min={0}
                max={sceneTakes.find((t) => t.takeNumber === selectedTakeNumber)?.durationSeconds || 10}
                step={0.1}
                value={trimEndSeconds ?? (sceneTakes.find((t) => t.takeNumber === selectedTakeNumber)?.durationSeconds || 0)}
                onChange={(e) => onTrimChange(parseFloat(e.target.value))}
                className="w-full h-1 accent-violet-500"
              />
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="px-3 py-2 border-t border-neutral-800 flex flex-col gap-1.5">
        <button
          onClick={onRecordNew}
          className="w-full text-xs py-2 bg-red-500/10 border border-red-500/25 text-red-400 hover:bg-red-500/20 rounded-lg font-medium transition-colors"
        >
          Record New Take
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="w-full text-xs py-1.5 text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 rounded-md transition-colors"
        >
          Import Audio
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp3,.wav,.m4a,.webm,.ogg"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onImport(file);
            e.target.value = "";
          }}
        />
      </div>
    </div>
  );
}
