"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DongDetailPanel, type DetailState } from "@/components/dong/dong-detail-panel";
import { DongList } from "@/components/dong/dong-list";
import { MapPanel, type MapItem } from "@/components/dong/map-panel";
import { EmptyState } from "@/components/dong/empty-state";
import { SearchPanel } from "@/components/dong/search-panel";
import { Button } from "@/components/ui/button";
import { EMPTY_FILTER, filterDongs, isFilterActive, type DongFilter } from "@/lib/filter";
import type { DongDetail, DongSummary, Meta } from "@/lib/types";

type DongExplorerProps = {
  dongs: DongSummary[];
  meta: Meta;
  guNames: string[];
  tags: string[];
  /** 동 대표 좌표. 법정동 경계 GeoJSON이 없어 단지 좌표 평균을 쓴다 */
  centers: Record<string, { lat: number; lng: number }>;
  kakaoJsKey?: string;
};

export function DongExplorer({
  dongs,
  meta,
  guNames,
  tags,
  centers,
  kakaoJsKey,
}: DongExplorerProps) {
  const [filter, setFilter] = useState<DongFilter>(EMPTY_FILTER);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DongDetail | null>(null);
  const [detailState, setDetailState] = useState<DetailState>("idle");
  const [reloadToken, setReloadToken] = useState(0);
  const detailRef = useRef<HTMLElement>(null);
  const cache = useRef(new Map<string, DongDetail>());

  const visibleDongs = useMemo(() => filterDongs(dongs, filter), [dongs, filter]);
  const selectedDong = dongs.find((dong) => dong.dong_id === selectedId) ?? null;

  const mapItems = useMemo<MapItem[]>(
    () =>
      visibleDongs.flatMap((dong) => {
        const center = centers[dong.dong_id];
        if (!center) return [];
        return [
          {
            id: dong.dong_id,
            title: dong.umd_name,
            subtitle: dong.gu_name,
            lat: center.lat,
            lng: center.lng,
            status: dong.status === "PREDICTED" ? ("default" as const) : ("muted" as const),
          },
        ];
      }),
    [visibleDongs, centers],
  );

  // 상세는 API에서 선택 시점에 가져온다. 동이 300개가 넘어 첫 화면에 다 실어 보내지 않는다.
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setDetailState("idle");
      return;
    }

    const cached = cache.current.get(selectedId);
    if (cached) {
      setDetail(cached);
      setDetailState("ready");
      return;
    }

    let cancelled = false;
    setDetailState("loading");
    setDetail(null);

    const url = `/api/dong/${encodeURIComponent(selectedId)}?asOf=${encodeURIComponent(meta.as_of_quarter)}`;
    fetch(url)
      .then(async (response) => {
        if (!response.ok) throw new Error(`상세 조회 실패: ${response.status}`);
        return (await response.json()) as { detail: DongDetail };
      })
      .then(({ detail: loaded }) => {
        if (cancelled) return;
        cache.current.set(selectedId, loaded);
        setDetail(loaded);
        setDetailState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setDetail(null);
        setDetailState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId, meta.as_of_quarter, reloadToken]);

  // 목록과 상세가 세로로 쌓이는 폭에서는 선택 시 상세로 스크롤한다
  useEffect(() => {
    if (!selectedId) return;
    if (window.matchMedia("(min-width: 1024px)").matches) return;
    detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [selectedId]);

  const retry = useCallback(() => {
    if (selectedId) cache.current.delete(selectedId);
    setReloadToken((token) => token + 1);
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

      <div className="space-y-4">
        {/* 모바일에서는 목록과 상세 읽기가 먼저라 지도를 접어 둔다 */}
        <details open>
          <summary className="cursor-pointer list-none text-sm font-medium text-muted-foreground lg:hidden">
            지도 보기
          </summary>
          <div className="mt-2 lg:mt-0">
            <MapPanel
              items={mapItems}
              selectedId={selectedId}
              onSelect={setSelectedId}
              kakaoJsKey={kakaoJsKey}
            />
          </div>
        </details>

        <section
          ref={detailRef}
          aria-label="선택한 동 상세"
          aria-busy={detailState === "loading"}
        >
          <DongDetailPanel
            dong={selectedDong}
            detail={detail}
            meta={meta}
            state={detailState}
            onRetry={retry}
          />
        </section>
      </div>
    </div>
  );
}
