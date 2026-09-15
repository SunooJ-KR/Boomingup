"""5번 축: 매물 속성(면적·층)이 매매가에 주는 영향 + 취소거래 비율 추이.

trade_sale 자체 필드만 사용한다 (조인 불필요).
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

sale = query_df("""
    select deal_year, deal_month, exclu_use_ar, floor, deal_amount_manwon, is_cancelled
    from app.trade_sale
    where deal_amount_manwon is not null and exclu_use_ar > 0;
""")

# --- 취소 거래 비율 추이 (전체 포함, 취소 제외 안함) ---
cancel_rate = sale.groupby("deal_year")["is_cancelled"].mean() * 100
print("=== 연도별 거래 취소율(%) ===")
print(cancel_rate.round(2).to_string())
cancel_rate.to_csv("../output/05_cancel_rate_by_year.csv")

# 이후 분석은 취소 제외
s = sale[~sale["is_cancelled"]].copy()
s["price_per_m2"] = s["deal_amount_manwon"] / s["exclu_use_ar"]

# --- 면적대별 단가 (국평 vs 소형 프리미엄) ---
area_bin = pd.cut(s["exclu_use_ar"], bins=[0, 40, 60, 85, 102, 135, 165, 1000], right=False,
                   labels=["~40㎡", "40-60㎡", "60-85㎡(국평이하)", "85-102㎡(국평)", "102-135㎡", "135-165㎡", "165㎡+"])
area_summary = s.groupby(area_bin, observed=True)["price_per_m2"].agg(n="size", median="median", mean="mean")
print("\n=== 면적대별 ㎡당 단가(만원) ===")
print(area_summary.round(0).to_string())
area_summary.to_csv("../output/05_area_price.csv")

# --- 층대별 단가 ---
floor_bin = pd.cut(s["floor"], bins=[-100, 1, 3, 5, 10, 15, 20, 200], right=True,
                    labels=["지하/1층", "2-3층", "4-5층", "6-10층", "11-15층", "16-20층", "21층+"])
floor_summary = s.groupby(floor_bin, observed=True)["price_per_m2"].agg(n="size", median="median")
print("\n=== 층대별 ㎡당 단가(만원) ===")
print(floor_summary.round(0).to_string())
floor_summary.to_csv("../output/05_floor_price.csv")

print("\nCSV 저장 완료: eda/output/05_cancel_rate_by_year.csv, 05_area_price.csv, 05_floor_price.csv")
