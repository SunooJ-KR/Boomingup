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
      and deal_amount_manwon > 0
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
# 데이터가 최신 연도 8월까지만 있어(2026), 그해 "연간" 합계를 이전 해 "연간" 합계와 그대로
# 나누면 12개월 대 8개월 비교가 된다(2026-09-16 codex 검증에서 지적됨). 완결 연도만 pct_change로
# 비교하고, 최신 연도는 "같은 개월수(1~last_month월)" 비교를 별도로 만든다.
yearly = sale.groupby("deal_year").agg(
    n_trades=("price_per_m2", "size"),
    median_price_per_m2=("price_per_m2", "median"),
)
last_year = sale["deal_year"].max()
last_month = sale.loc[sale["deal_year"] == last_year, "deal_month"].max()
yearly["is_complete_year"] = yearly.index < last_year
yearly.loc[yearly["is_complete_year"], "volume_yoy_pct"] = (
    yearly.loc[yearly["is_complete_year"], "n_trades"].pct_change() * 100
)
yearly.loc[yearly["is_complete_year"], "price_yoy_pct"] = (
    yearly.loc[yearly["is_complete_year"], "median_price_per_m2"].pct_change() * 100
)

print(f"\n=== 연간 거래량·가격 증감률(%) — {last_year}년은 {last_month}월까지만 있어 incomplete로 표시, "
      f"pct_change 계산에서 제외 ===")
print(yearly.round(1).to_string())

# 최신 연도는 같은 개월수(1~last_month월)로 전년과 비교한 별도 지표를 만든다
comparable = sale[sale["deal_month"] <= last_month].groupby("deal_year").agg(
    n_trades=("price_per_m2", "size"), median_price_per_m2=("price_per_m2", "median"),
)
comparable["volume_yoy_pct_comparable"] = comparable["n_trades"].pct_change() * 100
comparable["price_yoy_pct_comparable"] = comparable["median_price_per_m2"].pct_change() * 100
print(f"\n=== {last_year}년 비교를 위한 '1~{last_month}월만' 동일 개월수 비교 ===")
print(comparable.tail(3).round(1).to_string())
comparable.to_csv("../output/01_yearly_yoy_comparable_months.csv")

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
