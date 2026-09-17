-- ============================================================================
-- 004_dong_support.sql
-- ============================================================================
-- 목적: 판단 보조 화면이 읽는 동별 통합 산출물을 담을 테이블을 만든다.
-- 배경: 동별 상승률 예측을 화면에서 내리고 표본 상태·변화 표시·구조 유형·
--       함께 볼 동 네 가지를 내보내기로 했다(docs/decisions.md 결정 66).
-- 컬럼 정의: docs/feature-spec.md §5. 여기에 snapshot_id만 앞에 붙인다.
--           컬럼 이름이 곧 화면 payload 필드명이므로 바꾸려면
--           docs/payload-schema.md도 같이 고친다.
-- 산출: models/index/69.build_dong_support.py -> output/69.1.dong_support.txt
-- 적재: data/db/50.load_db.py --kind support
-- app.dong_prediction은 더 이상 읽지 않지만 지우지 않고 남긴다(결정 66).
-- ============================================================================

begin;

create table if not exists app.dong_support (
    snapshot_id bigint not null references app.dataset_snapshot(snapshot_id) on delete cascade,
    dong text not null,
    -- 네 산출물이 모두 같은 기준 분기 T를 쓴다. 예: '2026Q2'
    as_of text not null,
    -- F-1 표본 상태. 매매 0건은 0이고, 값이 없는 것과 구분한다.
    sale_n_all_4q integer,
    n_complexes_4q integer,
    -- 매매 0건이면 비중을 낼 수 없어 null이다.
    dominant_complex_share_4q double precision,
    index_se double precision,
    index_se_band text check (index_se_band in ('LOW', 'MID', 'HIGH')),
    -- 주의 flag를 ';'로 이은 문자열. 없으면 null이다. 빈 문자열을 쓰지 않는다.
    sample_flags text,
    -- F-2 12개월 변화. 단위는 log이며 화면에서 %로 바꾼다.
    change_12m double precision,
    -- 서울 세대수 가중 평균. 모든 행에 같은 값이 들어간다.
    mu_12m double precision,
    delta_12m double precision,
    delta_se double precision,
    delta_state text check (delta_state in ('DISTINGUISHABLE', 'INDISTINGUISHABLE')),
    -- 5년 창에 지수가 20분기 미만이면 세 값이 모두 null이다.
    peak_5y_gap double precision,
    peak_5y_gap_se double precision,
    peak_5y_state text check (peak_5y_state in ('AT_PEAK', 'DISTINGUISHABLE', 'INDISTINGUISHABLE')),
    -- F-3 구조 유형. output/66.1의 최신 기점 클러스터 번호 0~3.
    structure_type integer check (structure_type between 0 and 3),
    structure_desc text,
    -- F-4 함께 볼 동. [{"dong":"…","reason":"…"}] 형태이며 조건에 못 미치면 null이다.
    -- 빈 배열로 두지 않는다. 화면이 null일 때 블록을 통째로 숨긴다.
    peer_dongs jsonb,
    primary key (snapshot_id, dong),
    foreign key (snapshot_id, dong) references app.dong(snapshot_id, dong) on delete cascade
);

comment on table app.dong_support is
    '판단 보조 화면용 동별 통합 산출물. 산식은 docs/feature-spec.md, 산출은 69.build_dong_support.py';

grant select on app.dong_support to boomingup_readonly;
grant select, insert, update, delete on app.dong_support to boomingup_loader;

commit;
