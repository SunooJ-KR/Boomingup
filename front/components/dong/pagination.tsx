"use client";

import { pageWindow } from "@/lib/paginate";
import { cn } from "@/lib/utils";

type PaginationProps = {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
};

/** 동 목록을 번호로 넘긴다. 페이지가 하나뿐이면 아무것도 그리지 않는다. */
export function Pagination({ page, totalPages, onChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <nav aria-label="동 목록 페이지" className="flex flex-wrap items-center justify-center gap-1">
      <StepButton label="이전 페이지" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        ‹
      </StepButton>

      {pageWindow(page, totalPages).map((slot, at) =>
        slot === "gap" ? (
          <span key={`gap-${at}`} aria-hidden className="px-1 text-xs text-muted-foreground">
            …
          </span>
        ) : (
          <button
            key={slot}
            type="button"
            aria-label={`${slot}페이지`}
            aria-current={slot === page ? "page" : undefined}
            onClick={() => onChange(slot)}
            className={cn(
              "h-8 min-w-8 rounded-md border px-2 text-xs font-medium tabular-nums transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              slot === page
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-muted-foreground hover:bg-muted",
            )}
          >
            {slot}
          </button>
        ),
      )}

      <StepButton
        label="다음 페이지"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
      >
        ›
      </StepButton>
    </nav>
  );
}

function StepButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="h-8 min-w-8 rounded-md border border-border bg-card px-2 text-xs text-muted-foreground transition-opacity hover:bg-muted disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {children}
    </button>
  );
}
