import type { RefinedHookResult } from "../../types/script";

interface Props {
  result: RefinedHookResult;
}

export default function HookRefinementResult({ result }: Props) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-3">
        <h4 className="text-xs font-medium uppercase tracking-wider text-neutral-500">
          Original
        </h4>
        <p className="text-sm text-neutral-500 italic leading-relaxed">
          &ldquo;{result.original_hook.intro_hook}&rdquo;
        </p>
        <p className="text-xs text-neutral-600 leading-relaxed">
          {result.original_hook.opening_narration}
        </p>
      </div>

      <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4 space-y-3">
        <h4 className="text-xs font-medium uppercase tracking-wider text-violet-400">
          Refined
        </h4>
        <p className="text-sm text-neutral-100 italic leading-relaxed">
          &ldquo;{result.refined_hook.intro_hook}&rdquo;
        </p>
        <p className="text-xs text-neutral-400 leading-relaxed">
          {result.refined_hook.opening_narration}
        </p>
      </div>
    </div>
  );
}
