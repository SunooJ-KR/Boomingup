-- ============================================================================
-- 003_dong_index_se.sql
-- ============================================================================
-- 목적: 동×분기 지수에 추정오차(log_index_se) 자리를 만든다.
-- 배경: 지수 추정오차 정의는 docs/decisions.md 결정 42를 따른다.
--       measurement-error 조정, 측정오차 진단이 모두 이 값을 입력으로 쓴다.
-- 값의 뜻: 보고한 동 지수가 참 동 지수에서 떨어져 있을 수 있는 크기(log 단위).
--         표본 잡음과 구 지수로 되돌아간 수축 편향을 합친 값이다.
--         산출은 models/index/60.build_dong_index_se.py.
-- 기존 snapshot 행은 값이 없으므로 nullable로 둔다.
-- ============================================================================

alter table app.dong_index
    add column if not exists log_index_se double precision;

comment on column app.dong_index.log_index_se is
    '동 지수 추정오차(log 단위). 표본 잡음 + 구 지수 수축 편향. 60.build_dong_index_se.py 산출';
