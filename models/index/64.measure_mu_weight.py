# ============================================================================
# 64.measure_mu_weight.py
# ============================================================================
# Author:      yjkim
# Purpose:     μ(서울 공통 변화)의 가중 방식을 정하려고 세대수의 동 매핑 커버리지를 잰다
# Description: 계획 docs/model-develope-plan.md §1 선행 조건, 진행 P0-4.
#              재고(세대수)가중을 쓰려면 단지 세대수가 동에 붙어야 한다. 그런데
#              `app.complex`의 `bjd_code`는 5자리 자체 코드라 법정동 코드가 아니고
#              경계 테이블의 `emd_cd`(8자리)와 하나도 맞지 않는다. 그래서 단지를 동에
#              묶는 길은 매매 기록의 (sgg_cd, umd_nm)뿐이고, 매매가 한 번도 없던
#              단지는 동이 붙지 않는다.
#              커버리지가 낮으면 재고가중을 포기하고 거래가중으로 간다.
#
#              판정: 세대수 기준 커버리지 95% 이상이면 재고가중, 아니면 거래가중.
# ============================================================================

import importlib.util
from pathlib import Path

import pandas as pd
import psycopg

work_dir = Path(__file__).resolve().parents[2]
COVERAGE_THRESHOLD = 0.95


def database_url(env_name="DATABASE_READONLY_URL"):
    loader_path = work_dir / "data" / "db" / "50.load_db.py"
    spec = importlib.util.spec_from_file_location("boomingup_load_db", loader_path)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    return loader.database_url(env_name)


# ============================================================================
# 1. 단지 세대수와 매매로 붙는 동
# ============================================================================

COMPLEX_QUERY = """
    select c.apt_seq, c.name, c.total_households
    from app.complex c
    join app.dataset_snapshot s on s.snapshot_id = c.snapshot_id
    where s.is_active
"""

# 단지를 동에 묶는 유일한 경로다. 매매가 없던 단지는 여기에 나오지 않는다
MAPPING_QUERY = """
    select distinct c.apt_seq, t.sgg_cd || '_' || t.umd_nm as dong
    from app.complex c
    join app.dataset_snapshot s on s.snapshot_id = c.snapshot_id
    join app.trade_sale t on t.apt_seq = c.apt_seq
    join app.trade_batch b on b.batch_id = t.batch_id
    where s.is_active and b.kind = 'sale' and b.is_active
      and t.sgg_cd is not null and t.umd_nm is not null
"""

with psycopg.connect(database_url()) as connection:
    complexes = pd.DataFrame(connection.execute(COMPLEX_QUERY).fetchall(),
                             columns=["apt_seq", "name", "total_households"])
    mapping = pd.DataFrame(connection.execute(MAPPING_QUERY).fetchall(),
                           columns=["apt_seq", "dong"])

complexes["total_households"] = pd.to_numeric(complexes["total_households"], errors="coerce")
print("===== 1. 단지 적재 완료 =====")
print(f"  단지 {len(complexes):,}개, 세대수 합계 {complexes['total_households'].sum():,.0f}")
print(f"  세대수 결측 단지 {complexes['total_households'].isna().sum():,}개")


# ============================================================================
# 2. 커버리지
# ============================================================================

# 한 단지가 여러 동에 걸리면(구 코드 불일치 등) 세대수를 나눠 세지 않고 매핑 실패로 보지도 않는다.
# 커버리지 질문은 "동을 붙일 수 있는가"이므로 하나라도 붙으면 성공으로 센다
mapped_ids = set(mapping["apt_seq"])
complexes["mapped"] = complexes["apt_seq"].isin(mapped_ids)
multi = mapping.groupby("apt_seq").size()

households = complexes["total_households"].fillna(0)
total_hh = households.sum()
mapped_hh = households[complexes["mapped"]].sum()
coverage_hh = mapped_hh / total_hh
coverage_n = complexes["mapped"].mean()

print("\n===== 2. 동 매핑 커버리지 =====")
print(f"  단지 수 기준 {coverage_n:.1%} ({complexes['mapped'].sum():,}/{len(complexes):,})")
print(f"  세대수 기준 {coverage_hh:.1%} ({mapped_hh:,.0f}/{total_hh:,.0f})")
print(f"  두 개 이상 동에 걸린 단지 {(multi > 1).sum():,}개")

missing = complexes[~complexes["mapped"]]
print(f"\n  매핑 안 된 단지 {len(missing):,}개, 세대수 {missing['total_households'].sum():,.0f}")
if len(missing):
    print("  세대수 큰 순 5개:")
    for _, row in missing.nlargest(5, "total_households").iterrows():
        print(f"    {row['name']} ({row['total_households']:,.0f}세대)")


# ============================================================================
# 3. 판정
# ============================================================================

verdict = "재고(세대수)가중" if coverage_hh >= COVERAGE_THRESHOLD else "거래가중"
print("\n===== 3. 판정 =====")
print(f"  문턱 {COVERAGE_THRESHOLD:.0%}, 실측 {coverage_hh:.1%} → μ 가중 방식: {verdict}")
print("  이 수치와 판정을 docs/decisions.md에 남긴다")
