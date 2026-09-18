"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { FOOTNOTES } from "@/lib/format";
import {
  boundaryId,
  boundsOfFeatures,
  polygonsOf,
  visibleBoundaries,
  type BoundaryData,
  type BoundaryFeature,
  type DongBoundaryFeature,
  type FeatureCollection,
  type GuBoundaryFeature,
} from "@/lib/boundary";
import { boundsOf, projectToBounds, type Bounds } from "@/lib/map";
import { cn } from "@/lib/utils";

export type MapItem = {
  id: string;
  title: string;
  subtitle?: string;
  lat: number;
  lng: number;
  /** 구조 유형 0~3. 없으면 회색으로 둔다 */
  structureType: number | null;
  /** 표본 주의 flag가 하나라도 있으면 흐리게 그린다 */
  flagged: boolean;
};

type MapPanelProps = {
  items: MapItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  kakaoJsKey?: string;
  itemKind?: "gu" | "dong";
  activeGuName?: string | null;
};

type Mode = "loading" | "kakao" | "fallback";

const SDK_TIMEOUT_MS = 8000;
const SEOUL_CENTER = { lat: 37.5665, lng: 126.978 };
/** 카카오 지도는 숫자가 작을수록 확대된다. 동과 주변을 함께 볼 수 있는 수준이다. */
const SELECTED_DONG_LEVEL = 5;

