// 실행: node --test lib/filter.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EMPTY_FILTER,
  filterDongs,
  hasDetailFilter,
  isFilterActive,
  priceBandsOf,
  regionTagLabel,
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

test("상세 조건 여부는 검색어와 자치구를 제외하고 판단한다", () => {
  assert.equal(hasDetailFilter(withFilter({ query: "개포", gu: "강남구" })), false);
  assert.equal(hasDetailFilter(withFilter({ flagged: true })), true);
  assert.equal(hasDetailFilter(withFilter({ priceBand: [1000, 2000] })), true);
  assert.equal(hasDetailFilter(withFilter({ structureTypes: [1] })), true);
  assert.equal(hasDetailFilter(withFilter({ tags: ["거래 많은 동"] })), true);
});

test("지역 태그 이름은 정렬 기준이 드러나게 바꾼다", () => {
  assert.equal(regionTagLabel("거래 많은 동"), "거래 많은 순");
  assert.equal(regionTagLabel("정비사업 정보 있음"), "정비사업 구역 많은 순");
  assert.equal(regionTagLabel("알 수 없는 태그"), "알 수 없는 태그");
});

test("지역 태그를 선택하면 해당 관측값의 내림차순으로 정렬한다", () => {
  const tagged = [
    {
      ...dongs[0],
      dong_id: "a",
      umd_name: "첫째동",
      tags: ["전세가율 높은 동"],
      tag_sort_values: { "전세가율 높은 동": 0.62 },
    },
    {
      ...dongs[0],
      dong_id: "b",
      umd_name: "둘째동",
      tags: ["전세가율 높은 동"],
      tag_sort_values: { "전세가율 높은 동": 0.74 },
    },
  ] as DongSummary[];

  assert.deepEqual(
    names(filterDongs(tagged, withFilter({ tags: ["전세가율 높은 동"] }))),
    ["둘째동", "첫째동"],
  );
});

test("거래 태그도 화면용 건수가 아니라 태그 산정값으로 정렬한다", () => {
  const tagged = [
    {
      ...dongs[0],
      dong_id: "a",
      umd_name: "첫째동",
      n_sales_4q: 900,
      tags: ["거래 많은 동"],
      tag_sort_values: { "거래 많은 동": 120 },
    },
    {
      ...dongs[0],
      dong_id: "b",
      umd_name: "둘째동",
      n_sales_4q: 500,
      tags: ["거래 많은 동"],
      tag_sort_values: { "거래 많은 동": 240 },
    },
  ] as DongSummary[];

  assert.deepEqual(
    names(filterDongs(tagged, withFilter({ tags: ["거래 많은 동"] }))),
    ["둘째동", "첫째동"],
  );
});
