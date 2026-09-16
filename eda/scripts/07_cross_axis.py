"""7번 축: 복합/교차 - 정비사업 진행 동 vs 일반 동의 가격 변동성 비교.

dong_feature의 정비사업 이벤트 수(rz_events_4q)를 기준으로 동을
"정비사업 진행" / "일반"으로 나누고, dong_index 분기 변화율의
표준편차(변동성)를 비교한다.

v2 (2026-09-16 codex 검증 후 수정)
① eligible=true인 행만 먼저 가져와 diff()를 하면, 중간 분기가 부적격으로 빠졌을 때
   2개 분기 이상 차이를 1분기 변화로 계산하는 오류가 있었다. 이제 분기가 실제로 연속인
   행끼리만 diff를 계산한다(quarter를 정수로 바꿔 이전 행과 차이가 1인지 검증).
② redevelop_intensity(rz_active_households/stock_hh)가 273개 동 중 19개에서 1을
   초과했다(최댓값 9.46, 보광동). "재고 대비 진행 세대 비중"이 100%를 넘는 건 분모(stock_hh)
   커버리지가 불완전하거나 두 집계 범위가 다르기 때문으로 보이며 우리 쪽에서 고칠 수 있는
   값이 아니다. 대신 intensity<=1(정상 범위)만 남긴 결과를 함께 보고한다.
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

feat = query_df("""
    select dong, as_of_quarter, rz_events_4q, rz_active_households, stock_hh
    from app.dong_feature
    where rz_events_4q is not null;
""")

idx = query_df("""
    select dong, quarter, log_index, eligible
    from app.dong_index
    order by dong, quarter;
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

# 정비사업 진행 강도(rz_active_households / stock_hh)와 가격 변동성의 연관성
# ("이후" 변동성이 아니라 관측기간 전체 강도 최댓값 vs 전체기간 변동성의 단순 연관성 — 시차 없음)
feat["redevelop_intensity"] = feat["rz_active_households"] / feat["stock_hh"].replace(0, pd.NA)
intensity_by_dong = feat.groupby("dong")["redevelop_intensity"].max()
vol_by_dong = idx.dropna(subset=["qoq_change"]).groupby("dong")["qoq_change"].std()
joined = pd.concat([intensity_by_dong, vol_by_dong.rename("volatility")], axis=1).dropna()
joined["redevelop_intensity"] = joined["redevelop_intensity"].astype(float)
joined["volatility"] = joined["volatility"].astype(float)
joined["intensity_over_1"] = joined["redevelop_intensity"] > 1

corr_all = joined["redevelop_intensity"].corr(joined["volatility"])
normal = joined[~joined["intensity_over_1"]]
corr_normal = normal["redevelop_intensity"].corr(normal["volatility"])
from scipy import stats
_, p_all = stats.pearsonr(joined["redevelop_intensity"], joined["volatility"])
_, p_normal = stats.pearsonr(normal["redevelop_intensity"], normal["volatility"])

print(f"\n정비사업 강도 > 1인 동(분모 이상 의심): {joined['intensity_over_1'].sum()}개 / {len(joined)}개, "
      f"최댓값 {joined['redevelop_intensity'].max():.2f} ({joined['redevelop_intensity'].idxmax()})")
print(f"전체(n={len(joined)}) 상관계수: {corr_all:.3f} (p={p_all:.3f})")
print(f"강도<=1만(n={len(normal)}) 상관계수: {corr_normal:.3f} (p={p_normal:.3f})")
joined.to_csv("../output/07_redevelop_intensity_vs_volatility.csv")

print("\nCSV 저장 완료: eda/output/07_redevelop_volatility.csv, 07_redevelop_intensity_vs_volatility.csv")