export function MapPanel({
  items,
  selectedId,
  onSelect,
  kakaoJsKey,
  itemKind = "dong",
  activeGuName,
}: MapPanelProps) {
  const [mode, setMode] = useState<Mode>(kakaoJsKey ? "loading" : "fallback");
  const [boundaryData, setBoundaryData] = useState<BoundaryData | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  const overlaysRef = useRef(new Map<string, KakaoOverlay>());
  const polygonsRef = useRef<KakaoPolygon[]>([]);
  // 마커 DOM은 매번 다시 만들지 않으므로 최신 콜백을 ref로 들고 있는다
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const itemBounds = useMemo(() => boundsOf(items), [items]);
  const itemIds = useMemo(() => items.map((item) => item.id), [items]);
  const boundaryFeatures = useMemo(
    () => boundaryData ? visibleBoundaries(boundaryData, itemKind, itemIds, activeGuName) : [],
    [activeGuName, boundaryData, itemIds, itemKind],
  );
  const boundaryBounds = useMemo(() => boundsOfFeatures(boundaryFeatures), [boundaryFeatures]);
  const mapBounds = boundaryBounds ?? itemBounds;
  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  );
  const selectedBoundary = useMemo(
    () => boundaryFeatures.find((feature) => boundaryId(feature) === selectedId) ?? null,
    [boundaryFeatures, selectedId],
  );
  const selectedBoundaryBounds = useMemo(
    () => selectedBoundary ? boundsOfFeatures([selectedBoundary]) : null,
    [selectedBoundary],
  );
  const previewBounds = useMemo(
    () => selectedBoundaryBounds ?? (selectedItem ? boundsOf([selectedItem]) : mapBounds),
    [mapBounds, selectedBoundaryBounds, selectedItem],
  );
  const previewItems = useMemo(
    () => (selectedItem ? [selectedItem] : items),
    [items, selectedItem],
  );

  useEffect(() => {
    let cancelled = false;
    loadBoundaryData()
      .then((data) => {
        if (!cancelled) setBoundaryData(data);
      })
      .catch(() => {
        // 경계가 실패해도 기존 라벨 지도는 계속 쓸 수 있다.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!kakaoJsKey) return;
    let cancelled = false;

    loadKakaoSdk(kakaoJsKey)
      .then((kakao) => {
        if (cancelled || !containerRef.current) return;
        mapRef.current = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(SEOUL_CENTER.lat, SEOUL_CENTER.lng),
          level: 8,
        });
        setMode("kakao");
      })
      .catch(() => {
        if (!cancelled) setMode("fallback");
      });

    return () => {
      cancelled = true;
    };
  }, [kakaoJsKey]);

  // 자치구·법정동 면을 라벨보다 먼저 그린다. 선택 가능한 영역은 면을 눌러도 같은 동작을 한다.
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map) return;

    polygonsRef.current.forEach((polygon) => polygon.setMap(null));
    polygonsRef.current = [];
    const selectableIds = new Set(itemIds);

    boundaryFeatures.forEach((feature) => {
      const id = boundaryId(feature);
      const selected = id === selectedId;
      polygonsOf(feature.geometry).forEach((rings) => {
        const polygon = new kakao.maps.Polygon({
          path: rings.map((ring) => ring.map(([lng, lat]) => new kakao.maps.LatLng(lat, lng))),
          strokeWeight: selected ? 3 : itemKind === "gu" ? 2 : 1,
          strokeColor: selected ? "#4136e8" : itemKind === "gu" ? "#525866" : "#70798b",
          strokeOpacity: selected ? 0.95 : itemKind === "gu" ? 0.72 : 0.48,
          strokeStyle: "solid",
          fillColor: selected || itemKind === "gu" ? "#4136e8" : "#ffffff",
          fillOpacity: selected ? 0.16 : itemKind === "gu" ? 0.035 : 0.01,
        });
        if (selectableIds.has(id)) {
          kakao.maps.event.addListener(polygon, "click", () => onSelectRef.current(id));
        }
        polygon.setMap(map);
        polygonsRef.current.push(polygon);
      });
    });

    return () => {
      polygonsRef.current.forEach((polygon) => polygon.setMap(null));
      polygonsRef.current = [];
    };
  }, [boundaryFeatures, itemIds, itemKind, mode, selectedId]);

  // ponytail: 마커를 그릴 때마다 다시 만든다. 동은 최대 346개라 이 정도면 충분하고,
  // 더 늘어나면 MarkerClusterer와 bounds 기준 렌더링으로 올린다.
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map) return;

    overlaysRef.current.forEach((overlay) => overlay.setMap(null));
    overlaysRef.current.clear();

    items.forEach((item) => {
      const marker = document.createElement("button");
      marker.type = "button";
      marker.title = item.title;
      marker.setAttribute("aria-label", `${item.title} 선택`);
      marker.textContent = item.title;
      marker.className = markerClassName(item, item.id === selectedId, itemKind);
      marker.addEventListener("click", () => onSelectRef.current(item.id));

      const overlay = new kakao.maps.CustomOverlay({
        position: new kakao.maps.LatLng(item.lat, item.lng),
        content: marker,
        zIndex: item.id === selectedId ? 10 : 1,
      });
      overlay.setMap(map);
      overlaysRef.current.set(item.id, overlay);
    });
  }, [itemKind, items, mode, selectedId]);

  // 선택한 동이 화면 밖이면 지도를 옮긴다
  // 자치구를 고르는 등 조건이 바뀌어 보이는 동이 달라지면 그 범위로 지도를 맞춘다
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || items.length === 0) return;
    map.setBounds(
      new kakao.maps.LatLngBounds(
        new kakao.maps.LatLng(mapBounds.minLat, mapBounds.minLng),
        new kakao.maps.LatLng(mapBounds.maxLat, mapBounds.maxLng),
      ),
    );
  }, [items.length, mapBounds, mode]);

  // 동을 고르면 실제 경계가 모두 보이는 범위로 맞춘다. 경계가 없을 때만 대표 좌표를 쓴다.
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || itemKind !== "dong") return;
    if (selectedBoundaryBounds) {
      map.setBounds(
        new kakao.maps.LatLngBounds(
          new kakao.maps.LatLng(selectedBoundaryBounds.minLat, selectedBoundaryBounds.minLng),
          new kakao.maps.LatLng(selectedBoundaryBounds.maxLat, selectedBoundaryBounds.maxLng),
        ),
      );
      return;
    }
    if (!selectedItem) return;
    const position = new kakao.maps.LatLng(selectedItem.lat, selectedItem.lng);
    map.setLevel(Math.min(map.getLevel(), SELECTED_DONG_LEVEL), {
      anchor: position,
      animate: true,
    });
    map.panTo(position);
  }, [itemKind, mode, selectedBoundaryBounds, selectedItem]);

  return (
    // 좌측 동 목록 열과 같은 높이에서 --map-peek만큼 줄인다.
    // 지도로 화면이 꽉 차 보이지 않게 하고, 아래에 상세가 이어진다는 것도 함께 보여 준다
    <div className="overflow-hidden rounded-lg border border-border bg-card shadow-panel lg:flex lg:h-[calc(var(--app-column-h)-var(--map-peek))] lg:flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">지도</p>
        <p className="text-xs text-muted-foreground">
          {mode === "kakao"
            ? `${items.length}개 ${itemKind === "gu" ? "자치구" : "법정동"}`
            : mode === "loading"
              ? "지도를 불러오고 있어요"
              : "좌표 미리보기"}
        </p>
      </div>

      {mode === "kakao" || mode === "loading" ? (
        <div ref={containerRef} className="h-[320px] w-full bg-muted lg:h-auto lg:min-h-0 lg:flex-1" />
      ) : (
        <FallbackPreview
          items={previewItems}
          bounds={previewBounds}
          selectedId={selectedId}
          onSelect={onSelect}
          itemKind={itemKind}
          boundaries={boundaryFeatures}
        />
      )}

      {mode === "fallback" ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          지도를 불러오지 못해서 좌표 위치만 보여주고 있어요. 동 선택은 그대로 할 수 있어요.
        </p>
      ) : null}

      {items.length === 0 ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          보여줄 좌표가 없어요. 왼쪽 목록에서 지역을 선택해주세요.
        </p>
      ) : itemKind === "gu" ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          자치구를 선택하면 해당 지역으로 확대되고 법정동이 나타나요.
        </p>
      ) : (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          {FOOTNOTES.map}
        </p>
      )}
    </div>
  );
}

