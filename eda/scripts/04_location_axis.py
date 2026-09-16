"""4번 축: 입지(역 거리·학군·조망·일조)가 매매가에 주는 영향.

최근 2년(2024~2026) 실거래를 active snapshot의 complex_metrics와 apt_seq로 묶어서 본다.
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

sale = query_df("""
    select apt_seq, exclu_use_ar, deal_amount_manwon
    from app.trade_sale
    where is_cancelled = false
      and deal_amount_manwon > 0
      and exclu_use_ar > 0
      and deal_year >= 2024
      and apt_seq is not null;
""")
sale["price_per_m2"] = sale["deal_amount_manwon"] / sale["exclu_use_ar"]

metrics = query_df("""
    select cm.apt_seq, cm.station_dist_m, cm.station_walk_min_est,
           cm.elem_school_m, cm.mid_school_m, cm.high_school_m,
           cm.sun_hours_avg, cm.river_view_ratio, cm.park_m
    from app.complex_metrics cm
    join app.dataset_snapshot ds on ds.snapshot_id = cm.snapshot_id
    where ds.is_active;
""")

merged = sale.merge(metrics, on="apt_seq", how="inner")
print(f"매칭된 거래 {len(merged)}건 / 전체 실거래 {len(sale)}건 (매칭률 {len(merged) / len(sale) * 100:.1f}%)")

# --- 역까지 거리 구간별 단가 ---
station_bin = pd.cut(merged["station_dist_m"], bins=[0, 300, 500, 800, 1200, 2000, 100000], right=False,
                      labels=["<300m", "300-500m", "500-800m", "800-1200m", "1200-2000m", "2000m+"])
st_summary = merged.groupby(station_bin, observed=True)["price_per_m2"].agg(n="size", median="median")
print("\n=== 역까지 거리 구간별 ㎡당 단가(만원) ===")
print(st_summary.round(0).to_string())
st_summary.to_csv("../output/04_station_dist_price.csv")

# --- 초등학교 거리 구간별 단가 ---
elem_bin = pd.cut(merged["elem_school_m"], bins=[0, 300, 500, 800, 1200, 100000], right=False,
                   labels=["<300m", "300-500m", "500-800m", "800-1200m", "1200m+"])
elem_summary = merged.groupby(elem_bin, observed=True)["price_per_m2"].agg(n="size", median="median")
print("\n=== 초등학교까지 거리 구간별 ㎡당 단가(만원) ===")
print(elem_summary.round(0).to_string())
elem_summary.to_csv("../output/04_elem_school_dist_price.csv")

# --- 한강 조망 비율과 단가 ---
merged["has_river_view"] = merged["river_view_ratio"].fillna(0) > 0
river = merged.groupby("has_river_view")["price_per_m2"].agg(n="size", median="median", mean="mean")
print("\n=== 한강 조망 세대 비율 유무별 ㎡당 단가(만원) ===")
print(river.round(0).to_string())
river.to_csv("../output/04_river_view_price.csv")

# --- 상관계수 종합 ---
corr_cols = ["price_per_m2", "station_dist_m", "elem_school_m", "mid_school_m", "high_school_m",
             "sun_hours_avg", "river_view_ratio", "park_m"]
corr = merged[corr_cols].corr(numeric_only=True)["price_per_m2"].drop("price_per_m2").sort_values(key=abs, ascending=False)
print("\n=== 입지 지표와 ㎡당 단가의 상관계수(Pearson) ===")
print(corr.round(3).to_string())
corr.to_csv("../output/04_location_correlation.csv")

print("\nCSV 저장 완료: eda/output/04_station_dist_price.csv, 04_elem_school_dist_price.csv, 04_river_view_price.csv, 04_location_correlation.csv")
