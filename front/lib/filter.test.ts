// 실행: node --test lib/filter.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EMPTY_FILTER,
  filterDongs,
  hasDetailFilter,
  isFilterActive,
  priceBandsOf,
  regionTagMetricLabel,
  sortDongs,
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
    tag_sort_values: { "정비사업 정보 있음": 2, "전세가율 높은 동": 0.45 },
  },
  {
    gu_name: "마포구",
    umd_name: "연남동",
    ppm2_med_4q_manwon: 1200,
    sample_flags: ["FEW_SALES"],
    structure_type: 1,
    tags: [],
    tag_sort_values: { "정비사업 정보 있음": 0, "전세가율 높은 동": 0.52 },
  },
  {
    gu_name: "강남구",
    umd_name: "대치동",
    ppm2_med_4q_manwon: null,
    sample_flags: ["HIGH_INDEX_ERROR"],
    structure_type: null,
    tags: ["전세가율 높은 동"],
    tag_sort_values: { "정비사업 정보 있음": null, "전세가율 높은 동": 0.74 },
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

test("상세 조건 여부는 검색어와 자치구를 제외하고 판단한다", () => {
  assert.equal(hasDetailFilter(withFilter({ query: "개포", gu: "강남구" })), false);
  assert.equal(hasDetailFilter(withFilter({ flagged: true })), true);
  assert.equal(hasDetailFilter(withFilter({ priceBand: [1000, 2000] })), true);
  assert.equal(hasDetailFilter(withFilter({ structureTypes: [1] })), true);
});

test("지역 특성 이름은 정렬할 관측값이 드러나게 바꾼다", () => {
  assert.equal(regionTagMetricLabel("거래 많은 동"), "거래 건수");
  assert.equal(regionTagMetricLabel("정비사업 정보 있음"), "정비사업 구역 수");
  assert.equal(regionTagMetricLabel("알 수 없는 태그"), "알 수 없는 태그");
});

test("㎡당 중앙가는 높은순과 낮은순으로 정렬하고 결측값은 마지막에 둔다", () => {
  assert.deepEqual(
    names(sortDongs(dongs, { by: "price", direction: "desc" })),
    ["개포동", "연남동", "대치동"],
  );
  assert.deepEqual(
    names(sortDongs(dongs, { by: "price", direction: "asc" })),
    ["연남동", "개포동", "대치동"],
  );
});

test("지역 특성은 전체 동을 유지하면서 높은순과 낮은순으로 정렬한다", () => {
  assert.deepEqual(
    names(sortDongs(dongs, { by: "tag", tag: "전세가율 높은 동", direction: "desc" })),
    ["대치동", "연남동", "개포동"],
  );
  assert.deepEqual(
    names(sortDongs(dongs, { by: "tag", tag: "전세가율 높은 동", direction: "asc" })),
    ["개포동", "연남동", "대치동"],
  );
});
