// 실행: node --test lib/map.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import { boundsOf, projectToBounds, SEOUL_BOUNDS } from "./map.ts";

const span = (bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number }) => ({
  lat: bounds.maxLat - bounds.minLat,
  lng: bounds.maxLng - bounds.minLng,
});

test("좌표가 없으면 서울 전체 범위를 쓴다", () => {
  assert.deepEqual(boundsOf([]), SEOUL_BOUNDS);
});

test("자치구 하나만 남으면 그 좌표들만 담는 좁은 범위가 나온다", () => {
  const gangnam = [
    { lat: 37.49, lng: 127.05 },
    { lat: 37.52, lng: 127.09 },
  ];
  const bounds = boundsOf(gangnam);
  // 서울 전체보다 훨씬 좁다
  assert.ok(span(bounds).lat < span(SEOUL_BOUNDS).lat / 3);
  assert.ok(span(bounds).lng < span(SEOUL_BOUNDS).lng / 3);
  // 양 끝 동이 범위 안에 들어온다
  assert.ok(bounds.minLat < 37.49 && bounds.maxLat > 37.52);
  assert.ok(bounds.minLng < 127.05 && bounds.maxLng > 127.09);
});

test("보이는 범위가 지도 한 축의 90%를 차지하도록 여백을 둔다", () => {
  const points = [
    { lat: 37.4, lng: 126.8 },
    { lat: 37.6, lng: 127.2 },
  ];
  const bounds = boundsOf(points);

  assert.ok(Math.abs(0.2 / span(bounds).lat - 0.9) < 1e-9);
  assert.ok(Math.abs(0.4 / span(bounds).lng - 0.9) < 1e-9);
});

test("동이 하나뿐이어도 최소 범위만큼은 벌어진다", () => {
  const bounds = boundsOf([{ lat: 37.5, lng: 127.0 }]);
  assert.ok(span(bounds).lat >= 0.02 - 1e-9);
  assert.ok(span(bounds).lng >= 0.025 - 1e-9);
  // 고른 동이 한가운데에 온다
  assert.ok(Math.abs((bounds.minLat + bounds.maxLat) / 2 - 37.5) < 1e-9);
});

test("범위 안의 좌표는 0~100% 위치로 바뀐다", () => {
  const bounds = { minLat: 37.4, maxLat: 37.6, minLng: 126.8, maxLng: 127.2 };
  const middle = projectToBounds({ lat: 37.5, lng: 127.0 }, bounds);
  assert.equal(Math.round(middle.x), 50);
  assert.equal(Math.round(middle.y), 50);
  // 위도가 높을수록 화면 위쪽이다
  assert.ok(projectToBounds({ lat: 37.59, lng: 127.0 }, bounds).y < middle.y);
});
