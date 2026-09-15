"""2번 축: 지역에 따른 매매가 차이.

- 자치구별 ㎡당 단가 수준과 최근 3년 추이
- dong_index(hedonic 지수) 기준 최근 1년 상승률 상위/하위 동
- 강남3구 vs 비강남3구 가격 수준·변동성 비교
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

GANGNAM3 = {"강남구", "서초구", "송파구"}

# --- 구별 최근 3년 단가 수준 ---
sale = query_df("""
    select deal_year, gu, exclu_use_ar, deal_amount_manwon
    from app.trade_sale
    where is_cancelled = false
      and deal_amount_manwon is not null
      and exclu_use_ar > 0
      and deal_year >= 2023;
""")
sale["price_per_m2"] = sale["deal_amount_manwon"] / sale["exclu_use_ar"]

gu_year = (
    sale.groupby(["gu", "deal_year"])
    .agg(n_trades=("price_per_m2", "size"), median_price_per_m2=("price_per_m2", "median"))
    .reset_index()
)
gu_pivot = gu_year.pivot(index="gu", columns="deal_year", values="median_price_per_m2").round(0)
gu_pivot["gangnam3"] = gu_pivot.index.isin(GANGNAM3)
gu_pivot = gu_pivot.sort_values(2026, ascending=False)

print("=== 자치구별 연도별 중앙값 ㎡당 단가(만원), 2023~2026 ===")
print(gu_pivot.to_string())
gu_pivot.to_csv("../output/02_gu_yearly_price.csv")

# --- 강남3구 vs 비강남3구: 수준과 변동성(표준편차) ---
sale["is_gangnam3"] = sale["gu"].isin(GANGNAM3)
grp = sale.groupby("is_gangnam3")["price_per_m2"].agg(
    n="size", median="median", mean="mean", std="std", cv=lambda x: x.std() / x.mean()
)
grp.index = grp.index.map({True: "강남3구", False: "비강남3구"})
print("\n=== 강남3구 vs 비강남3구 가격 수준·변동성 (2023~2026 전체) ===")
print(grp.round(2).to_string())
grp.to_csv("../output/02_gangnam_vs_rest.csv")

# --- dong_index 기준 최근 1년 상승률 상위/하위 동 ---
di = query_df("""
    select di.dong, d.gu_name, di.quarter, di.log_index, di.n_sales_4q, di.eligible
    from app.dong_index di
    join app.dong d on d.dong = di.dong
    where di.quarter in ('2025Q2', '2026Q2');
""")
wide = di.pivot(index=["dong", "gu_name"], columns="quarter", values=["log_index", "eligible"])
wide.columns = ["_".join(c) for c in wide.columns]
wide = wide.dropna(subset=["log_index_2025Q2", "log_index_2026Q2"])
wide["yoy_change_pct"] = (wide["log_index_2026Q2"] - wide["log_index_2025Q2"]) * 100
wide["both_eligible"] = wide["eligible_2025Q2"] & wide["eligible_2026Q2"]

eligible_wide = wide[wide["both_eligible"]].sort_values("yoy_change_pct", ascending=False)
print(f"\n=== dong_index 2025Q2→2026Q2 상승률 상위 10개 동 (표본기준 통과, {len(eligible_wide)}개 동 중) ===")
print(eligible_wide.head(10)[["yoy_change_pct"]].reset_index().to_string(index=False))

print("\n=== 하위 10개 동 ===")
print(eligible_wide.tail(10)[["yoy_change_pct"]].reset_index().to_string(index=False))

eligible_wide.reset_index().to_csv("../output/02_dong_yoy_ranked.csv", index=False)

print("\n제외된(표본 부족) 동 수:", len(wide) - len(eligible_wide), "/", len(wide))
print("CSV 저장 완료: eda/output/02_gu_yearly_price.csv, 02_gangnam_vs_rest.csv, 02_dong_yoy_ranked.csv")
