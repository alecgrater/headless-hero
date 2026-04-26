import type { ReactNode } from "react";

const variantClasses = {
  default: "bg-neutral-700/50 text-neutral-300",
  success: "bg-emerald-500/15 text-emerald-400",
  warning: "bg-amber-500/15 text-amber-400",
  danger: "bg-red-500/15 text-red-400",
  info: "bg-sky-500/15 text-sky-400",
  violet: "bg-violet-500/15 text-violet-400",
} as const;

interface BadgeProps {
  variant?: keyof typeof variantClasses;
  children: ReactNode;
  className?: string;
}

export function Badge({ variant = "default", children, className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded-full ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
