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
    : `relative min-w-0 ${className}`.trim();
  const titleClassName = compact
    ? "text-sm font-semibold text-neutral-100"
    : "text-xl font-semibold tracking-tight text-neutral-100";
  const Heading = level === 2 ? "h2" : "h3";

  return (
    <div className={wrapperClassName}>
      {!compact && (
        <span
          aria-hidden="true"
          className="absolute -left-4 top-1 h-9 w-1 rounded-full bg-gradient-to-b from-violet-400 via-violet-500 to-sky-400 shadow-[0_0_18px_rgba(139,92,246,0.45)]"
        />
      )}
      <Heading className={titleClassName}>{title}</Heading>
      {description && (
        <p className={`text-xs leading-relaxed text-neutral-500 ${descriptionClassName}`.trim()}>
          {description}
        </p>
      )}
    </div>
  );
}
