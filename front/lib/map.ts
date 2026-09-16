/**
 * 지도에 보여 줄 범위 계산. 좌표만 다루고 지도 SDK는 모른다.
 * Kakao 지도와 좌표 미리보기가 같은 범위를 쓰도록 여기에 모아 둔다.
 */

export type LatLng = { lat: number; lng: number };
export type Bounds = { minLat: number; maxLat: number; minLng: number; maxLng: number };

/** 좌표가 하나도 없을 때 쓰는 서울 전체 범위 */
export const SEOUL_BOUNDS: Bounds = {
  minLat: 37.42,
  maxLat: 37.72,
  minLng: 126.74,
  maxLng: 127.2,
};

/**
 * 동이 하나만 남아도 지도가 지나치게 확대되지 않도록 두는 최소 범위.
 * 위도 0.02도는 약 2.2km, 경도 0.025도는 서울 위도에서 약 2.2km다.
 * ponytail: 조절값이다. 한 동만 골랐을 때 주변이 더 보였으면 하면 이 값을 키운다.
 */
const MIN_SPAN_LAT = 0.02;
const MIN_SPAN_LNG = 0.025;
/** 가장자리 동이 화면 끝에 붙지 않도록 범위의 15%를 여유로 둔다 */
const PADDING_RATIO = 0.15;

/** 보이는 동을 모두 담는 범위. 자치구를 고르면 그 자치구만 담긴 범위가 나온다. */
export function boundsOf(points: LatLng[]): Bounds {
  if (points.length === 0) return SEOUL_BOUNDS;

  const lats = points.map((point) => point.lat);
  const lngs = points.map((point) => point.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);

  const padLat = Math.max((maxLat - minLat) * PADDING_RATIO, (MIN_SPAN_LAT - (maxLat - minLat)) / 2);
  const padLng = Math.max((maxLng - minLng) * PADDING_RATIO, (MIN_SPAN_LNG - (maxLng - minLng)) / 2);

  return {
    minLat: minLat - padLat,
    maxLat: maxLat + padLat,
    minLng: minLng - padLng,
    maxLng: maxLng + padLng,
  };
}

/** 범위 안의 좌표를 0~100% 위치로 옮긴다. 좌표 미리보기가 마커를 놓을 때 쓴다. */
export function projectToBounds(point: LatLng, bounds: Bounds) {
  const width = bounds.maxLng - bounds.minLng;
  const height = bounds.maxLat - bounds.minLat;
  const x = width > 0 ? ((point.lng - bounds.minLng) / width) * 100 : 50;
  const y = height > 0 ? (1 - (point.lat - bounds.minLat) / height) * 100 : 50;
  return { x: Math.max(4, Math.min(96, x)), y: Math.max(6, Math.min(94, y)) };
}

/** 53.export_front_boundary.py가 내보내는 경계 파일 형식 */
export type BoundaryGeometry = {
  type: "Polygon" | "MultiPolygon";
  /** Polygon은 링 목록, MultiPolygon은 링 목록의 목록이다. 좌표는 [경도, 위도] 순이다 */
  coordinates: number[][][] | number[][][][];
};
export type BoundaryFeature = {
  properties: { dong: string; umd_nm: string };
  geometry: BoundaryGeometry;
};
export type BoundaryCollection = { source: string; features: BoundaryFeature[] };

export type GuBoundaryFeature = {
  /** label은 자치구 이름을 적을 자리다. [경도, 위도] 순이다 */
  properties: { sgg_cd: string; gu_name: string; label: [number, number] };
  geometry: BoundaryGeometry;
};
export type GuBoundaryCollection = { source: string; features: GuBoundaryFeature[] };

/**
 * GeoJSON 도형을 지도에 그릴 경로로 바꾼다.
 * 결과는 [조각][링][좌표] 세 겹이다. 한 조각의 첫 링이 바깥이고 나머지는 구멍이라
 * 지도 쪽에서는 조각 하나가 도형 하나가 된다.
 */
export function boundaryPaths(geometry: BoundaryGeometry): LatLng[][][] {
  const polygons =
    geometry.type === "Polygon"
      ? [geometry.coordinates as number[][][]]
      : (geometry.coordinates as number[][][][]);
  return polygons.map((rings) =>
    rings.map((ring) => ring.map(([lng, lat]) => ({ lat, lng }))),
  );
}
