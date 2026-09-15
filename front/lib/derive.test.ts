// 실행: node --test lib/derive.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import { deriveStatus, deriveTags, logChangeToPct } from "./derive.ts";
import { shiftQuarter } from "./quarter.ts";

test("log 변화율을 퍼센트로 바꾼다", () => {
  assert.equal(logChangeToPct(0), 0);
  assert.equal(logChangeToPct(0.0315), 3.2);
  assert.equal(logChangeToPct(-0.0513), -5);
  assert.equal(logChangeToPct(null), null);
});

test("예측 행이 없으면 매매 기준 충족 여부로 상태를 나눈다", () => {
  assert.equal(deriveStatus("PREDICTED", true), "PREDICTED");
  assert.equal(deriveStatus(null, true), "NOT_SERVED");
  assert.equal(deriveStatus(null, false), "INSUFFICIENT_SALES");
  assert.equal(deriveStatus("알 수 없는 값", false), "INSUFFICIENT_SALES");
});

test("지역 태그는 관측값 기준으로만 붙는다", () => {
  assert.deepEqual(
    deriveTags({
      jeonse_ratio_4q: 0.62,
      old30_share_4q: 0.1,
      completed_share_8q: 0,
      redevelop_zone_count: 2,
    }),
    ["정비사업 진행", "전세 비중 높음"],
  );
  assert.deepEqual(
    deriveTags({
      jeonse_ratio_4q: null,
      old30_share_4q: null,
      completed_share_8q: null,
      redevelop_zone_count: 0,
    }),
    [],
  );
});

test("분기 이동은 연도를 넘어간다", () => {
  assert.equal(shiftQuarter("2026Q2", -4), "2025Q2");
  assert.equal(shiftQuarter("2026Q1", -1), "2025Q4");
  assert.equal(shiftQuarter("2025Q4", 1), "2026Q1");
  assert.equal(shiftQuarter("이상한 값", -4), "이상한 값");
});
