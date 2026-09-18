import { boundsOf, type Bounds } from "./map.ts";

export type Position = [lng: number, lat: number];
export type PolygonCoordinates = Position[][];
export type BoundaryGeometry =
  | { type: "Polygon"; coordinates: PolygonCoordinates }
  | { type: "MultiPolygon"; coordinates: PolygonCoordinates[] };

export type DongBoundaryFeature = {
  type: "Feature";
  properties: {
    dong: string;
    sgg_cd: string;
    emd_cd: string;
    umd_nm: string;
    gu_name: string;
  };
  geometry: BoundaryGeometry;
};

export type GuBoundaryFeature = {
  type: "Feature";
  properties: { sgg_cd: string; gu_name: string };
  geometry: BoundaryGeometry;
};

export type BoundaryFeature = DongBoundaryFeature | GuBoundaryFeature;
export type FeatureCollection<T extends BoundaryFeature> = {
  type: "FeatureCollection";
  features: T[];
};

export type BoundaryData = {
  dongs: DongBoundaryFeature[];
  gus: GuBoundaryFeature[];
};

/** Polygon과 MultiPolygon을 지도 SDK가 반복하기 쉬운 Polygon 배열로 맞춘다. */
export function polygonsOf(geometry: BoundaryGeometry): PolygonCoordinates[] {
  return geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
}

export function boundaryId(feature: BoundaryFeature): string {
  return "dong" in feature.properties ? feature.properties.dong : feature.properties.gu_name;
}

/** 현재 지도 단계와 필터 맥락에 맞는 경계만 고른다. */
export function visibleBoundaries(
  data: BoundaryData,
  itemKind: "gu" | "dong",
  itemIds: string[],
  activeGuName?: string | null,
): BoundaryFeature[] {
  if (itemKind === "gu") return data.gus;
  if (activeGuName) return data.dongs.filter((feature) => feature.properties.gu_name === activeGuName);

  const visibleIds = new Set(itemIds);
  return data.dongs.filter((feature) => visibleIds.has(feature.properties.dong));
}

export function boundsOfFeature(feature: BoundaryFeature): Bounds {
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLng = Infinity;
  let maxLng = -Infinity;

  for (const polygon of polygonsOf(feature.geometry)) {
    for (const ring of polygon) {
      for (const [lng, lat] of ring) {
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
        minLng = Math.min(minLng, lng);
        maxLng = Math.max(maxLng, lng);
      }
    }
  }

  return { minLat, maxLat, minLng, maxLng };
}

/** 여러 경계를 모두 포함하는 최소 범위. 초기 서울 화면처럼 여백 없이 꽉 채울 때 쓴다. */
export function tightBoundsOfFeatures(features: BoundaryFeature[]): Bounds | null {
  if (features.length === 0) return null;
  const bounds = features.map(boundsOfFeature);
  return {
    minLat: Math.min(...bounds.map((item) => item.minLat)),
    maxLat: Math.max(...bounds.map((item) => item.maxLat)),
    minLng: Math.min(...bounds.map((item) => item.minLng)),
    maxLng: Math.max(...bounds.map((item) => item.maxLng)),
  };
}

/** 각 도형의 모서리만 다시 범위 계산에 넣어 최소 폭과 바깥 여백을 함께 적용한다. */
export function boundsOfFeatures(features: BoundaryFeature[]): Bounds | null {
  const tightBounds = tightBoundsOfFeatures(features);
  if (!tightBounds) return null;
  return boundsOf(
    [
      { lat: tightBounds.minLat, lng: tightBounds.minLng },
      { lat: tightBounds.maxLat, lng: tightBounds.maxLng },
    ],
  );
}
