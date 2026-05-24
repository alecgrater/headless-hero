import { X } from "lucide-react";

import { getProjectConfig, type ProjectConfig } from "../../api";
import { MainCharacterSection } from "../settings/MainCharacterSection";

type Props = {
  scriptId: string;
  config: ProjectConfig;
  onClose: () => void;
  onUpdated: (next: ProjectConfig) => void;
};

export default function MainCharacterDrawer({
  scriptId,
  onClose,
  onUpdated,
}: Props) {
  const handleContinue = async () => {
    const res = await getProjectConfig(scriptId);
    if (res.ok) {
      onUpdated(res.data as ProjectConfig);
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onClick={onClose}>
      <div
        className="h-full w-[720px] max-w-[92vw] overflow-y-auto border-l border-neutral-800 bg-neutral-950 p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-neutral-100">Main Character</h2>
            <p className="mt-1 text-sm text-neutral-400">
              This project uses the global main character. Continue with the active reference or change it here.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close main character panel"
            className="flex size-9 items-center justify-center rounded-md text-neutral-500 hover:bg-neutral-900 hover:text-neutral-200 transition-colors"
          >
            <X className="size-5" />
          </button>
        </div>

        <MainCharacterSection compact onContinue={handleContinue} />
      </div>
    </div>
  );
}
