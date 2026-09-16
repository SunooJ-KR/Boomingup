"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  boundaryPaths,
  boundsOf,
  projectToBounds,
  type Bounds,
  type BoundaryCollection,
  type BoundaryGeometry,
  type GuBoundaryCollection,
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
  /** 고른 자치구. 고르면 지도가 그 자치구로 확대되고 동 이름이 나온다 */
  gu?: string | null;
  onSelectGu?: (gu: string | null) => void;
  kakaoJsKey?: string;
};

type Mode = "loading" | "kakao" | "fallback";

const SDK_TIMEOUT_MS = 8000;
const SEOUL_CENTER = { lat: 37.5665, lng: 126.978 };
const SEOUL_LEVEL = 8;
/**
 * 자치구를 보여 줄 확대 수준. Kakao는 숫자가 클수록 넓게 본다.
 * 서울 전체가 8, 자치구 하나가 6 안팎이라 7을 경계로 둔다.
 * ponytail: 조절값이다. 동 이름이 너무 일찍 나오면 키운다.
 */
const GU_VIEW_LEVEL = 7;
/** 53이 만드는 경계 파일. 없으면 지금까지처럼 마커만 그린다 */
const DONG_BOUNDARY_URL = "/data/dong-boundary.geojson";
const GU_BOUNDARY_URL = "/data/gu-boundary.geojson";

