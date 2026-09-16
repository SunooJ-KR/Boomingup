"use client";

import { StatusBadge } from "@/components/dong/status-badge";
import { formatPct, statusReason } from "@/lib/format";
import type { DongSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

type DongListProps = {
  dongs: DongSummary[];
  selectedId: string | null;
  onSelect: (dongId: string) => void;
};

export function DongList({ dongs, selectedId, onSelect }: DongListProps) {
  return (
    <ul className="space-y-2">
      {dongs.map((dong) => (
        <li key={dong.dong_id}>
          <DongListItem
            dong={dong}
            selected={dong.dong_id === selectedId}
            onSelect={() => onSelect(dong.dong_id)}
          />
        </li>
      ))}
    </ul>
  );
}

function DongListItem({
  dong,
  selected,
  onSelect,
}: {
  dong: DongSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "w-full break-keep rounded-lg border bg-card p-3 text-left shadow-panel transition-transform duration-150 ease-[var(--ease-out-soft)] hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "border-primary bg-primary-soft/40" : "border-border",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-bold text-foreground">{dong.umd_name}</p>
          <p className="text-xs text-muted-foreground">{dong.gu_name}</p>
        </div>
        <StatusBadge status={dong.status} />
      </div>

      {/* 매매 건수는 "매매 20 / 건"처럼 끊기면 읽기 나쁘므로 줄바꿈하지 않고 폭도 양보하지 않는다.
          왼쪽 사유가 남는 폭에서 접힌다. 카드에 건 break-keep이 낱말 가운데를 가르지 않게 막아 준다. */}
      <div className="mt-2 flex items-baseline justify-between gap-2">
        {dong.status === "PREDICTED" ? (
          <p className="text-lg font-bold tabular-nums text-foreground">
            {formatPct(dong.change_pct_est)}
          </p>
        ) : (
          <p className="min-w-0 text-xs text-muted-foreground">
            {statusReason(dong.status, dong.status_reason)}
          </p>
        )}
        <p className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">
          최근 1년 매매 {dong.n_sales_4q}건
        </p>
      </div>

      {dong.tags && dong.tags.length > 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">{dong.tags.join(" · ")}</p>
      ) : null}
    </button>
  );
}
