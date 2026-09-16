// 실행: node --test lib/filter.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import { EMPTY_FILTER, filterDongs, isFilterActive, type DongFilter } from "./filter.ts";
import type { DongSummary } from "./types.ts";

const dongs = [
  { gu_name: "강남구", umd_name: "개포동", status: "PREDICTED", tags: ["정비사업 진행"] },
  { gu_name: "마포구", umd_name: "연남동", status: "INSUFFICIENT_SALES", tags: [] },
  { gu_name: "강남구", umd_name: "대치동", status: "NOT_SERVED", tags: ["전세 비중 높음"] },
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

test("자치구, 상태, 태그 필터가 함께 걸린다", () => {
  const filter = withFilter({ gu: "강남구", statuses: ["PREDICTED"], tags: ["정비사업 진행"] });
  assert.deepEqual(names(filterDongs(dongs, filter)), ["개포동"]);
  assert.equal(isFilterActive(filter), true);
});

test("태그는 선택한 것을 모두 가진 동만 남긴다", () => {
  const filter = withFilter({ tags: ["정비사업 진행", "전세 비중 높음"] });
  assert.deepEqual(names(filterDongs(dongs, filter)), []);
});
