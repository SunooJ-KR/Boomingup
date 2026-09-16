"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { statusLabel } from "@/lib/format";
import type { DongFilter } from "@/lib/filter";
import { isFilterActive } from "@/lib/filter";
import type { PredictionStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUSES: PredictionStatus[] = ["PREDICTED", "INSUFFICIENT_SALES", "NOT_SERVED"];

type SearchPanelProps = {
  filter: DongFilter;
  onChange: (filter: DongFilter) => void;
  guNames: string[];
  tags: string[];
  resultCount: number;
};

export function SearchPanel({ filter, onChange, guNames, tags, resultCount }: SearchPanelProps) {
  const toggleStatus = (status: PredictionStatus) => {
    const next = filter.statuses.includes(status)
      ? filter.statuses.filter((item) => item !== status)
      : [...filter.statuses, status];
    onChange({ ...filter, statuses: next });
  };

  const toggleTag = (tag: string) => {
    const next = filter.tags.includes(tag)
      ? filter.tags.filter((item) => item !== tag)
      : [...filter.tags, tag];
    onChange({ ...filter, tags: next });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <label htmlFor="dong-search" className="text-sm font-medium text-foreground">
          법정동 검색
        </label>
        <Input
          id="dong-search"
          type="search"
          placeholder="동 이름 또는 자치구 이름"
          value={filter.query}
          onChange={(event) => onChange({ ...filter, query: event.target.value })}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="dong-gu" className="text-sm font-medium text-foreground">
          자치구
        </label>
        <select
          id="dong-gu"
          className="h-10 w-full rounded-md border border-border bg-input px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          value={filter.gu ?? ""}
          onChange={(event) => onChange({ ...filter, gu: event.target.value || null })}
        >
          <option value="">전체</option>
          {guNames.map((gu) => (
            <option key={gu} value={gu}>
              {gu}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="space-y-1.5">
        <legend className="text-sm font-medium text-foreground">예측 상태</legend>
        <div className="flex flex-wrap gap-1.5">
          {STATUSES.map((status) => (
            <FilterChip
              key={status}
              label={statusLabel(status)}
              active={filter.statuses.includes(status)}
              onClick={() => toggleStatus(status)}
            />
          ))}
        </div>
      </fieldset>

      {tags.length > 0 ? (
        <fieldset className="space-y-1.5">
          <legend className="text-sm font-medium text-foreground">지역 태그</legend>
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <FilterChip
                key={tag}
                label={tag}
                active={filter.tags.includes(tag)}
                onClick={() => toggleTag(tag)}
              />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            태그는 지역의 관측된 특징이며 좋고 나쁨을 뜻하지 않습니다.
          </p>
        </fieldset>
      ) : null}

      <div className="flex items-center justify-between">
        <Badge variant="neutral">{resultCount}개 동</Badge>
        {isFilterActive(filter) ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange({ query: "", gu: null, statuses: [], tags: [] })}
          >
            필터 초기화
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-sm border px-2.5 py-1 text-xs font-medium transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary bg-primary-soft text-primary"
          : "border-border bg-card text-muted-foreground hover:bg-muted",
      )}
    >
      {label}
    </button>
  );
}
