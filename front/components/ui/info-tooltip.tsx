import { CircleHelp } from "lucide-react";

import { cn } from "@/lib/utils";

type InfoTooltipProps = {
  label: string;
  description: string;
  align?: "left" | "center" | "right";
  className?: string;
};

const ALIGN_CLASS = {
  left: "left-0",
  center: "left-1/2 -translate-x-1/2",
  right: "right-0",
} as const;

/**
 * 용어 옆에 붙는 짧은 설명 상자.
 * 마우스를 올리거나 키보드로 초점을 옮기면 열리고, 터치 화면에서는 한 번 눌러 볼 수 있다.
 */
export function InfoTooltip({
  label,
  description,
  align = "left",
  className,
}: InfoTooltipProps) {
  return (
    <span className={cn("group relative inline-flex max-w-full align-baseline", className)}>
      <button
        type="button"
        aria-label={`${label} 설명: ${description}`}
        className="inline-flex cursor-help items-center gap-1 rounded-sm text-left decoration-border underline decoration-dotted underline-offset-4 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span>{label}</span>
        <CircleHelp aria-hidden="true" className="size-3.5 shrink-0" strokeWidth={2} />
      </button>
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none invisible absolute top-[calc(100%+0.5rem)] z-50 w-64 max-w-[calc(100vw-3rem)] rounded-md bg-foreground px-3 py-2 text-xs font-normal leading-relaxed tracking-normal text-background opacity-0 shadow-float transition-opacity duration-150 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100",
          ALIGN_CLASS[align],
        )}
      >
        {description}
      </span>
    </span>
  );
}
