// 실행: node --test lib/format.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import { changeMeaningSentence, formatTwelveMonthRange } from "./format.ts";

test("지난 12개월을 시작 분기와 끝 분기로 풀어 쓴다", () => {
  assert.equal(formatTwelveMonthRange("2026Q2"), "2025년 2분기 → 2026년 2분기");
});

test("가격 지수 변화의 방향을 쉬운 문장으로 설명한다", () => {
  assert.match(changeMeaningSentence(12.3), /1년 전보다 12.3% 높게/);
  assert.match(changeMeaningSentence(-4.5), /1년 전보다 4.5% 낮게/);
  assert.match(changeMeaningSentence(0), /1년 전과 같게/);
  assert.match(changeMeaningSentence(null), /계산할 수 없어요/);
});
