// 실행: node --test lib/boundary.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  boundaryId,
  boundsOfFeature,
  polygonsOf,
  visibleBoundaries,
  type BoundaryData,
  type BoundaryGeometry,
  type DongBoundaryFeature,
  type GuBoundaryFeature,
} from "./boundary.ts";

const geometry: BoundaryGeometry = {
  type: "Polygon",
  coordinates: [[[126.9, 37.5], [127, 37.5], [127, 37.6], [126.9, 37.5]]],
};
const dong = (id: string, guName: string): DongBoundaryFeature => ({
  type: "Feature",
  properties: { dong: id, sgg_cd: id.slice(0, 5), emd_cd: `${id.slice(0, 5)}101`, umd_nm: id.slice(6), gu_name: guName },
  geometry,
});
const gu = (name: string): GuBoundaryFeature => ({
  type: "Feature",
  properties: { sgg_cd: "11110", gu_name: name },
  geometry,
});
const data: BoundaryData = {
  dongs: [dong("11110_청운동", "종로구"), dong("11680_역삼동", "강남구")],
  gus: [gu("종로구"), gu("강남구")],
};

test("지도 단계에 따라 자치구 또는 법정동 경계를 고른다", () => {
  assert.deepEqual(visibleBoundaries(data, "gu", []).map(boundaryId), ["종로구", "강남구"]);
  assert.deepEqual(visibleBoundaries(data, "dong", [], "강남구").map(boundaryId), ["11680_역삼동"]);
  assert.deepEqual(visibleBoundaries(data, "dong", ["11110_청운동"]).map(boundaryId), ["11110_청운동"]);
});

test("Polygon을 한 개짜리 Polygon 배열로 바꾸고 경계 범위를 계산한다", () => {
  assert.equal(polygonsOf(geometry).length, 1);
  assert.deepEqual(boundsOfFeature(data.dongs[0]), {
    minLat: 37.5,
    maxLat: 37.6,
    minLng: 126.9,
    maxLng: 127,
  });
});
