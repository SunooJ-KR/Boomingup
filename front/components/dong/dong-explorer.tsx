"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { DongDetailPanel } from "@/components/dong/dong-detail-panel";
import { DongList } from "@/components/dong/dong-list";
import { EmptyState } from "@/components/dong/empty-state";
import { SearchPanel } from "@/components/dong/search-panel";
import { Button } from "@/components/ui/button";
import { EMPTY_FILTER, filterDongs, isFilterActive, type DongFilter } from "@/lib/filter";
import type { DongDetail, DongSummary, Meta } from "@/lib/types";

type DongExplorerProps = {
  dongs: DongSummary[];
  details: Record<string, DongDetail>;
  meta: Meta;
  guNames: string[];
  tags: string[];
};

export function DongExplorer({ dongs, details, meta, guNames, tags }: DongExplorerProps) {
  const [filter, setFilter] = useState<DongFilter>(EMPTY_FILTER);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const detailRef = useRef<HTMLElement>(null);

  const visibleDongs = useMemo(() => filterDongs(dongs, filter), [dongs, filter]);
  const selectedDong = dongs.find((dong) => dong.dong_id === selectedId) ?? null;

  // 목록과 상세가 세로로 쌓이는 폭에서는 선택 시 상세로 스크롤한다
  useEffect(() => {
    if (!selectedId) return;
    if (window.matchMedia("(min-width: 1024px)").matches) return;
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [selectedId]);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      <section aria-label="검색과 동 목록" className="space-y-4">
        <SearchPanel
          filter={filter}
          onChange={setFilter}
          guNames={guNames}
          tags={tags}
          resultCount={visibleDongs.length}
        />
        {visibleDongs.length === 0 ? (
          <EmptyState
            title="검색 조건에 맞는 동이 없습니다."
            description="검색어를 줄이거나 필터를 해제해 보세요."
            action={
              isFilterActive(filter) ? (
                <Button variant="outline" size="sm" onClick={() => setFilter(EMPTY_FILTER)}>
                  필터 초기화
                </Button>
              ) : undefined
            }
          />
        ) : (
          <DongList dongs={visibleDongs} selectedId={selectedId} onSelect={setSelectedId} />
        )}
      </section>

      <section
        ref={detailRef}
        aria-label="선택한 동 상세"
        className="lg:sticky lg:top-20 lg:self-start"
      >
        <DongDetailPanel
          dong={selectedDong}
          detail={selectedId ? (details[selectedId] ?? null) : null}
          meta={meta}
        />
      </section>
    </div>
  );
}
