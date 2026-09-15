"""1번 축: 시간 흐름에 따른 매매 실거래 거래량·가격 추이.

- 분기별 거래량, 중앙값/평균 ㎡당 단가
- market_event(규제 지정·해제 등) 전후 비교
- 거래량과 가격의 선행/후행 관계(연간 증감률 비교)
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

# 취소 거래는 제외 (docs/decisions.md 결정 5 기준과 동일하게)
sale = query_df("""
    select deal_year, deal_month, exclu_use_ar, deal_amount_manwon, gu
    from app.trade_sale
    where is_cancelled = false
      and deal_amount_manwon is not null
      and exclu_use_ar > 0;
""")
sale["price_per_m2"] = sale["deal_amount_manwon"] / sale["exclu_use_ar"]
sale["quarter"] = sale["deal_year"].astype(str) + "Q" + (((sale["deal_month"] - 1) // 3) + 1).astype(str)
sale["yq_sort"] = sale["deal_year"] * 10 + ((sale["deal_month"] - 1) // 3 + 1)

quarterly = (
    sale.groupby(["yq_sort", "quarter"])
    .agg(n_trades=("price_per_m2", "size"),
         median_price_per_m2=("price_per_m2", "median"),
         mean_price_per_m2=("price_per_m2", "mean"))
    .reset_index()
    .sort_values("yq_sort")
)

print("=== 분기별 거래량 & ㎡당 단가(만원) ===")
print(quarterly.tail(20).to_string(index=False))

quarterly.to_csv("../output/01_quarterly_trend.csv", index=False)

# 연간 증감률: 거래량 vs 가격
yearly = sale.groupby("deal_year").agg(
    n_trades=("price_per_m2", "size"),
    median_price_per_m2=("price_per_m2", "median"),
)
yearly["volume_yoy_pct"] = yearly["n_trades"].pct_change() * 100
yearly["price_yoy_pct"] = yearly["median_price_per_m2"].pct_change() * 100

print("\n=== 연간 거래량·가격 증감률(%) ===")
print(yearly.round(1).to_string())

yearly.to_csv("../output/01_yearly_yoy.csv")

# market_event 목록 (규제 지정/해제 등)
events = query_df("""
    select event_id, effective_date, category, direction, label, verified
    from app.market_event
    order by effective_date;
""")
print(f"\n=== market_event 목록 ({len(events)}건) ===")
print(events.to_string(index=False))

events.to_csv("../output/01_market_events.csv", index=False)

print("\nCSV 저장 완료: eda/output/01_quarterly_trend.csv, 01_yearly_yoy.csv, 01_market_events.csv")
