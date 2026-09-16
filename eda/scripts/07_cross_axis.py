"""7번 축: 복합/교차 - 정비사업 진행 동 vs 일반 동의 가격 변동성 비교.

dong_feature의 정비사업 이벤트 수(rz_events_4q)를 기준으로 동을
"정비사업 진행" / "일반"으로 나누고, dong_index 분기 변화율의
표준편차(변동성)를 비교한다.

정비사업 강도(그 동에서 정비사업이 차지하는 비중)는 "정비구역 계획상 세대수
(아파트·빌라 등 모든 주택 유형 포함) ÷ 그 동의 전체 세대수"로 계산한다. 전체
세대수는 10번 축에서 받아온 행정안전부 주민등록 인구·세대현황(hh_cnt, 모든
주택 유형 포함)을 쓴다 — 분자·분모의 대상 범위(모든 주택 유형)를 맞춰야
비율이 뜻하는 바가 정확해진다. 이 세대수는 2026년 6월 한 시점 값이라, 분석
기간(2011~2026년) 내내 고정값으로 적용한다는 한계가 있다.
"""
import pandas as pd
from scipy import stats

from _db import query_df

pd.set_option("display.width", 120)

feat = query_df("""
    select f.dong, f.as_of_quarter, f.rz_events_4q, f.rz_active_households
    from app.dong_feature f
    join app.dataset_snapshot ds on ds.snapshot_id = f.snapshot_id
    where ds.is_active and f.rz_events_4q is not null;
""")

idx = query_df("""
    select di.dong, di.quarter, di.log_index, di.eligible
    from app.dong_index di
    join app.dataset_snapshot ds on ds.snapshot_id = di.snapshot_id
    where ds.is_active
    order by di.dong, di.quarter;
""")


def quarter_to_int(q):
    y, qq = int(q[:4]), int(q[5])
    return y * 4 + qq


idx["q_int"] = idx["quarter"].apply(quarter_to_int)
idx = idx.sort_values(["dong", "q_int"])
idx["prev_q_int"] = idx.groupby("dong")["q_int"].shift(1)
idx["prev_log_index"] = idx.groupby("dong")["log_index"].shift(1)
idx["prev_eligible"] = idx.groupby("dong")["eligible"].shift(1)
is_consecutive = idx["q_int"] - idx["prev_q_int"] == 1
idx["qoq_change"] = (idx["log_index"] - idx["prev_log_index"]).where(is_consecutive)
# 두 분기(현재·직전) 모두 eligible일 때만 변화량을 신뢰한다
both_eligible = idx["eligible"].astype(bool) & idx["prev_eligible"].fillna(False).astype(bool)
idx.loc[~both_eligible, "qoq_change"] = pd.NA

# 동별로 관측기간 중 정비사업 이벤트가 한 번이라도 있었는지
redevelop_dongs = set(feat.loc[feat["rz_events_4q"] > 0, "dong"].unique())
idx["is_redevelop_dong"] = idx["dong"].isin(redevelop_dongs)

vol = idx.dropna(subset=["qoq_change"]).groupby("is_redevelop_dong")["qoq_change"].agg(
    n="size", std="std", mean="mean"
)
vol.index = vol.index.map({True: "정비사업 진행 동", False: "일반 동"})
print(f"정비사업 진행 동 수: {len(redevelop_dongs)} / 전체 {idx['dong'].nunique()}")
print("\n=== 정비사업 진행 여부별 분기 변화율 평균·변동성(표준편차) ===")
print(vol.round(4).to_string())
vol.to_csv("../output/07_redevelop_volatility.csv")

# 정비사업 강도(정비구역 계획 세대수 / 그 동 전체 세대수)와 가격 변동성의 연관성
# ("이후" 변동성이 아니라 관측기간 전체 강도 최댓값 vs 전체기간 변동성의 단순 연관성 — 시차 없음)
rz_by_dong = feat.groupby("dong")["rz_active_households"].max()
pop = pd.read_csv("../output/11_population_dong_monthly.csv")
hh_total = pop[pop["stats_ym"] == 202606].groupby("dong")["hh_cnt"].sum().rename("hh_total")

vol_by_dong = idx.dropna(subset=["qoq_change"]).groupby("dong")["qoq_change"].std()
joined = pd.concat([rz_by_dong, hh_total, vol_by_dong.rename("volatility")], axis=1).dropna()
joined["redevelop_intensity"] = (joined["rz_active_households"] / joined["hh_total"]).astype(float)
joined["volatility"] = joined["volatility"].astype(float)
joined["intensity_over_1"] = joined["redevelop_intensity"] > 1

corr_all = joined["redevelop_intensity"].corr(joined["volatility"])
normal = joined[~joined["intensity_over_1"]]
corr_normal = normal["redevelop_intensity"].corr(normal["volatility"])
_, p_all = stats.pearsonr(joined["redevelop_intensity"], joined["volatility"])
_, p_normal = stats.pearsonr(normal["redevelop_intensity"], normal["volatility"])

print(f"\n정비사업 강도 > 1인 동(정비구역 세대수가 전체 세대수보다 많음, 재건축 후기 단계로 "
      f"실거주 세대가 줄었을 가능성): {joined['intensity_over_1'].sum()}개 / {len(joined)}개, "
      f"최댓값 {joined['redevelop_intensity'].max():.2f} ({joined['redevelop_intensity'].idxmax()})")
print(f"전체(n={len(joined)}) 상관계수: {corr_all:.3f} (p={p_all:.3f})")
print(f"강도<=1만(n={len(normal)}) 상관계수: {corr_normal:.3f} (p={p_normal:.3f})")
joined.to_csv("../output/07_redevelop_intensity_vs_volatility.csv")

print("\nCSV 저장 완료: eda/output/07_redevelop_volatility.csv, 07_redevelop_intensity_vs_volatility.csv")
