import type { ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}

const positionClasses = {
  top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
  bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
  left: "right-full top-1/2 -translate-y-1/2 mr-2",
  right: "left-full top-1/2 -translate-y-1/2 ml-2",
};

const arrowClasses = {
  top: "top-full left-1/2 -translate-x-1/2 border-t-neutral-700 border-x-transparent border-b-transparent border-4",
  bottom: "bottom-full left-1/2 -translate-x-1/2 border-b-neutral-700 border-x-transparent border-t-transparent border-4",
  left: "left-full top-1/2 -translate-y-1/2 border-l-neutral-700 border-y-transparent border-r-transparent border-4",
  right: "right-full top-1/2 -translate-y-1/2 border-r-neutral-700 border-y-transparent border-l-transparent border-4",
};

export function Tooltip({ content, children, side = "top" }: TooltipProps) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={[
          "pointer-events-none absolute z-50 w-max max-w-80 whitespace-normal break-words",
          "rounded-md bg-neutral-700 px-2 py-1 text-left text-xs leading-snug text-neutral-200 shadow-lg",
          "opacity-0 group-hover:opacity-100",
          "transition-opacity duration-150 delay-0 group-hover:delay-300",
          "animate-[tooltipFade_150ms_ease-out]",
          positionClasses[side],
        ].join(" ")}
      >
        {content}
        <span className={`absolute ${arrowClasses[side]}`} />
      </span>
    </span>
  );
}
