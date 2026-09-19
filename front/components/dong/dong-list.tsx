"use client";

import { ChevronDown, Palette } from "lucide-react";

import type { StructureOption } from "@/components/dong/search-panel";
import { Badge } from "@/components/ui/badge";
import { formatManwon } from "@/lib/format";
import { structureBackgroundClass, structureTextClass } from "@/lib/structure";
import type { DongSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

type DongListProps = {
  dongs: DongSummary[];
  selectedId: string | null;
  onSelect: (dongId: string) => void;
};

export function DongList({ dongs, selectedId, onSelect }: DongListProps) {
  return (
    <ul className="space-y-2 lg:space-y-1.5 2xl:space-y-2">
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

export function DongListLegend({ options }: { options: StructureOption[] }) {
  if (options.length === 0) return null;

  return (
    <details className="group relative">
      <summary className="flex min-h-8 cursor-pointer list-none items-center gap-1.5 rounded-md px-2 text-xs font-medium text-muted-foreground marker:content-none hover:bg-card hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:min-h-7 2xl:min-h-8">
        <Palette aria-hidden="true" className="size-3.5" />
        클러스터 색상
        <ChevronDown
          aria-hidden="true"
          className="size-3.5 transition-transform group-open:rotate-180"
        />
      </summary>
      <div className="absolute right-0 top-full z-30 mt-1 w-72 max-w-[calc(100vw-2rem)] space-y-2 rounded-md border border-border bg-card p-3 shadow-float">
        {options.map((option) => (
          <div key={option.type} className="flex items-start gap-2 text-xs text-foreground">
            <span
              aria-hidden="true"
              className={cn(
                "mt-0.5 size-3 shrink-0 rounded-sm",
                structureBackgroundClass(option.type),
              )}
            />
            <span>{option.desc}</span>
          </div>
        ))}
      </div>
    </details>
  );
}

/**
 * 목록에는 변화율을 싣지 않는다. 행에 변화율이 있으면 눈으로 정렬하게 되고,
 * 오차를 뗀 숫자만 남기 때문이다(payload-schema.md §3).
 */
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
        "w-full break-keep rounded-lg border bg-card px-3 py-2.5 text-left shadow-panel transition-transform duration-150 ease-[var(--ease-out-soft)] hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:py-2 2xl:py-2.5",
        selected ? "border-primary bg-primary-soft/40" : "border-border",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-baseline gap-1.5">
          <p className={cn("truncate text-sm font-bold", structureTextClass(dong.structure_type))}>
            {dong.umd_name}
          </p>
          <p className="shrink-0 text-xs text-muted-foreground">{dong.gu_name}</p>
        </div>
        {dong.sample_flags.length > 0 ? (
          <Badge variant="neutral" className="shrink-0">
            주의
          </Badge>
        ) : null}
      </div>

      {dong.ppm2_med_4q_manwon !== null ? (
        <p className="mt-1 text-xs text-muted-foreground">
          ㎡당 중앙가 {formatManwon(dong.ppm2_med_4q_manwon)}
        </p>
      ) : null}
    </button>
  );
}