function FallbackPreview({
  items,
  bounds,
  selectedId,
  onSelect,
  itemKind = "dong",
  boundaries,
}: Omit<MapPanelProps, "kakaoJsKey"> & { bounds: Bounds; boundaries: BoundaryFeature[] }) {
  const selectableIds = new Set(items.map((item) => item.id));
  return (
    <div className="relative h-[320px] w-full bg-muted lg:h-auto lg:min-h-0 lg:flex-1">
      <svg
        aria-hidden="true"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
      >
        {boundaries.map((feature) => {
          const id = boundaryId(feature);
          const selected = id === selectedId;
          return (
            <path
              key={id}
              d={boundaryPath(feature, bounds)}
              fill={selected || itemKind === "gu" ? "#4136e8" : "#ffffff"}
              fillOpacity={selected ? 0.16 : itemKind === "gu" ? 0.035 : 0.01}
              fillRule="evenodd"
              stroke={selected ? "#4136e8" : itemKind === "gu" ? "#525866" : "#70798b"}
              strokeOpacity={selected ? 0.95 : itemKind === "gu" ? 0.72 : 0.48}
              strokeWidth={selected ? 0.8 : itemKind === "gu" ? 0.5 : 0.28}
              vectorEffect="non-scaling-stroke"
              onClick={selectableIds.has(id) ? () => onSelect(id) : undefined}
              className={selectableIds.has(id) ? "cursor-pointer" : undefined}
            />
          );
        })}
      </svg>
      {items.map((item) => {
        const { x, y } = projectToBounds(item, bounds);
        return (
          <button
            key={item.id}
            type="button"
            title={item.title}
            aria-label={`${item.title} 선택`}
            onClick={() => onSelect(item.id)}
            style={{ left: `${x}%`, top: `${y}%` }}
            className={cn(
              "absolute -translate-x-1/2 -translate-y-1/2",
              markerClassName(item, item.id === selectedId, itemKind),
            )}
          >
            {item.title}
          </button>
        );
      })}
    </div>
  );
}

function boundaryPath(feature: BoundaryFeature, bounds: Bounds): string {
  return polygonsOf(feature.geometry)
    .flatMap((polygon) => polygon.map((ring) => {
      const points = ring.map(([lng, lat]) => projectToBounds({ lat, lng }, bounds));
      return points.map(({ x, y }, index) => `${index === 0 ? "M" : "L"}${x} ${y}`).join(" ") + " Z";
    }))
    .join(" ");
}

/**
 * 구조 유형별 색. Tailwind가 클래스 이름을 훑어야 하므로 문자열을 그대로 적는다.
 * 순서에 뜻이 없는 구분용이라 진하기 단계로 두지 않는다(globals.css의 --structure-*).
 */
const STRUCTURE_BG = ["bg-structure-0", "bg-structure-1", "bg-structure-2", "bg-structure-3"];

