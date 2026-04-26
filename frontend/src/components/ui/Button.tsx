import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

const variantClasses = {
  primary:
    "bg-gradient-to-br from-violet-600 to-violet-500 text-white shadow-sm hover:shadow-lg hover:shadow-violet-500/20",
  secondary:
    "border border-neutral-700 text-neutral-300 hover:bg-neutral-800 hover:text-neutral-100",
  danger:
    "bg-red-600/90 text-white hover:bg-red-500",
  success:
    "bg-emerald-600/90 text-white hover:bg-emerald-500",
  ghost:
    "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/60",
} as const;

const sizeClasses = {
  sm: "text-xs px-3 py-1.5 rounded-lg gap-1.5",
  md: "text-sm px-4 py-2 rounded-lg gap-2",
  lg: "text-sm px-5 py-2.5 rounded-lg gap-2",
} as const;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variantClasses;
  size?: keyof typeof sizeClasses;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "secondary", size = "md", loading, icon, children, className = "", disabled, ...rest }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={[
        "inline-flex items-center justify-center font-medium",
        "transition-all duration-150 cursor-pointer",
        "active:scale-[0.97]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950",
        "disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100",
        variantClasses[variant],
        sizeClasses[size],
        className,
      ].join(" ")}
      {...rest}
    >
      {loading ? (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  ),
);

Button.displayName = "Button";
