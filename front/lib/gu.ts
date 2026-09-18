import type { DongSummary } from "./types";

export type GuSummary = {
  name: string;
  dongCount: number;
  center: { lat: number; lng: number } | null;
};

/** 법정동 목록을 자치구별로 묶고, 지도용 중심점은 동 대표 좌표의 평균으로 잡는다. */
export function guSummariesOf(
  dongs: DongSummary[],
  centers: Record<string, { lat: number; lng: number }>,
): GuSummary[] {
  const groups = new Map<string, { dongCount: number; points: { lat: number; lng: number }[] }>();

  dongs.forEach((dong) => {
    const group = groups.get(dong.gu_name) ?? { dongCount: 0, points: [] };
    group.dongCount += 1;
    const center = centers[dong.dong_id];
    if (center) group.points.push(center);
    groups.set(dong.gu_name, group);
  });

  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b, "ko"))
    .map(([name, group]) => ({
      name,
      dongCount: group.dongCount,
      center:
        group.points.length === 0
          ? null
          : {
              lat: group.points.reduce((sum, point) => sum + point.lat, 0) / group.points.length,
              lng: group.points.reduce((sum, point) => sum + point.lng, 0) / group.points.length,
            },
    }));
}
