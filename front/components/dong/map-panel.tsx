"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  boundaryPaths,
  boundsOf,
  projectToBounds,
  type Bounds,
  type BoundaryCollection,
} from "@/lib/map";
import { cn } from "@/lib/utils";

export type MapItem = {
  id: string;
  title: string;
  subtitle?: string;
  lat: number;
  lng: number;
  status: "default" | "muted";
};

type MapPanelProps = {
  items: MapItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  kakaoJsKey?: string;
};

type Mode = "loading" | "kakao" | "fallback";

const SDK_TIMEOUT_MS = 8000;
const SEOUL_CENTER = { lat: 37.5665, lng: 126.978 };
/** 53이 만드는 법정동 경계. 없으면 지금까지처럼 마커만 그린다 */
const BOUNDARY_URL = "/data/dong-boundary.geojson";

export function MapPanel({ items, selectedId, onSelect, kakaoJsKey }: MapPanelProps) {
  const [mode, setMode] = useState<Mode>(kakaoJsKey ? "loading" : "fallback");
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  const overlaysRef = useRef(new Map<string, KakaoOverlay>());
  // 마커 DOM은 매번 다시 만들지 않으므로 최신 콜백을 ref로 들고 있는다
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  // 동을 고를 때는 목록이 바뀐 것이 아니므로 범위를 다시 잡지 않는다
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const bounds = useMemo(() => boundsOf(items), [items]);
  const [boundary, setBoundary] = useState<BoundaryCollection | null>(null);
  const polygonsRef = useRef(new Map<string, KakaoPolygon[]>());

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

  // 경계 파일은 한 번만 받는다. 아직 만들지 않았거나 받지 못하면 마커만 그린다
  useEffect(() => {
    if (mode !== "kakao") return;
    let cancelled = false;

    fetch(BOUNDARY_URL)
      .then((response) => (response.ok ? response.json() : null))
      .then((data: BoundaryCollection | null) => {
        if (!cancelled && data?.features?.length) setBoundary(data);
      })
      .catch(() => {
        /* 경계는 있으면 좋은 것이라 실패해도 그냥 넘어간다 */
      });

    return () => {
      cancelled = true;
    };
  }, [mode]);

  // 경계는 한 번 만들어 두고 보이고 숨기는 것만 바꾼다.
  // 동을 고를 때마다 도형을 다시 만들면 340개를 매번 새로 그리게 된다
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || !boundary) return;

    const statusById = new Map(items.map((item) => [item.id, item.status]));
    const cache = polygonsRef.current;

    const style = polygonStyle();
    boundary.features.forEach((feature) => {
      const dong = feature.properties.dong;
      const status = statusById.get(dong);
      let polygons = cache.get(dong);

      if (!status) {
        polygons?.forEach((polygon) => polygon.setMap(null));
        return;
      }

      if (!polygons) {
        polygons = toKakaoPaths(kakao, feature.geometry).map((path) => {
          const polygon = new kakao.maps.Polygon({ path });
          kakao.maps.event.addListener(polygon, "click", () => onSelectRef.current(dong));
          return polygon;
        });
        cache.set(dong, polygons);
      }

      polygons.forEach((polygon) => {
        polygon.setOptions(style[dong === selectedId ? "selected" : status]);
        polygon.setMap(map);
      });
    });
  }, [boundary, items, mode, selectedId]);

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
      marker.className = markerClassName(item.status, item.id === selectedId);
      marker.addEventListener("click", () => onSelectRef.current(item.id));

      const overlay = new kakao.maps.CustomOverlay({
        position: new kakao.maps.LatLng(item.lat, item.lng),
        content: marker,
        zIndex: item.id === selectedId ? 10 : 1,
      });
      overlay.setMap(map);
      overlaysRef.current.set(item.id, overlay);
    });
  }, [items, mode, selectedId]);

  // 선택한 동이 화면 밖이면 지도를 옮긴다
  // 자치구를 고르는 등 조건이 바뀌어 보이는 동이 달라지면 그 범위로 지도를 맞춘다
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || items.length === 0) return;
    map.setBounds(
      new kakao.maps.LatLngBounds(
        new kakao.maps.LatLng(bounds.minLat, bounds.minLng),
        new kakao.maps.LatLng(bounds.maxLat, bounds.maxLng),
      ),
    );
  }, [bounds, items.length, mode]);

  // 동을 고르면 확대 수준은 그대로 두고 그 동이 가운데에 오게만 옮긴다
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || !selectedId) return;
    const selected = itemsRef.current.find((item) => item.id === selectedId);
    if (!selected) return;
    map.panTo(new kakao.maps.LatLng(selected.lat, selected.lng));
  }, [selectedId, mode]);

  return (
    // 좌측 동 목록 열과 같은 높이에서 --map-peek만큼 줄인다.
    // 지도로 화면이 꽉 차 보이지 않게 하고, 아래에 상세가 이어진다는 것도 함께 보여 준다
    <div className="overflow-hidden rounded-lg border border-border bg-card shadow-panel lg:flex lg:h-[calc(var(--app-column-h)-var(--map-peek))] lg:flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">지도</p>
        <p className="text-xs text-muted-foreground">
          {mode === "kakao"
            ? `${items.length}개 동`
            : mode === "loading"
              ? "지도를 불러오고 있어요"
              : "좌표 미리보기"}
        </p>
      </div>

      {mode === "kakao" || mode === "loading" ? (
        <div ref={containerRef} className="h-[320px] w-full bg-muted lg:h-auto lg:min-h-0 lg:flex-1" />
      ) : (
        <FallbackPreview
          items={items}
          bounds={bounds}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      )}

      {mode === "fallback" ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          지도를 불러오지 못해서 좌표 위치만 보여주고 있어요. 동 선택은 그대로 할 수 있어요.
        </p>
      ) : null}

      {items.length === 0 ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          보여줄 좌표가 없어요. 목록에서 동을 선택해주세요.
        </p>
      ) : null}

      {/* 결정 40: 경계를 화면에 그리면 출처를 함께 밝힌다 */}
      {boundary?.source ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
          {boundary.source}
        </p>
      ) : null}
    </div>
  );
}

