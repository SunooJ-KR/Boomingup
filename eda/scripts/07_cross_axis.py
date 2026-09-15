"""7번 축: 복합/교차 - 정비사업 진행 동 vs 일반 동의 가격 변동성 비교.

dong_feature의 정비사업 이벤트 수(rz_events_4q)를 기준으로 동을
"정비사업 진행" / "일반"으로 나누고, dong_index 분기 변화율의
표준편차(변동성)를 비교한다.
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
    select dong, quarter, log_index
    from app.dong_index
    where eligible = true
    order by dong, quarter;
""")
idx["qoq_change"] = idx.groupby("dong")["log_index"].diff()

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

# 정비사업 진행 강도(rz_active_households / stock_hh)와 이후 변동성 상관
feat["redevelop_intensity"] = feat["rz_active_households"] / feat["stock_hh"].replace(0, pd.NA)
intensity_by_dong = feat.groupby("dong")["redevelop_intensity"].max()
vol_by_dong = idx.dropna(subset=["qoq_change"]).groupby("dong")["qoq_change"].std()
joined = pd.concat([intensity_by_dong, vol_by_dong.rename("volatility")], axis=1).dropna()
corr = joined.corr().iloc[0, 1]
print(f"\n정비사업 강도(진행 세대 비중) vs 가격 변동성 상관계수: {corr:.3f} (n={len(joined)})")
joined.to_csv("../output/07_redevelop_intensity_vs_volatility.csv")

print("\nCSV 저장 완료: eda/output/07_redevelop_volatility.csv, 07_redevelop_intensity_vs_volatility.csv")
