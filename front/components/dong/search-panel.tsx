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

  const detailCount = filter.statuses.length + filter.tags.length;

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <label htmlFor="dong-search" className="text-sm font-medium text-foreground">
          법정동 검색
        </label>
        <Input
          id="dong-search"
          type="search"
          placeholder="예: 개포동, 강남구"
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

      {/* 상태와 태그 칩이 좌측 열 높이의 절반쯤을 먹어 목록이 밀린다.
          접어 두고 몇 개 걸렸는지만 알려준 뒤, 필요할 때 펼치게 한다. */}
      {/* open을 값으로 넘기면 다시 그릴 때마다 React가 상태를 되돌려 펼친 칩이 접힌다.
          열고 닫는 상태는 브라우저에 맡기고 여기서는 몇 개 걸렸는지만 알려준다. */}
      <details className="rounded-md border border-border bg-card px-3 py-2">
        <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-foreground">
          <span>상세 필터</span>
          <span className="text-xs font-normal text-muted-foreground">
            {detailCount > 0 ? `${detailCount}개 적용` : "전체"}
          </span>
        </summary>

        <div className="space-y-4 pt-3">
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
                태그는 동네에서 관측된 특징이에요. 좋고 나쁨을 뜻하지 않아요.
              </p>
            </fieldset>
          ) : null}
        </div>
      </details>

      <div className="flex items-center justify-between">
        <Badge variant="neutral">{resultCount}개 동</Badge>
        {isFilterActive(filter) ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange({ query: "", gu: null, statuses: [], tags: [] })}
          >
            필터 지우기
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
