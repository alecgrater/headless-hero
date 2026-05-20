import { assetUrl } from "../../api";
import type { ScriptContent } from "../../types/script";

interface Props {
  script: ScriptContent | null;
  scriptId: string;
  timestamp: number;
}

export function CinematicChaptersPreview({ script, scriptId, timestamp }: Props) {
  const levels = script?.levels ?? [];
  return (
    <div>
      <p className="text-xs text-neutral-500 mb-2">Cinematic thumbnail</p>
      <img
        className="rounded mb-4 w-full max-w-md border border-neutral-700"
        src={assetUrl(`/static/projects/${scriptId}/images/cinematic_thumbnail.png?t=${timestamp}`)}
        alt="Cinematic thumbnail"
      />

      <p className="text-xs text-neutral-500 mb-2">Chapter cards</p>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {levels.map((level) => (
          <div key={level.number} className="shrink-0 w-48">
            <img
              className="rounded mb-1.5 aspect-video object-cover border border-neutral-700"
              src={assetUrl(`/static/projects/${scriptId}/images/chapter_${level.number}.png?t=${timestamp}`)}
              alt={`Level ${level.number}`}
            />
            <div className="text-[10px] text-neutral-500 uppercase tracking-wide">
              Level {level.number}
            </div>
            <div className="text-xs text-neutral-200 truncate">
              The {level.descriptor}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default CinematicChaptersPreview;
