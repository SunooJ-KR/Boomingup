"use client";

import { useState, type ReactNode } from "react";
import { ArrowLeft, ChevronDown, MapPinned, Search, SlidersHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  EMPTY_FILTER,
  hasDetailFilter,
  regionTagLabel,
  type DongFilter,
} from "@/lib/filter";
import { compactClusterDesc, formatManwon } from "@/lib/format";
import { cn } from "@/lib/utils";

export type StructureOption = { type: number; desc: string };
type FilterSectionId = "sample" | "price" | "cluster" | "tag";

type SearchPanelProps = {
  filter: DongFilter;
  onChange: (filter: DongFilter) => void;
  guNames: string[];
  tags: string[];
  /** 가격대 칩. 전체 분포의 4분위로 화면이 만든다 */
  priceBands: [number, number][];
  /** 구조 유형 칩. 번호 대신 자동 설명을 붙인다 */
  structureOptions: StructureOption[];
  resultCount: number;
  onBack?: () => void;
};

export function SearchPanel({
  filter,
  onChange,
  guNames,
  tags,
  priceBands,
  structureOptions,
  resultCount,
  onBack,
}: SearchPanelProps) {
  const [openFilterSection, setOpenFilterSection] = useState<FilterSectionId | null>(null);

  const toggleTag = (tag: string) => {
    const next = filter.tags.includes(tag) ? [] : [tag];
    onChange({ ...filter, tags: next });
  };

  const toggleStructure = (type: number) => {
    const next = filter.structureTypes.includes(type)
      ? filter.structureTypes.filter((item) => item !== type)
      : [...filter.structureTypes, type];
    onChange({ ...filter, structureTypes: next });
  };

  const sameBand = (band: [number, number]) =>
    filter.priceBand !== null &&
    filter.priceBand[0] === band[0] &&
    filter.priceBand[1] === band[1];

  const detailCount =
    (filter.flagged === null ? 0 : 1) +
    (filter.priceBand === null ? 0 : 1) +
    filter.structureTypes.length +
    filter.tags.length;
  const refinementActive =
    filter.query.trim() !== "" ||
    hasDetailFilter(filter);

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4 shadow-panel">
      {filter.gu !== null && onBack ? (
        <div className="flex items-center justify-between gap-2 border-b border-border pb-3">
          <Button variant="ghost" size="sm" onClick={onBack} className="-ml-3">
            <ArrowLeft aria-hidden="true" className="size-4" />
            서울 전체
          </Button>
          <Badge variant="accent" className="px-2.5 py-1 text-sm">
            {filter.gu}
          </Badge>
        </div>
      ) : null}

      <div>
        <p className="text-xs font-semibold tracking-wide text-primary">지역 찾기</p>
        <h2 className="mt-1 text-lg font-bold text-foreground">어느 동을 살펴볼까요?</h2>
      </div>

      <div className="space-y-2">
        <div className="flex items-end justify-between gap-2">
          <label htmlFor="dong-search" className="text-sm font-bold text-foreground">
            법정동 검색
          </label>
          <span className="text-xs text-muted-foreground">동 이름 또는 자치구 이름</span>
        </div>
        <div className="relative">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-primary"
          />
          <Input
            id="dong-search"
            type="search"
            placeholder="예: 개포동, 강남구"
            value={filter.query}
            onChange={(event) => onChange({ ...filter, query: event.target.value })}
            className="h-12 border-primary/40 bg-card pl-11 text-base shadow-sm transition-colors hover:border-primary focus-visible:border-primary"
          />
        </div>
      </div>

      <div className="space-y-2 rounded-md bg-muted p-3">
        <label
          htmlFor="dong-gu"
          className="flex items-center gap-2 text-sm font-bold text-foreground"
        >
          <MapPinned aria-hidden="true" className="size-4 text-primary" />
          자치구 선택
        </label>
        <div className="relative">
          <select
            id="dong-gu"
            className="h-11 w-full appearance-none rounded-md border border-border bg-card px-3 pr-10 text-sm font-medium text-foreground shadow-sm hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={filter.gu ?? ""}
            onChange={(event) => onChange({ ...filter, gu: event.target.value || null })}
          >
            <option value="">서울 전체</option>
            {guNames.map((gu) => (
              <option key={gu} value={gu}>
                {gu}
              </option>
            ))}
          </select>
          <ChevronDown
            aria-hidden="true"
            className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          />
        </div>
      </div>

      {/* 칩이 좌측 열 높이의 절반쯤을 먹어 목록이 밀린다.
          접어 두고 몇 개 걸렸는지만 알려준 뒤, 필요할 때 펼치게 한다. */}
      {/* open을 값으로 넘기면 다시 그릴 때마다 React가 상태를 되돌려 펼친 칩이 접힌다.
          열고 닫는 상태는 브라우저에 맡기고 여기서는 몇 개 걸렸는지만 알려준다. */}
      <details className="group overflow-hidden rounded-md border border-border bg-card">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-sm font-bold text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
          <span className="flex items-center gap-2">
            <SlidersHorizontal aria-hidden="true" className="size-4 text-primary" />
            조건 필터
          </span>
          <span className="flex items-center gap-2">
            <Badge variant={detailCount > 0 ? "accent" : "neutral"}>
              {detailCount > 0 ? `${detailCount}개 적용` : "선택 안 함"}
            </Badge>
            <ChevronDown
              aria-hidden="true"
              className="size-4 text-muted-foreground transition-transform group-open:rotate-180"
            />
          </span>
        </summary>

        <div className="max-h-[clamp(12rem,32dvh,22rem)] space-y-1 overflow-y-auto overscroll-contain border-t border-border bg-muted/50 p-2">
          <FilterSection
            id="sample"
            label="표본 상태"
            selectedCount={filter.flagged === null ? 0 : 1}
            open={openFilterSection === "sample"}
            onToggle={() =>
              setOpenFilterSection((current) => (current === "sample" ? null : "sample"))
            }
          >
            <div className="flex flex-wrap gap-1.5">
              <FilterChip
                label="주의 없음"
                active={filter.flagged === false}
                onClick={() =>
                  onChange({ ...filter, flagged: filter.flagged === false ? null : false })
                }
              />
              <FilterChip
                label="주의 있음"
                active={filter.flagged === true}
                onClick={() =>
                  onChange({ ...filter, flagged: filter.flagged === true ? null : true })
                }
              />
            </div>
          </FilterSection>

          {priceBands.length > 0 ? (
            <FilterSection
              id="price"
              label="㎡당 매매 중앙가"
              selectedCount={filter.priceBand === null ? 0 : 1}
              open={openFilterSection === "price"}
              onToggle={() =>
                setOpenFilterSection((current) => (current === "price" ? null : "price"))
              }
            >
              <div className="flex flex-wrap gap-1.5">
                {priceBands.map((band) => (
                  <FilterChip
                    key={band[0]}
                    label={`${formatManwon(band[0])} ~ ${formatManwon(band[1])}`}
                    active={sameBand(band)}
                    onClick={() =>
                      onChange({ ...filter, priceBand: sameBand(band) ? null : band })
                    }
                  />
                ))}
              </div>
            </FilterSection>
          ) : null}

          {structureOptions.length > 0 ? (
            <FilterSection
              id="cluster"
              label="클러스터"
              selectedCount={filter.structureTypes.length}
              open={openFilterSection === "cluster"}
              onToggle={() =>
                setOpenFilterSection((current) =>
                  current === "cluster" ? null : "cluster",
                )
              }
            >
              <div className="flex flex-wrap gap-1.5">
                {structureOptions.map((option) => (
                  <FilterChip
                    key={option.type}
                    label={compactClusterDesc(option.desc)}
                    active={filter.structureTypes.includes(option.type)}
                    onClick={() => toggleStructure(option.type)}
                  />
                ))}
              </div>
            </FilterSection>
          ) : null}

          {tags.length > 0 ? (
            <FilterSection
              id="tag"
              label="지역 태그 정렬"
              selectedCount={filter.tags.length}
              open={openFilterSection === "tag"}
              onToggle={() =>
                setOpenFilterSection((current) => (current === "tag" ? null : "tag"))
              }
            >
              <div className="flex flex-wrap gap-1.5">
                {tags.map((tag) => (
                  <FilterChip
                    key={tag}
                    label={regionTagLabel(tag)}
                    active={filter.tags.includes(tag)}
                    onClick={() => toggleTag(tag)}
                  />
                ))}
              </div>
              <p className="text-xs text-muted-foreground">
                하나를 선택하면 해당 특징이 두드러진 동을 많은 값부터 보여줘요.
              </p>
            </FilterSection>
          ) : null}
        </div>
      </details>

      <div className="flex items-center justify-between border-t border-border pt-3">
        <p className="text-sm text-muted-foreground">
          검색 결과 <strong className="font-bold text-foreground">{resultCount}개 동</strong>
        </p>
        {refinementActive ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange({ ...EMPTY_FILTER, gu: filter.gu })}
          >
            필터 지우기
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function FilterSection({
  id,
  label,
  selectedCount,
  open,
  onToggle,
  children,
}: {
  id: FilterSectionId;
  label: string;
  selectedCount: number;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  const panelId = `condition-filter-${id}`;

  return (
    <section className="overflow-hidden rounded-md bg-card">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
        className="flex min-h-10 w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm font-medium text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span>{label}</span>
        <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
          {selectedCount > 0 ? `${selectedCount}개 선택` : "전체"}
          <ChevronDown
            aria-hidden="true"
            className={cn("size-4 transition-transform", open && "rotate-180")}
          />
        </span>
      </button>
      {open ? (
        <div id={panelId} className="border-t border-border px-3 py-3">
          <fieldset className="space-y-2">
            <legend className="sr-only">{label}</legend>
            {children}
          </fieldset>
        </div>
      ) : null}
    </section>
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
        "rounded-md border px-3 py-1.5 text-xs font-semibold transition-[background-color,border-color,color] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        active
          ? "border-primary bg-primary-soft text-primary"
          : "border-border bg-card text-muted-foreground hover:bg-muted",
      )}
    >
      {label}
    </button>
  );
}
