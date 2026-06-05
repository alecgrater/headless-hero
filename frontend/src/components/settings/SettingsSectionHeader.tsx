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
    : `min-w-0 border-l-2 border-violet-500/60 pl-3 ${className}`.trim();
  const titleClassName = compact
    ? "text-sm font-semibold text-neutral-100"
    : "text-lg font-semibold tracking-tight text-neutral-100";
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
