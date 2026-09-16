"use client";

import { useEffect, useRef, useState } from "react";

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

/** 좌표 미리보기용 서울 경계. 다른 지역을 다루면 이 값만 바꾼다. */
const BOUNDS = { minLng: 126.74, maxLng: 127.2, minLat: 37.42, maxLat: 37.72 };

function projectToMap(lat: number, lng: number) {
  const x = ((lng - BOUNDS.minLng) / (BOUNDS.maxLng - BOUNDS.minLng)) * 100;
  const y = (1 - (lat - BOUNDS.minLat) / (BOUNDS.maxLat - BOUNDS.minLat)) * 100;
  return { x: Math.max(4, Math.min(96, x)), y: Math.max(6, Math.min(94, y)) };
}

export function MapPanel({ items, selectedId, onSelect, kakaoJsKey }: MapPanelProps) {
  const [mode, setMode] = useState<Mode>(kakaoJsKey ? "loading" : "fallback");
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  const overlaysRef = useRef(new Map<string, KakaoOverlay>());
  // 마커 DOM은 매번 다시 만들지 않으므로 최신 콜백을 ref로 들고 있는다
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

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
  useEffect(() => {
    const kakao = getKakao();
    const map = mapRef.current;
    if (mode !== "kakao" || !kakao || !map || !selectedId) return;
    const selected = items.find((item) => item.id === selectedId);
    if (!selected) return;
    map.panTo(new kakao.maps.LatLng(selected.lat, selected.lng));
  }, [selectedId, items, mode]);

  return (
    // 좌측 동 목록 열과 아래 끝을 맞춘다. 높이 계산은 dong-explorer의 좌측 열과 같은 값이다
    <div className="overflow-hidden rounded-lg border border-border bg-card shadow-panel lg:flex lg:h-[calc(100dvh-81px)] lg:flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">지도</p>
        <p className="text-xs text-muted-foreground">
          {mode === "kakao"
            ? `${items.length}개 동`
            : mode === "loading"
              ? "지도를 불러오는 중"
              : "좌표 미리보기"}
        </p>
      </div>

      {mode === "kakao" || mode === "loading" ? (
        <div ref={containerRef} className="h-[320px] w-full bg-muted lg:h-auto lg:min-h-0 lg:flex-1" />
      ) : (
        <FallbackPreview items={items} selectedId={selectedId} onSelect={onSelect} />
      )}

      {mode === "fallback" ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          Kakao 지도 키가 없거나 불러오지 못해 좌표 위치만 보여줍니다. 동 선택은 그대로 됩니다.
        </p>
      ) : null}

      {items.length === 0 ? (
        <p className="shrink-0 border-t border-border px-3 py-2 text-xs text-muted-foreground">
          표시할 좌표가 없습니다. 목록에서 동을 선택해 주세요.
        </p>
      ) : null}
    </div>
  );
}

function FallbackPreview({ items, selectedId, onSelect }: Omit<MapPanelProps, "kakaoJsKey">) {
  return (
    <div className="relative h-[320px] w-full bg-muted lg:h-auto lg:min-h-0 lg:flex-1">
      {items.map((item) => {
        const { x, y } = projectToMap(item.lat, item.lng);
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
/* Kakao SDK 로딩 (클라이언트 전용)                                  */
/* ---------------------------------------------------------------- */

type KakaoLatLng = object;
type KakaoMap = { panTo: (latlng: KakaoLatLng) => void };
type KakaoOverlay = { setMap: (map: KakaoMap | null) => void };
type Kakao = {
  maps: {
    load: (callback: () => void) => void;
    Map: new (container: HTMLElement, options: { center: KakaoLatLng; level: number }) => KakaoMap;
    LatLng: new (lat: number, lng: number) => KakaoLatLng;
    CustomOverlay: new (options: {
      position: KakaoLatLng;
      content: HTMLElement;
      zIndex: number;
    }) => KakaoOverlay;
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
