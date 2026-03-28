import { assetUrl } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";

interface Props {
  content: ScriptContent;
  selectedSceneId: string | null;
  onSelectScene: (sceneId: string) => void;
}

export default function PreviewStrip({ content, selectedSceneId, onSelectScene }: Props) {
  const allScenes: Scene[] = content.segments.flatMap((seg) => seg.scenes);

  return (
    <div className="shrink-0 border-t border-neutral-800 bg-neutral-900/80 px-4 py-2 overflow-x-auto">
      <div className="flex gap-1.5">
        {allScenes.map((scene) => {
          const isSelected = scene.id === selectedSceneId;
          return (
            <button
              key={scene.id}
              onClick={() => onSelectScene(scene.id)}
              className={`shrink-0 w-16 h-10 rounded overflow-hidden border-2 transition-colors ${
                isSelected
                  ? "border-violet-500"
                  : "border-transparent hover:border-neutral-600"
              }`}
              title={scene.narration.slice(0, 50)}
            >
              {scene.image_url ? (
                <img
                  src={assetUrl(scene.image_url)}
                  alt=""
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full bg-neutral-800 flex items-center justify-center">
                  <span className="text-[8px] text-neutral-600">{scene.id.slice(-4)}</span>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
