// 실행: node --test lib/filter.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EMPTY_FILTER,
  filterDongs,
  isFilterActive,
  priceBandsOf,
  type DongFilter,
} from "./filter.ts";
import type { DongSummary } from "./types.ts";

const dongs = [
  {
    gu_name: "강남구",
    umd_name: "개포동",
    ppm2_med_4q_manwon: 2480,
    sample_flags: [],
    structure_type: 0,
    tags: ["정비사업 정보 있음"],
  },
  {
    gu_name: "마포구",
    umd_name: "연남동",
    ppm2_med_4q_manwon: 1200,
    sample_flags: ["FEW_SALES"],
    structure_type: 1,
    tags: [],
  },
  {
    gu_name: "강남구",
    umd_name: "대치동",
    ppm2_med_4q_manwon: null,
    sample_flags: ["HIGH_INDEX_ERROR"],
    structure_type: null,
    tags: ["전세가율 높은 동"],
  },
] as unknown as DongSummary[];

const withFilter = (patch: Partial<DongFilter>): DongFilter => ({ ...EMPTY_FILTER, ...patch });
const names = (list: DongSummary[]) => list.map((dong) => dong.umd_name);

test("조건이 없으면 전부 통과한다", () => {
  assert.equal(filterDongs(dongs, EMPTY_FILTER).length, 3);
  assert.equal(isFilterActive(EMPTY_FILTER), false);
});

test("검색어는 동 이름과 자치구 이름에 모두 걸린다", () => {
  assert.deepEqual(names(filterDongs(dongs, withFilter({ query: "개포" }))), ["개포동"]);
  assert.deepEqual(names(filterDongs(dongs, withFilter({ query: "강남구" }))), ["개포동", "대치동"]);
  assert.deepEqual(names(filterDongs(dongs, withFilter({ query: " 연남 " }))), ["연남동"]);
});

test("표본 상태는 주의 유무로만 나눈다", () => {
  assert.deepEqual(names(filterDongs(dongs, withFilter({ flagged: false }))), ["개포동"]);
  assert.deepEqual(names(filterDongs(dongs, withFilter({ flagged: true }))), ["연남동", "대치동"]);
});

test("가격을 모르는 동은 가격대를 고르면 남지 않는다", () => {
  assert.deepEqual(names(filterDongs(dongs, withFilter({ priceBand: [1000, 3000] }))), [
    "개포동",
    "연남동",
  ]);
  assert.deepEqual(names(filterDongs(dongs, withFilter({ priceBand: [0, 1500] }))), ["연남동"]);
});

test("구조 유형이 없는 동은 유형을 고르면 남지 않는다", () => {
  assert.deepEqual(names(filterDongs(dongs, withFilter({ structureTypes: [0, 1] }))), [
    "개포동",
    "연남동",
  ]);
  assert.deepEqual(names(filterDongs(dongs, withFilter({ structureTypes: [3] }))), []);
});

test("자치구, 태그 필터가 함께 걸린다", () => {
  const filter = withFilter({ gu: "강남구", tags: ["정비사업 정보 있음"] });
  assert.deepEqual(names(filterDongs(dongs, filter)), ["개포동"]);
  assert.equal(isFilterActive(filter), true);
});

test("태그는 선택한 것을 모두 가진 동만 남긴다", () => {
  const filter = withFilter({ tags: ["정비사업 정보 있음", "전세가율 높은 동"] });
  assert.deepEqual(names(filterDongs(dongs, filter)), []);
});

test("가격대 구간은 서로 겹치지 않고 전체를 덮는다", () => {
  const list = [100, 200, 300, 400, 500, 600, 700, 800].map(
    (price) => ({ ppm2_med_4q_manwon: price }) as unknown as DongSummary,
  );
  const bands = priceBandsOf(list);
  assert.equal(bands.length, 4);
  assert.equal(bands[0][0], 100);
  assert.equal(bands[3][1], 800);
  for (let at = 1; at < bands.length; at += 1) {
    assert.ok(bands[at][0] > bands[at - 1][1]);
  }
  // 값이 적으면 구간을 만들지 않는다
  assert.deepEqual(priceBandsOf(list.slice(0, 3)), []);
});
