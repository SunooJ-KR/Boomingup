// 실행: node --test lib/derive.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import { buildTags, logChangeToPct, logSeToPct } from "./derive.ts";
import { shiftQuarter } from "./quarter.ts";

test("log 변화율을 퍼센트로 바꾼다", () => {
  assert.equal(logChangeToPct(0), 0);
  assert.equal(logChangeToPct(0.0315), 3.2);
  assert.equal(logChangeToPct(-0.0513), -5);
  assert.equal(logChangeToPct(null), null);
});

test("log 오차를 퍼센트 오차로 바꾼다", () => {
  // 중심이 0이면 위아래 폭이 같아 se를 그대로 퍼센트로 바꾼 값과 가깝다
  assert.equal(logSeToPct(0, 0.01), 1);
  // 중심이 커지면 같은 log 오차라도 퍼센트 폭이 넓어진다
  assert.ok((logSeToPct(0.2, 0.01) ?? 0) > (logSeToPct(0, 0.01) ?? 0));
  assert.equal(logSeToPct(0.1, null), null);
  assert.equal(logSeToPct(null, 0.1), null);
});

test("지역 태그는 서비스 대상 동 분포의 상위 30%를 기준으로 붙는다", () => {
  const rows = [10, 20, 30, 40, 50].map((n) => ({
    n_sales_4q: n,
    jeonse_ratio_4q: null,
    completed_share_8q: null,
    old30_share_4q: null,
    redevelop_zone_count: 0,
  }));

  // 5개 중 상위 30%는 2개다. 40건과 50건만 "거래 많은 동"이 된다
  assert.deepEqual(buildTags(rows), [[], [], [], ["거래 많은 동"], ["거래 많은 동"]]);
});

test("정비사업은 구역이 하나라도 있으면 붙고, 값이 없으면 태그가 없다", () => {
  const rows = [
    {
      n_sales_4q: null,
      jeonse_ratio_4q: null,
      completed_share_8q: null,
      old30_share_4q: null,
      redevelop_zone_count: 1,
    },
    {
      n_sales_4q: null,
      jeonse_ratio_4q: null,
      completed_share_8q: null,
      old30_share_4q: null,
      redevelop_zone_count: 0,
    },
  ];
  assert.deepEqual(buildTags(rows), [["정비사업 정보 있음"], []]);
});

test("분기 이동은 연도를 넘어간다", () => {
  assert.equal(shiftQuarter("2026Q2", -4), "2025Q2");
  assert.equal(shiftQuarter("2026Q1", -1), "2025Q4");
  assert.equal(shiftQuarter("2025Q4", 1), "2026Q1");
  assert.equal(shiftQuarter("이상한 값", -4), "이상한 값");
});
