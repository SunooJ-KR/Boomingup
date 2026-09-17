# ============================================================================
# 64.measure_mu_weight.py
# ============================================================================
# Author:      yjkim
# Purpose:     μ(서울 공통 변화)의 가중 방식을 정하려고 세대수의 동 매핑 커버리지를 잰다
# Description: 계획 docs/model-develope-plan.md §1 선행 조건, 진행 P0-4.
#              재고(세대수)가중을 쓰려면 단지 세대수가 동에 붙어야 한다. 붙이는 길은 둘이다.
#                (1) 매매 기록의 (sgg_cd, umd_nm) — 매매가 한 번도 없던 단지는 못 붙는다
#                (2) `complex.bjd_code` + `apt_seq` 앞자리(구 코드) — 매매가 없어도 붙는다
#              (2)의 `bjd_code`는 국토부 API의 `umdCd`와 같은 5자리 법정동 하위코드다.
#              매매가 있는 단지로 (구, bjd_code) → 동 사전을 만들면 매매가 없는 단지에도
#              같은 사전을 쓸 수 있다. 사전이 1:1인지는 이 스크립트가 함께 확인한다.
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
# 1. 단지와 매매로 붙는 동
# ============================================================================

COMPLEX_QUERY = """
    select c.apt_seq, c.name, c.total_households, c.bjd_code,
           split_part(c.apt_seq, '-', 1) as gu_cd
    from app.complex c
    join app.dataset_snapshot s on s.snapshot_id = c.snapshot_id
    where s.is_active
"""

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
                             columns=["apt_seq", "name", "total_households", "bjd_code", "gu_cd"])
    mapping = pd.DataFrame(connection.execute(MAPPING_QUERY).fetchall(),
                           columns=["apt_seq", "dong"])

complexes["total_households"] = pd.to_numeric(complexes["total_households"], errors="coerce")
print("===== 1. 단지 적재 완료 =====")
print(f"  단지 {len(complexes):,}개, 세대수 합계 {complexes['total_households'].sum():,.0f}")
print(f"  세대수 결측 단지 {complexes['total_households'].isna().sum():,}개")
print(f"  bjd_code 있는 단지 {complexes['bjd_code'].notna().sum():,}개")


# ============================================================================
# 2. 경로 1 — 매매 기록
# ============================================================================

# 한 단지가 여러 동에 걸리면(구 코드 불일치 등) 세대수를 나눠 세지 않고 매핑 실패로 보지도 않는다.
# 커버리지 질문은 "동을 붙일 수 있는가"이므로 하나라도 붙으면 성공으로 센다
complexes["by_trade"] = complexes["apt_seq"].isin(set(mapping["apt_seq"]))
multi = mapping.groupby("apt_seq").size()


# ============================================================================
# 3. 경로 2 — (구, bjd_code) 사전
# ============================================================================

single = mapping.drop_duplicates("apt_seq")
known = complexes[complexes["by_trade"] & complexes["bjd_code"].notna()].merge(single, on="apt_seq")
per_code = known.groupby(["gu_cd", "bjd_code"])["dong"].nunique()

print("\n===== 2. (구, bjd_code) → 동 사전 =====")
print(f"  사전 항목 {len(per_code):,}개, 매매로 확인된 동 {known['dong'].nunique():,}개")
conflicts = per_code[per_code > 1]
print(f"  같은 (구, bjd_code)가 두 동을 가리키는 경우 {len(conflicts)}건")
for (gu_cd, bjd_code), _ in conflicts.items():
    names = sorted(known.loc[(known["gu_cd"] == gu_cd) & (known["bjd_code"] == bjd_code), "dong"].unique())
    print(f"    {gu_cd}-{bjd_code}: {', '.join(names)}")

# 충돌은 원장의 구 코드 불일치 동(`docs/data-and-schema.md` §2.3)에서 나온다. 매매 31건짜리
# 문제라 사전을 버릴 이유는 아니지만, 충돌이 늘면 코드 체계가 바뀐 것이므로 멈춘다
if len(conflicts) > 0.01 * len(per_code):
    raise SystemExit("사전 충돌이 1%를 넘는다. bjd_code로 동을 붙이면 안 된다")

# 충돌한 코드는 매매가 많은 쪽 동을 쓴다
vote = known.groupby(["gu_cd", "bjd_code", "dong"]).size().rename("n").reset_index()
dictionary = (vote.sort_values("n", ascending=False)
              .drop_duplicates(["gu_cd", "bjd_code"])
              .set_index(["gu_cd", "bjd_code"])["dong"])
codes = pd.MultiIndex.from_frame(complexes[["gu_cd", "bjd_code"]])
complexes["by_code"] = codes.isin(dictionary.index)
complexes["mapped"] = complexes["by_trade"] | complexes["by_code"]


# ============================================================================
# 4. 커버리지
# ============================================================================

households = complexes["total_households"].fillna(0)
total_hh = households.sum()
coverage_hh = households[complexes["mapped"]].sum() / total_hh
coverage_n = complexes["mapped"].mean()

print("\n===== 3. 동 매핑 커버리지 =====")
print(f"  단지 수 기준 {coverage_n:.1%} ({complexes['mapped'].sum():,}/{len(complexes):,})")
print(f"  세대수 기준 {coverage_hh:.1%} ({households[complexes['mapped']].sum():,.0f}/{total_hh:,.0f})")
print(f"  두 개 이상 동에 걸린 단지 {(multi > 1).sum():,}개")

added = complexes["by_code"] & ~complexes["by_trade"]
print(f"\n  경로별: 매매로 {households[complexes['by_trade']].sum() / total_hh:.1%}, "
      f"bjd_code가 더 붙인 몫 {households[added].sum() / total_hh:.1%} (단지 {int(added.sum()):,}개)")

missing = complexes[~complexes["mapped"]]
print(f"\n  끝까지 안 붙은 단지 {len(missing):,}개, 세대수 {missing['total_households'].sum():,.0f}")
if len(missing):
    print(f"    그중 bjd_code 없음 {int(missing['bjd_code'].isna().sum()):,}개")
    print("    세대수 큰 순 5개:")
    for _, row in missing.nlargest(5, "total_households").iterrows():
        print(f"      {row['name']} ({row['total_households']:,.0f}세대)")


# ============================================================================
# 5. 판정
# ============================================================================

verdict = "재고(세대수)가중" if coverage_hh >= COVERAGE_THRESHOLD else "거래가중"
print("\n===== 4. 판정 =====")
print(f"  문턱 {COVERAGE_THRESHOLD:.0%}, 실측 {coverage_hh:.1%} → μ 가중 방식: {verdict}")
print("  이 수치와 판정을 docs/decisions.md에 남긴다")
