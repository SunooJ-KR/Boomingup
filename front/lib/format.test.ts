// 실행: node --test lib/format.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  changeMeaningSentence,
  compactClusterDesc,
  formatQuarter,
  formatTwelveMonthRange,
  sampleFootnote,
  structureFootnote,
} from "./format.ts";
import type { Meta } from "./types.ts";

const META: Meta = {
  as_of_quarter: "2026Q2",
  data_period: { sale: "2006-01 ~ 2026-08", rent: "2011-01 ~ 2026-08" },
  support_as_of: "2026Q2",
  cluster_as_of: "2026Q2",
  thresholds: {
    few_sales: 20,
    one_complex_share: 0.5,
    high_index_se: 0.032,
    delta_sigma: 2,
  },
  regulation_as_of: "2026-06-30",
  seoul_apartment_permit_zone: true,
};

test("분기 코드를 사용자용 표현으로 바꾼다", () => {
  assert.equal(formatQuarter("2026Q2"), "2026년 2분기");
  assert.equal(sampleFootnote(META), "최근 1년은 2026년 2분기 기준 직전 4분기예요.");
  assert.match(structureFootnote(META), /2026년 2분기 기준/);
});

test("지난 12개월을 시작 분기와 끝 분기로 풀어 쓴다", () => {
  assert.equal(formatTwelveMonthRange("2026Q2"), "2025년 2분기 → 2026년 2분기");
});

test("가격 지수 변화의 방향을 쉬운 문장으로 설명한다", () => {
  assert.match(changeMeaningSentence(12.3), /1년 전보다 12.3% 높게/);
  assert.match(changeMeaningSentence(-4.5), /1년 전보다 4.5% 낮게/);
  assert.match(changeMeaningSentence(0), /1년 전과 같게/);
  assert.match(changeMeaningSentence(null), /계산할 수 없어요/);
});

test("클러스터 설명은 필터 버튼에 맞게 짧게 줄인다", () => {
  assert.equal(
    compactClusterDesc("평당가 높음 · 강남 7km대"),
    "가격대 높음 · 강남 가까움",
  );
  assert.equal(compactClusterDesc("강남 13km대 · 도심 9km대"), "강남·도심에서 먼 편");
  assert.equal(
    compactClusterDesc("신축 비중 높음 · 아파트 세대수 적음"),
    "신축 많음 · 아파트 세대 적음",
  );
  assert.equal(
    compactClusterDesc("아파트 세대수 적음 · 도심 3km대"),
    "아파트 세대 적음 · 도심 가까움",
  );
});
