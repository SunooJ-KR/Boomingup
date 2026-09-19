// 실행: node --test lib/paginate.test.ts
import assert from "node:assert/strict";
import { test } from "node:test";

import { clampPage, fitPageSize, pageCount, pageWindow } from "./paginate.ts";

test("항목이 없어도 페이지는 1개다", () => {
  assert.equal(pageCount(0, 10), 1);
  assert.equal(pageCount(346, 10), 35);
  assert.equal(pageCount(20, 10), 2);
});

test("페이지 번호는 1과 마지막 페이지 사이로 맞춰진다", () => {
  assert.equal(clampPage(0, 346, 10), 1);
  assert.equal(clampPage(99, 346, 10), 35);
  assert.equal(clampPage(3, 346, 10), 3);
  // 필터로 목록이 3개만 남으면 어떤 번호를 들고 있어도 1페이지로 돌아온다
  assert.equal(clampPage(12, 3, 10), 1);
});

test("페이지 번호 창은 처음과 마지막을 항상 포함한다", () => {
  assert.deepEqual(pageWindow(6, 35), [1, "gap", 4, 5, 6, 7, 8, "gap", 35]);
  assert.deepEqual(pageWindow(1, 35), [1, 2, 3, "gap", 35]);
  assert.deepEqual(pageWindow(35, 35), [1, "gap", 33, 34, 35]);
});

test("페이지가 적으면 생략 표시 없이 전부 보여준다", () => {
  assert.deepEqual(pageWindow(1, 1), [1]);
  assert.deepEqual(pageWindow(2, 4), [1, 2, 3, 4]);
  assert.deepEqual(pageWindow(1, 0), []);
});

test("한 페이지 개수는 목록 칸 높이에 들어가는 만큼으로 정해진다", () => {
  // 높이 900에 항목 120짜리면 들어가는 만큼인 7개를 보여준다
  assert.equal(fitPageSize(900, 120), 7);
  assert.equal(fitPageSize(1800, 120), 15);
  // 화면이 아주 커도 상한을 넘지 않는다
  assert.equal(fitPageSize(9000, 120), 24);
});

test("칸이 아주 낮아도 최소 개수는 보여준다", () => {
  // 목록 칸 최소 높이(12rem)에 항목 120짜리는 1개뿐이지만 목록으로 보이게 최소 개수를 채운다
  assert.equal(fitPageSize(192, 120), 4);
});

test("높이를 재지 못하면 최소 개수로 돌아간다", () => {
  assert.equal(fitPageSize(0, 120), 4);
  assert.equal(fitPageSize(900, 0), 4);
  assert.equal(fitPageSize(Number.NaN, 120), 4);
});
