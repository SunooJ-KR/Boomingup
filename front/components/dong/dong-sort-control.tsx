"use client";

import { ArrowUpDown, ChevronDown } from "lucide-react";

import {
  DEFAULT_DONG_SORT,
  regionTagMetricLabel,
  type DongSort,
  type SortDirection,
} from "@/lib/filter";

type DongSortControlProps = {
  sort: DongSort;
  tags: string[];
  onChange: (sort: DongSort) => void;
};

const TAG_ORDER = [
  "거래 많은 동",
  "전세가율 높은 동",
  "최근 준공 많은 동",
  "30년 이상 단지 많은 동",
  "정비사업 정보 있음",
];

export function DongSortControl({ sort, tags, onChange }: DongSortControlProps) {
  const orderedTags = [...tags].sort((a, b) => orderOf(a) - orderOf(b));

  return (
    <div className="relative min-w-0 flex-1">
      <label htmlFor="dong-list-sort" className="sr-only">
        동 목록 정렬 기준
      </label>
      <ArrowUpDown
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-primary"
      />
      <select
        id="dong-list-sort"
        aria-label="동 목록 정렬 기준"
        value={sortValue(sort)}
        onChange={(event) => onChange(parseSort(event.target.value))}
        className="h-10 w-full appearance-none truncate rounded-md border border-border bg-card pl-10 pr-7 text-[11px] font-medium text-foreground shadow-sm hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring lg:h-8 2xl:h-9 2xl:text-xs"
      >
        <option value="default">기본 정렬</option>
        <optgroup label="가격">
          <option value="price:desc">㎡당 중앙가 높은순</option>
          <option value="price:asc">㎡당 중앙가 낮은순</option>
        </optgroup>
        <optgroup label="지역 특성">
          {orderedTags.flatMap((tag) => {
            const label = regionTagMetricLabel(tag);
            return [
              <option key={`${tag}-desc`} value={tagValue(tag, "desc")}>
                {label} 높은순
              </option>,
              <option key={`${tag}-asc`} value={tagValue(tag, "asc")}>
                {label} 낮은순
              </option>,
            ];
          })}
        </optgroup>
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  );
}

function orderOf(tag: string): number {
  const index = TAG_ORDER.indexOf(tag);
  return index === -1 ? TAG_ORDER.length : index;
}

function sortValue(sort: DongSort): string {
  if (sort.by === "default") return "default";
  if (sort.by === "price") return `price:${sort.direction}`;
  return tagValue(sort.tag, sort.direction);
}

function tagValue(tag: string, direction: SortDirection): string {
  return `tag:${direction}:${encodeURIComponent(tag)}`;
}

function parseSort(value: string): DongSort {
  if (value === "price:desc") return { by: "price", direction: "desc" };
  if (value === "price:asc") return { by: "price", direction: "asc" };

  const match = /^tag:(desc|asc):(.+)$/.exec(value);
  if (!match) return DEFAULT_DONG_SORT;
  return {
    by: "tag",
    direction: match[1] as SortDirection,
    tag: decodeURIComponent(match[2]),
  };
}
