import { useState } from "react";

interface Preset {
  name: string;
  [key: string]: unknown;
}

interface Props<T extends Preset> {
  presets: T[];
  value: string;
  onChange: (value: string) => void;
  getValue: (preset: T) => string;
  renderPreview: (preset: T) => React.ReactNode;
  label: string;
}

export default function PresetCarousel<T extends Preset>({
  presets,
  value,
  onChange,
  getValue,
  renderPreview,
  label,
}: Props<T>) {
  const [customMode, setCustomMode] = useState(() => {
    if (!value) return false;
    return !presets.some((p) => getValue(p) === value);
  });

  const currentIndex = presets.findIndex((p) => getValue(p) === value);
  const activeIndex = currentIndex >= 0 ? currentIndex : 0;

  const go = (direction: -1 | 1) => {
    const next =
      (activeIndex + direction + presets.length) % presets.length;
    onChange(getValue(presets[next]));
  };

  const selectByIndex = (idx: number) => {
    onChange(getValue(presets[idx]));
  };

  if (customMode) {
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium tracking-[0.08em] uppercase text-white/40 font-['Sora']">
            {label}
          </span>
          <button
            type="button"
            onClick={() => {
              setCustomMode(false);
              if (presets.length > 0) onChange(getValue(presets[0]));
            }}
            className="text-[11px] text-violet-400/70 hover:text-violet-400 transition-colors font-['Sora']"
          >
            Use Presets
          </button>
        </div>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full min-h-[80px] rounded-lg bg-[#1a1a24] border border-white/[0.08] px-3 py-3 text-[13px] text-white/90 placeholder:text-white/40 outline-none transition-all duration-200 focus:border-[rgba(124,58,237,0.6)] focus:shadow-[0_0_0_3px_rgba(124,58,237,0.15)] resize-y"
          placeholder={`Enter custom ${label.toLowerCase()}...`}
        />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium tracking-[0.08em] uppercase text-white/40 font-['Sora']">
          {label}
        </span>
        <button
          type="button"
          onClick={() => setCustomMode(true)}
          className="text-[11px] text-violet-400/70 hover:text-violet-400 transition-colors font-['Sora']"
        >
          Customize
        </button>
      </div>

      {/* Preview area with arrows */}
      <div className="relative group">
        <button
          type="button"
          onClick={() => go(-1)}
          className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 z-10 w-7 h-7 rounded-full bg-white/[0.08] hover:bg-white/[0.15] border border-white/[0.1] flex items-center justify-center text-white/50 hover:text-white/80 transition-all duration-200 opacity-0 group-hover:opacity-100"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <div
          className="rounded-lg bg-[#1a1a24] border border-white/[0.08] px-5 py-4 min-h-[72px] flex items-center justify-center cursor-pointer transition-all duration-200 hover:border-white/[0.15]"
          onClick={() => go(1)}
        >
          {presets.length > 0 && renderPreview(presets[activeIndex])}
        </div>

        <button
          type="button"
          onClick={() => go(1)}
          className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1 z-10 w-7 h-7 rounded-full bg-white/[0.08] hover:bg-white/[0.15] border border-white/[0.1] flex items-center justify-center text-white/50 hover:text-white/80 transition-all duration-200 opacity-0 group-hover:opacity-100"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Dot indicators */}
      <div className="flex justify-center gap-1.5">
        {presets.map((_, i) => (
          <button
            key={i}
            type="button"
            onClick={() => selectByIndex(i)}
            className={`w-1.5 h-1.5 rounded-full transition-all duration-200 ${
              i === activeIndex
                ? "bg-violet-400 w-3"
                : "bg-white/[0.15] hover:bg-white/[0.3]"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
