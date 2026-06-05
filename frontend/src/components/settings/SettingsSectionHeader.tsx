interface SettingsSectionHeaderProps {
  title: string;
  description?: string;
  compact?: boolean;
  level?: 2 | 3;
  className?: string;
  descriptionClassName?: string;
}

export default function SettingsSectionHeader({
  title,
  description,
  compact = false,
  level = 3,
  className = "",
  descriptionClassName = "",
}: SettingsSectionHeaderProps) {
  const wrapperClassName = compact
    ? `min-w-0 ${className}`.trim()
    : `-ml-4 min-w-0 rounded-2xl border border-violet-500/40 bg-violet-500/5 px-4 py-3 shadow-[0_0_0_1px_rgba(139,92,246,0.08)] ${className}`.trim();
  const titleClassName = compact
    ? "text-sm font-semibold text-neutral-100"
    : "text-xl font-semibold tracking-tight text-neutral-100";
  const Heading = level === 2 ? "h2" : "h3";

  return (
    <div className={wrapperClassName}>
      <Heading className={titleClassName}>{title}</Heading>
      {description && (
        <p className={`text-xs leading-relaxed text-neutral-500 ${descriptionClassName}`.trim()}>
          {description}
        </p>
      )}
    </div>
  );
}