/** 색은 구조 유형, 흐린 정도는 표본 주의 여부다. 변화율로는 색칠하지 않는다. */
function markerClassName(item: MapItem, selected: boolean, itemKind: "gu" | "dong") {
  if (itemKind === "gu") {
    return cn(
      "rounded-md bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground shadow-float transition-transform duration-150 hover:scale-105",
      selected ? "scale-110 ring-2 ring-ring" : "",
    );
  }

  const background =
    item.structureType === null
      ? "bg-neutral-strong"
      : (STRUCTURE_BG[item.structureType] ?? "bg-neutral-strong");

  return cn(
    "rounded-sm px-1.5 py-0.5 text-[11px] font-medium text-primary-foreground shadow-float transition-transform duration-150",
    background,
    item.flagged ? "opacity-60" : "",
    selected ? "scale-110 ring-2 ring-ring" : "",
  );
}

/* ---------------------------------------------------------------- */
/* Kakao SDK 로딩 (클라이언트 전용)                                  */
/* ---------------------------------------------------------------- */

type KakaoLatLng = object;
type KakaoLatLngBounds = object;
type KakaoMap = {
  getLevel: () => number;
  panTo: (latlng: KakaoLatLng) => void;
  setLevel: (
    level: number,
    options?: { anchor?: KakaoLatLng; animate?: boolean | { duration: number } },
  ) => void;
  setBounds: (bounds: KakaoLatLngBounds) => void;
};
type KakaoOverlay = { setMap: (map: KakaoMap | null) => void };
type KakaoPolygon = { setMap: (map: KakaoMap | null) => void };
type Kakao = {
  maps: {
    load: (callback: () => void) => void;
    Map: new (container: HTMLElement, options: { center: KakaoLatLng; level: number }) => KakaoMap;
    LatLng: new (lat: number, lng: number) => KakaoLatLng;
    LatLngBounds: new (sw: KakaoLatLng, ne: KakaoLatLng) => KakaoLatLngBounds;
    CustomOverlay: new (options: {
      position: KakaoLatLng;
      content: HTMLElement;
      zIndex: number;
    }) => KakaoOverlay;
    Polygon: new (options: {
      path: KakaoLatLng[][];
      strokeWeight: number;
      strokeColor: string;
      strokeOpacity: number;
      strokeStyle: "solid";
      fillColor: string;
      fillOpacity: number;
    }) => KakaoPolygon;
    event: {
      addListener: (target: KakaoPolygon, event: "click", handler: () => void) => void;
    };
  };
};

function getKakao(): Kakao | null {
  return (window as unknown as { kakao?: Kakao }).kakao ?? null;
}

let sdkPromise: Promise<Kakao> | null = null;
let boundaryPromise: Promise<BoundaryData> | null = null;

function loadBoundaryData(): Promise<BoundaryData> {
  if (boundaryPromise) return boundaryPromise;

  boundaryPromise = Promise.all([
    fetch("/data/dong-boundary.geojson").then(readGeoJson<DongBoundaryFeature>),
    fetch("/data/gu-boundary.geojson").then(readGeoJson<GuBoundaryFeature>),
  ])
    .then(([dongs, gus]) => ({ dongs: dongs.features, gus: gus.features }))
    .catch((error) => {
      boundaryPromise = null;
      throw error;
    });
  return boundaryPromise;
}

function readGeoJson<T extends BoundaryFeature>(response: Response): Promise<FeatureCollection<T>> {
  if (!response.ok) throw new Error(`경계 조회 실패: ${response.status}`);
  return response.json() as Promise<FeatureCollection<T>>;
}

function loadKakaoSdk(key: string): Promise<Kakao> {
  if (sdkPromise) return sdkPromise;

  sdkPromise = new Promise<Kakao>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Kakao SDK 로딩 시간 초과")), SDK_TIMEOUT_MS);
    const done = (kakao: Kakao) => {
      clearTimeout(timer);
      kakao.maps.load(() => resolve(kakao));
    };

    const existing = getKakao();
    if (existing) {
      done(existing);
      return;
    }

    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(key)}&autoload=false`;
    script.async = true;
    script.onload = () => {
      const kakao = getKakao();
      if (kakao) done(kakao);
      else {
        clearTimeout(timer);
        reject(new Error("Kakao SDK를 찾지 못했습니다."));
      }
    };
    script.onerror = () => {
      clearTimeout(timer);
      reject(new Error("Kakao SDK 로딩 실패"));
    };
    document.head.appendChild(script);
  }).catch((error) => {
    sdkPromise = null;
    throw error;
  });

  return sdkPromise;
}