function FallbackPreview({
  items,
  bounds,
  selectedId,
  onSelect,
}: Omit<MapPanelProps, "kakaoJsKey"> & { bounds: Bounds }) {
  return (
    <div className="relative h-[320px] w-full bg-muted lg:h-auto lg:min-h-0 lg:flex-1">
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
              markerClassName(item.status, item.id === selectedId),
            )}
          >
            {item.title}
          </button>
        );
      })}
    </div>
  );
}

function markerClassName(status: MapItem["status"], selected: boolean) {
  return cn(
    "rounded-sm px-1.5 py-0.5 text-[11px] font-medium text-primary-foreground shadow-float transition-transform duration-150",
    status === "muted" ? "bg-neutral-strong" : "bg-primary",
    selected ? "scale-110 bg-primary-hover ring-2 ring-ring" : "",
  );
}

/* ---------------------------------------------------------------- */
/* 법정동 경계 (53.export_front_boundary.py 산출물)                  */
/* ---------------------------------------------------------------- */

/** 좌표 경로를 Kakao Polygon이 쓰는 LatLng으로 바꾼다 */
function toKakaoPaths(kakao: Kakao, geometry: BoundaryCollection["features"][number]["geometry"]) {
  return boundaryPaths(geometry).map((rings) =>
    rings.map((ring) => ring.map((point) => new kakao.maps.LatLng(point.lat, point.lng))),
  );
}

/**
 * 경계 색은 마커와 같은 값을 쓴다. globals.css의 토큰에서 읽어 와서
 * 색을 바꿀 때 두 군데를 고치지 않게 한다.
 * 경계는 배경이라 채우기를 옅게 두고, 고른 동만 진하게 만든다.
 */
function polygonStyle() {
  const token = (name: string) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const primary = token("--primary") || "#4136e8";
  const muted = token("--neutral-strong") || "#858b98";
  const base = { strokeWeight: 1, strokeOpacity: 0.7, fillOpacity: 0.07 };

  return {
    default: { ...base, strokeColor: primary, fillColor: primary },
    muted: { ...base, strokeColor: muted, fillColor: muted },
    selected: {
      ...base,
      strokeColor: primary,
      fillColor: primary,
      strokeWeight: 3,
      strokeOpacity: 1,
      fillOpacity: 0.18,
    },
  };
}

/* ---------------------------------------------------------------- */
/* Kakao SDK 로딩 (클라이언트 전용)                                  */
/* ---------------------------------------------------------------- */

type KakaoLatLng = object;
type KakaoLatLngBounds = object;
type KakaoMap = {
  panTo: (latlng: KakaoLatLng) => void;
  setBounds: (bounds: KakaoLatLngBounds) => void;
};
type KakaoOverlay = { setMap: (map: KakaoMap | null) => void };
type KakaoPolygonStyle = {
  strokeWeight: number;
  strokeColor: string;
  strokeOpacity: number;
  fillColor: string;
  fillOpacity: number;
};
type KakaoPolygon = {
  setMap: (map: KakaoMap | null) => void;
  setOptions: (options: KakaoPolygonStyle) => void;
};
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
    Polygon: new (options: { path: KakaoLatLng[][] }) => KakaoPolygon;
    event: {
      addListener: (target: KakaoPolygon, type: string, handler: () => void) => void;
    };
  };
};

function getKakao(): Kakao | null {
  return (window as unknown as { kakao?: Kakao }).kakao ?? null;
}

let sdkPromise: Promise<Kakao> | null = null;

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