export function MapPanel({
  items,
  selectedId,
  onSelect,
  gu = null,
  onSelectGu,
  kakaoJsKey,
}: MapPanelProps) {
  const [mode, setMode] = useState<Mode>(kakaoJsKey ? "loading" : "fallback");
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  const overlaysRef = useRef(new Map<string, KakaoOverlay>());
  // 마커 DOM은 매번 다시 만들지 않으므로 최신 콜백을 ref로 들고 있는다
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onSelectGuRef = useRef(onSelectGu);
  onSelectGuRef.current = onSelectGu;
  // 동을 고를 때는 목록이 바뀐 것이 아니므로 범위를 다시 잡지 않는다
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const bounds = useMemo(() => boundsOf(items), [items]);

  const [dongBoundary, setDongBoundary] = useState<BoundaryCollection | null>(null);
  const [guBoundary, setGuBoundary] = useState<GuBoundaryCollection | null>(null);
  const dongPolygonsRef = useRef(new Map<string, KakaoPolygon[]>());
  const guPolygonsRef = useRef(new Map<string, KakaoPolygon[]>());
  const guLabelsRef = useRef(new Map<string, KakaoOverlay>());

  // 넓게 보고 있으면 자치구를, 확대하면 동을 보여 준다
  const [level, setLevel] = useState(SEOUL_LEVEL);
  const view: "gu" | "dong" = level >= GU_VIEW_LEVEL ? "gu" : "dong";
  const boundarySource = guBoundary?.source ?? dongBoundary?.source ?? null;

  useEffect(() => {
    if (!kakaoJsKey) return;
    let cancelled = false;

    loadKakaoSdk(kakaoJsKey)
      .then((kakao) => {
        if (cancelled || !containerRef.current) return;
        const map = new kakao.maps.Map(containerRef.current, {
          center: new kakao.maps.LatLng(SEOUL_CENTER.lat, SEOUL_CENTER.lng),
          level: SEOUL_LEVEL,
        });
        // 확대 수준이 바뀌면 자치구 뷰와 동 뷰를 갈아 끼운다
        kakao.maps.event.addListener(map, "zoom_changed", () => setLevel(map.getLevel()));
        mapRef.current = map;
        setLevel(map.getLevel());
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

    const read = async <T,>(url: string): Promise<T | null> => {
      try {
        const response = await fetch(url);
        return response.ok ? ((await response.json()) as T) : null;
      } catch {
        // 경계는 있으면 좋은 것이라 실패해도 그냥 넘어간다
        return null;
      }
    };

    Promise.all([
      read<BoundaryCollection>(DONG_BOUNDARY_URL),
      read<GuBoundaryCollection>(GU_BOUNDARY_URL),
    ]).then(([dong, gus]) => {
      if (cancelled) return;
      if (dong?.features?.length) setDongBoundary(dong);
      if (gus?.features?.length) setGuBoundary(gus);
    });

    return () => {
      cancelled = true;
    };
  }, [mode]);

  // 자치구 경계와 이름. 넓게 볼 때만 보여 주고, 누르면 그 자치구로 좁힌다
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || !guBoundary) return;

    const style = polygonStyle();
    guBoundary.features.forEach((feature) => {
      const { gu_name: guName, label } = feature.properties;
      let polygons = guPolygonsRef.current.get(guName);
      let overlay = guLabelsRef.current.get(guName);

      if (!polygons) {
        polygons = toKakaoPolygons(kakao, feature.geometry, () => onSelectGuRef.current?.(guName));
        guPolygonsRef.current.set(guName, polygons);
      }
      if (!overlay) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = guName;
        button.setAttribute("aria-label", `${guName} 지도에서 크게 보기`);
        button.className = guLabelClassName();
        button.addEventListener("click", () => onSelectGuRef.current?.(guName));
        overlay = new kakao.maps.CustomOverlay({
          position: new kakao.maps.LatLng(label[1], label[0]),
          content: button,
          zIndex: 5,
        });
        guLabelsRef.current.set(guName, overlay);
      }

      // 자치구를 고르면 그 자치구만 남긴다. 옆 자치구까지 덮여 있으면 어디를 보는지 흐려진다
      const shown = view === "gu" && (gu === null || gu === guName);
      polygons.forEach((polygon) => {
        polygon.setOptions(guName === gu ? style.guSelected : style.gu);
        polygon.setMap(shown ? map : null);
      });
      overlay.setMap(shown ? map : null);
    });
  }, [guBoundary, gu, mode, view]);

  // 동 경계는 한 번 만들어 두고 보이고 숨기는 것만 바꾼다.
  // 동을 고를 때마다 도형을 다시 만들면 340개를 매번 새로 그리게 된다
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || !dongBoundary) return;

    const statusById = new Map(items.map((item) => [item.id, item.status]));
    const cache = dongPolygonsRef.current;
    const style = polygonStyle();

    dongBoundary.features.forEach((feature) => {
      const dong = feature.properties.dong;
      const status = statusById.get(dong);
      let polygons = cache.get(dong);

      if (view === "gu" || !status) {
        polygons?.forEach((polygon) => polygon.setMap(null));
        return;
      }

      if (!polygons) {
        polygons = toKakaoPolygons(kakao, feature.geometry, () => onSelectRef.current(dong));
        cache.set(dong, polygons);
      }

      polygons.forEach((polygon) => {
        polygon.setOptions(style[dong === selectedId ? "selected" : status]);
        polygon.setMap(map);
      });
    });
  }, [dongBoundary, items, mode, selectedId, view]);

  // ponytail: 마커를 그릴 때마다 다시 만든다. 동은 최대 346개라 이 정도면 충분하고,
  // 더 늘어나면 MarkerClusterer와 bounds 기준 렌더링으로 올린다.
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map) return;

    overlaysRef.current.forEach((overlay) => overlay.setMap(null));
    overlaysRef.current.clear();

    // 자치구를 보는 중에는 자치구 이름만 남긴다. 고른 동이 있으면 그것만 함께 보여 준다
    const shown = view === "dong" ? items : items.filter((item) => item.id === selectedId);

    shown.forEach((item) => {
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
  }, [items, mode, selectedId, view]);

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
    // setBounds가 바꾼 확대 수준을 바로 읽는다. zoom_changed를 기다리면 한 박자 늦게 바뀐다
    setLevel(map.getLevel());
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
            ? view === "gu" && guBoundary
              ? "자치구를 누르면 동이 보여요"
              : `${items.length}개 동`
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
      {boundarySource ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
          {boundarySource}
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
}: Omit<MapPanelProps, "kakaoJsKey" | "gu" | "onSelectGu"> & { bounds: Bounds }) {
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

/** 자치구 이름표. 경계 위에 올라가므로 마커보다 크고 배경을 깔아 읽히게 한다 */
function guLabelClassName() {
  return cn(
    "-translate-x-1/2 -translate-y-1/2 rounded-md bg-card/85 px-2 py-1",
    "text-xs font-semibold text-foreground shadow-float ring-1 ring-border",
    "transition-transform duration-150 hover:scale-105",
  );
}

/* ---------------------------------------------------------------- */
/* 법정동·자치구 경계 (53.export_front_boundary.py 산출물)           */
/* ---------------------------------------------------------------- */

/** GeoJSON 도형 하나를 Kakao Polygon으로 만든다. 떨어진 조각은 도형도 따로 만든다 */
function toKakaoPolygons(kakao: Kakao, geometry: BoundaryGeometry, onClick: () => void) {
  return boundaryPaths(geometry).map((rings) => {
    const path = rings.map((ring) =>
      ring.map((point) => new kakao.maps.LatLng(point.lat, point.lng)),
    );
    const polygon = new kakao.maps.Polygon({ path });
    kakao.maps.event.addListener(polygon, "click", onClick);
    return polygon;
  });
}

/**
 * 경계 색은 마커와 같은 값을 쓴다. globals.css의 토큰에서 읽어 와서
 * 색을 바꿀 때 두 군데를 고치지 않게 한다.
 * 경계는 배경이라 채우기를 옅게 두고, 고른 것만 진하게 만든다.
 * ponytail: 자치구마다 다른 색을 주지 않는다. 25색은 눈이 아프고, 색이 다르면
 * 값이 다르다는 뜻으로 읽힌다. 여기서는 자치구를 나누는 선일 뿐이다.
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
    gu: {
      strokeWeight: 2,
      strokeColor: primary,
      strokeOpacity: 0.8,
      fillColor: primary,
      fillOpacity: 0.1,
    },
    guSelected: {
      strokeWeight: 3,
      strokeColor: primary,
      strokeOpacity: 1,
      fillColor: primary,
      fillOpacity: 0.16,
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
  getLevel: () => number;
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
      addListener: (target: KakaoPolygon | KakaoMap, type: string, handler: () => void) => void;
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
