"""3번 축: 단지 속성(준공년도·세대수·용적률·정비사업 단계)이 매매가에 주는 영향.

최근 2년(2024~2026) 실거래를 active snapshot의 단지 정보와 apt_seq로 묶어서 본다.
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

sale = query_df("""
    select apt_seq, deal_year, exclu_use_ar, deal_amount_manwon
    from app.trade_sale
    where is_cancelled = false
      and deal_amount_manwon is not null
      and exclu_use_ar > 0
      and deal_year >= 2024
      and apt_seq is not null;
""")
sale["price_per_m2"] = sale["deal_amount_manwon"] / sale["exclu_use_ar"]

complex_df = query_df("""
    select c.apt_seq, c.built_year, c.total_households, c.far, c.bcr,
           c.parking_per_hh, c.redevelop_stage
    from app.complex c
    join app.dataset_snapshot ds on ds.snapshot_id = c.snapshot_id
    where ds.is_active;
""")

merged = sale.merge(complex_df, on="apt_seq", how="inner")
print(f"매칭된 거래 {len(merged)}건 / 전체 실거래 {len(sale)}건 (매칭률 {len(merged) / len(sale) * 100:.1f}%)")

merged["age"] = merged["deal_year"] - merged["built_year"]
merged = merged[(merged["age"] >= 0) & (merged["age"] <= 60)]

# --- 준공연차와 단가 ---
age_bin = pd.cut(merged["age"], bins=[0, 5, 10, 20, 30, 40, 60], right=False)
age_summary = merged.groupby(age_bin, observed=True)["price_per_m2"].agg(n="size", median="median", mean="mean")
print("\n=== 준공연차 구간별 ㎡당 단가(만원) ===")
print(age_summary.round(0).to_string())
age_summary.to_csv("../output/03_age_price.csv")

# --- 세대수, 용적률, 주차대수와 단가의 상관관계 ---
corr_cols = ["price_per_m2", "age", "total_households", "far", "bcr", "parking_per_hh"]
corr = merged[corr_cols].corr(numeric_only=True)["price_per_m2"].drop("price_per_m2").sort_values(key=abs, ascending=False)
print("\n=== 단지 속성과 ㎡당 단가의 상관계수(Pearson) ===")
print(corr.round(3).to_string())
corr.to_csv("../output/03_attr_correlation.csv")

# --- 정비사업 단계별 단가 프리미엄 (일반 단지 대비) ---
merged["stage"] = merged["redevelop_stage"].fillna("해당없음")
stage_summary = merged.groupby("stage")["price_per_m2"].agg(n="size", median="median", mean="mean").sort_values("median", ascending=False)
baseline = stage_summary.loc["해당없음", "median"]
stage_summary["premium_vs_none_pct"] = (stage_summary["median"] / baseline - 1) * 100
print("\n=== 정비사업 단계별 ㎡당 단가 및 일반 단지 대비 프리미엄(%) ===")
print(stage_summary.round(1).to_string())
stage_summary.to_csv("../output/03_redevelop_stage_price.csv")

print("\nCSV 저장 완료: eda/output/03_age_price.csv, 03_attr_correlation.csv, 03_redevelop_stage_price.csv")
