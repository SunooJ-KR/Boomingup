"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DongDetailPanel, type DetailState } from "@/components/dong/dong-detail-panel";
import { DongList } from "@/components/dong/dong-list";
import { MapPanel, type MapItem } from "@/components/dong/map-panel";
import { EmptyState } from "@/components/dong/empty-state";
import { Pagination } from "@/components/dong/pagination";
import { SearchPanel } from "@/components/dong/search-panel";
import { Button } from "@/components/ui/button";
import { EMPTY_FILTER, filterDongs, isFilterActive, type DongFilter } from "@/lib/filter";
import { clampPage, fitPageSize, pageCount } from "@/lib/paginate";
import type { DongDetail, DongSummary, Meta } from "@/lib/types";

/** 목록과 상세가 두 열로 갈리는 폭. Tailwind lg와 같은 값이다 */
const DESKTOP_QUERY = "(min-width: 1024px)";
/** 목록 칸 높이를 재기 전, 그리고 한 열로 쌓이는 좁은 화면에서 쓰는 한 페이지 개수 */
const DEFAULT_PAGE_SIZE = 10;
/** 목록 항목 사이 간격(space-y-2) */
const ITEM_GAP_PX = 8;

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
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const detailRef = useRef<HTMLElement>(null);
  const listBoxRef = useRef<HTMLDivElement>(null);
  const cache = useRef(new Map<string, DongDetail>());

  const visibleDongs = useMemo(() => filterDongs(dongs, filter), [dongs, filter]);
  const selectedDong = dongs.find((dong) => dong.dong_id === selectedId) ?? null;

  // 필터가 바뀌면 목록이 줄어드니 들고 있던 번호를 그대로 쓰지 않는다
  const totalPages = pageCount(visibleDongs.length, pageSize);
  const currentPage = clampPage(page, visibleDongs.length, pageSize);
  const pagedDongs = visibleDongs.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const changeFilter = useCallback((next: DongFilter) => {
    setFilter(next);
    setPage(1);
  }, []);

  const changePage = useCallback((next: number) => {
    setPage(next);
    listBoxRef.current?.scrollTo({ top: 0 });
  }, []);

  // 두 열로 갈리는 폭에서는 목록 칸에 들어가는 만큼만 한 페이지에 담는다.
  // 창 크기가 바뀌면 다시 잰다. 한 열로 쌓이는 폭에서는 페이지 전체가 흐르므로 기본값을 쓴다.
  // ponytail: 항목 높이를 평균으로 어림한다. 태그가 긴 항목이 모이면 목록 칸 안에서 조금 스크롤된다.
  useEffect(() => {
    const box = listBoxRef.current;
    if (!box) return;

    const measure = () => {
      if (!window.matchMedia(DESKTOP_QUERY).matches) {
        setPageSize(DEFAULT_PAGE_SIZE);
        return;
      }
      const items = [...box.querySelectorAll("li")];
      if (items.length === 0) return;
      const sum = items.reduce((total, li) => total + li.getBoundingClientRect().height, 0);
      setPageSize(fitPageSize(box.clientHeight, sum / items.length + ITEM_GAP_PX));
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  // 지도는 페이지와 상관없이 필터에 걸린 동을 전부 찍는다
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
      {/* 동이 300개가 넘어 목록을 그대로 펼치면 문서가 4만px를 넘고 오른쪽 열이 통째로 빈다.
          넓은 폭에서는 검색과 페이지 번호를 고정하고 목록 칸만 남는 높이를 채운다.
          오프셋 65px = 헤더 49px + main 위 여백 16px, 81px는 아래 여백 16px까지 뺀 값이다. */}
      <section
        aria-label="검색과 동 목록"
        className="space-y-4 lg:sticky lg:top-[65px] lg:flex lg:h-[calc(100dvh-81px)] lg:flex-col lg:self-start lg:space-y-0 lg:pr-1"
      >
        <div className="lg:shrink-0 lg:pb-4">
          <SearchPanel
            filter={filter}
            onChange={changeFilter}
            guNames={guNames}
            tags={tags}
            resultCount={visibleDongs.length}
          />
        </div>

        <div ref={listBoxRef} className="lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
          {visibleDongs.length === 0 ? (
            <EmptyState
              title="검색 조건에 맞는 동이 없습니다."
              description="검색어를 줄이거나 필터를 해제해 보세요."
              action={
                isFilterActive(filter) ? (
                  <Button variant="outline" size="sm" onClick={() => changeFilter(EMPTY_FILTER)}>
                    필터 초기화
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <DongList dongs={pagedDongs} selectedId={selectedId} onSelect={setSelectedId} />
          )}
        </div>

        <div className="mt-4 lg:mt-0 lg:shrink-0 lg:pt-4">
          <Pagination page={currentPage} totalPages={totalPages} onChange={changePage} />
        </div>
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
