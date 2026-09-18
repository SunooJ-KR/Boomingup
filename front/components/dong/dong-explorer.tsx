"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DongDetailPanel, type DetailState } from "@/components/dong/dong-detail-panel";
import { DongList } from "@/components/dong/dong-list";
import { MapPanel, type MapItem } from "@/components/dong/map-panel";
import { EmptyState } from "@/components/dong/empty-state";
import { Pagination } from "@/components/dong/pagination";
import { SearchPanel, type StructureOption } from "@/components/dong/search-panel";
import { Button } from "@/components/ui/button";
import {
  EMPTY_FILTER,
  filterDongs,
  priceBandsOf,
  type DongFilter,
} from "@/lib/filter";
import { guSummariesOf } from "@/lib/gu";
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

  const guSummaries = useMemo(() => guSummariesOf(dongs, centers), [dongs, centers]);
  const visibleDongs = useMemo(() => filterDongs(dongs, filter), [dongs, filter]);
  const priceBands = useMemo(() => priceBandsOf(dongs), [dongs]);

  // 구조 유형 칩에는 번호 대신 자동 설명을 붙인다. 같은 유형은 설명도 같다.
  const structureOptions = useMemo<StructureOption[]>(() => {
    const byType = new Map<number, string>();
    dongs.forEach((dong) => {
      if (dong.structure_type === null || dong.structure_desc === null) return;
      if (!byType.has(dong.structure_type)) byType.set(dong.structure_type, dong.structure_desc);
    });
    return [...byType.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([type, desc]) => ({ type, desc }));
  }, [dongs]);
  const selectedDong = dongs.find((dong) => dong.dong_id === selectedId) ?? null;

  // 필터가 바뀌면 목록이 줄어드니 들고 있던 번호를 그대로 쓰지 않는다
  const totalPages = pageCount(visibleDongs.length, pageSize);
  const currentPage = clampPage(page, visibleDongs.length, pageSize);
  const pagedDongs = visibleDongs.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const changeFilter = useCallback(
    (next: DongFilter) => {
      if (next.gu !== filter.gu) setSelectedId(null);
      setFilter(next);
      setPage(1);
    },
    [filter.gu],
  );

  const selectGu = useCallback((guName: string) => {
    setFilter({ ...EMPTY_FILTER, gu: guName });
    setSelectedId(null);
    setPage(1);
  }, []);

  const showAllGu = useCallback(() => {
    setFilter(EMPTY_FILTER);
    setSelectedId(null);
    setPage(1);
  }, []);

  // 목록에서 동을 골라도 탐색 맥락은 유지하고 상세만 연다.
  // 자치구 전환은 지도나 자치구 선택 상자에서 명시적으로 선택할 때만 일어난다.
  const selectDong = useCallback((dongId: string) => {
    setSelectedId(dongId);
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
  }, [filter.gu]);

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
            structureType: dong.structure_type,
            flagged: dong.sample_flags.length > 0,
          },
        ];
      }),
    [visibleDongs, centers],
  );

  const guMapItems = useMemo<MapItem[]>(
    () =>
      guSummaries.flatMap((gu) =>
        gu.center
          ? [
              {
                id: gu.name,
                title: gu.name,
                lat: gu.center.lat,
                lng: gu.center.lng,
                structureType: null,
                flagged: false,
              },
            ]
          : [],
      ),
    [guSummaries],
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

  // 넓은 폭에서도 지도가 화면을 가득 채워 상세는 화면 아래에 붙는다.
  // 어느 폭이든 동을 고르면 상세까지 부드럽게 내려간다. 좌측 목록은 sticky라 그대로 보인다.
  // 고른 직후 한 번, 내용이 도착해 높이가 늘어난 뒤 한 번 더 맞춘다.
  useEffect(() => {
    if (!selectedId) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    detailRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  }, [selectedId, detailState]);

  const retry = useCallback(() => {
    if (selectedId) cache.current.delete(selectedId);
    setReloadToken((token) => token + 1);
  }, [selectedId]);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      {/* 동이 300개가 넘어 목록을 그대로 펼치면 문서가 4만px를 넘고 오른쪽 열이 통째로 빈다.
          넓은 폭에서는 검색과 페이지 번호를 고정하고 목록 칸만 남는 높이를 채운다.
          높이와 위치는 globals.css의 --app-column-h, --app-header-h에서 나온다. */}
      <section
        aria-label="검색과 동 목록"
        className="space-y-4 lg:sticky lg:top-[calc(var(--app-header-h)+var(--app-gutter))] lg:flex lg:h-[var(--app-column-h)] lg:flex-col lg:self-start lg:space-y-0 lg:pr-1"
      >
        <div className="lg:shrink-0 lg:pb-4">
          <SearchPanel
            filter={filter}
            onChange={changeFilter}
            onBack={filter.gu === null ? undefined : showAllGu}
            guNames={guNames}
            tags={tags}
            priceBands={priceBands}
            structureOptions={structureOptions}
            resultCount={visibleDongs.length}
          />
        </div>

        <div ref={listBoxRef} className="lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
          {visibleDongs.length === 0 ? (
            <EmptyState
              title="검색 조건에 맞는 동이 없어요."
              description="검색어를 줄이거나 필터를 풀어보세요."
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => changeFilter({ ...EMPTY_FILTER, gu: filter.gu })}
                >
                  필터 지우기
                </Button>
              }
            />
          ) : (
            <DongList dongs={pagedDongs} selectedId={selectedId} onSelect={selectDong} />
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
              items={filter.gu === null ? guMapItems : mapItems}
              selectedId={filter.gu === null ? null : selectedId}
              onSelect={filter.gu === null ? selectGu : selectDong}
              kakaoJsKey={kakaoJsKey}
              itemKind={filter.gu === null ? "gu" : "dong"}
            />
          </div>
        </details>

        {/* 상세가 도착하면 아래에서 떠오르게 해서 새로 생겼다는 것을 알린다.
            key가 바뀌면 다음 동을 골랐을 때 효과가 다시 재생된다.
            효과를 줄이기로 한 사용자에게는 globals.css에서 사실상 꺼진다. */}
        {/* 스크롤은 이 section을 기준으로 잡는다. 여기에는 효과를 걸지 않는다.
            등장 효과는 DongDetailPanel이 자기 안에서 건다. 스크롤 기준이 되는 요소에
            transform이 걸려 있으면 그만큼 어긋난 위치에 멈추기 때문이다.
            머리말에 가리지 않게 하는 여백은 globals.css의 scroll-padding-top이 맡는다. */}
        {selectedId !== null ? (
          <section
            ref={detailRef}
            aria-label="선택한 동 상세"
            aria-busy={detailState === "loading"}
          >
            <DongDetailPanel
              key={selectedId ?? "idle"}
              dong={selectedDong}
              detail={detail}
              meta={meta}
              state={detailState}
              onRetry={retry}
              onSelect={selectDong}
            />
          </section>
        ) : null}
      </div>
    </div>
  );
}
