// 실행: node --test lib/gu.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import { guSummariesOf } from "./gu.ts";
import type { DongSummary } from "./types.ts";

const dong = (dongId: string, guName: string, umdName: string): DongSummary => ({
  dong_id: dongId,
  sgg_cd: dongId.slice(0, 5),
  gu_name: guName,
  umd_name: umdName,
  n_sales_4q: 0,
  ppm2_med_4q_manwon: null,
  sample_flags: [],
  index_se_band: null,
  structure_type: null,
  structure_desc: null,
});

test("자치구를 가나다순으로 묶고 법정동 수를 센다", () => {
  const summaries = guSummariesOf(
    [dong("11710_잠실동", "송파구", "잠실동"), dong("11680_개포동", "강남구", "개포동"), dong("11680_대치동", "강남구", "대치동")],
    {},
  );

  assert.deepEqual(
    summaries.map(({ name, dongCount }) => ({ name, dongCount })),
    [
      { name: "강남구", dongCount: 2 },
      { name: "송파구", dongCount: 1 },
    ],
  );
});

test("자치구 중심점은 좌표가 있는 법정동만 평균낸다", () => {
  const summaries = guSummariesOf(
    [dong("a", "강남구", "개포동"), dong("b", "강남구", "대치동"), dong("c", "강남구", "도곡동")],
    {
      a: { lat: 37.5, lng: 127.0 },
      b: { lat: 37.52, lng: 127.04 },
    },
  );

  assert.ok(Math.abs((summaries[0].center?.lat ?? 0) - 37.51) < 1e-9);
  assert.ok(Math.abs((summaries[0].center?.lng ?? 0) - 127.02) < 1e-9);
});
