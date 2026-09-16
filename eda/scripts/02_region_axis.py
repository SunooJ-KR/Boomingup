"""2번 축: 지역에 따른 매매가 차이.

- 자치구별 ㎡당 단가 수준과 최근 3년 추이 (원시 거래 중앙값)
- dong_index(hedonic 지수) 기준 최근 1년 상승률 상위/하위 동
- 강남3구 vs 비강남3구 가격 수준·변동성 비교
- 자치구 평균 상승률(구내 eligible 동의 hedonic 변화 평균) — 동별 순위와 "같은 기준"으로 비교하기 위해 추가.
  (v2, 2026-09-16 codex 검증 후 수정: ① log 지수 차이를 그대로 %로 표기하던 오류를
  exp(diff)-1 실제 상승률로 고침 ② 구 단가(원시거래, 2023~2026년 전체)와 동 상승률(hedonic,
  25Q2→26Q2)을 서로 다른 기준으로 비교하던 문제를 고치기 위해 구 단위 hedonic 상승률을 추가)
"""
import numpy as np
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
wide["log_index_2025Q2"] = wide["log_index_2025Q2"].astype(float)
wide["log_index_2026Q2"] = wide["log_index_2026Q2"].astype(float)
wide["log_change"] = wide["log_index_2026Q2"] - wide["log_index_2025Q2"]
# log 지수 차이는 실제 %가 아니다 — exp(x)-1로 변환해야 진짜 상승률이다 (2026-09-16 수정)
wide["yoy_change_pct"] = (np.exp(wide["log_change"]) - 1) * 100
wide["both_eligible"] = wide["eligible_2025Q2"] & wide["eligible_2026Q2"]

eligible_wide = wide[wide["both_eligible"]].sort_values("yoy_change_pct", ascending=False)
print(f"\n=== dong_index 2025Q2→2026Q2 상승률 상위 10개 동 (표본기준 통과, {len(eligible_wide)}개 동 중) ===")
print(eligible_wide.head(10)[["yoy_change_pct"]].reset_index().to_string(index=False))

print("\n=== 하위 10개 동 ===")
print(eligible_wide.tail(10)[["yoy_change_pct"]].reset_index().to_string(index=False))

eligible_wide.reset_index().to_csv("../output/02_dong_yoy_ranked.csv", index=False)

print("\n제외된(표본 부족) 동 수:", len(wide) - len(eligible_wide), "/", len(wide))

# --- 자치구 평균 hedonic 상승률: 동별 순위와 "같은 기준"으로 비교하기 위한 구 단위 집계 ---
# (원시거래 중앙값 기반 gu_pivot과는 별개 지표. eligible 동의 log_change 단순평균을 구해
#  exp(mean)-1로 변환한다 — 동 하나하나와 직접 비교 가능한 숫자를 만드는 게 목적)
gu_hedonic = (
    eligible_wide.reset_index()
    .groupby("gu_name")["log_change"]
    .agg(n_dong="size", mean_log_change="mean")
    .reset_index()
)
gu_hedonic["mean_yoy_change_pct"] = (np.exp(gu_hedonic["mean_log_change"]) - 1) * 100
gu_hedonic = gu_hedonic.sort_values("mean_yoy_change_pct", ascending=False)
print("\n=== 자치구별 hedonic 평균 상승률 (2025Q2→2026Q2, eligible 동 단순평균) ===")
print(gu_hedonic.round(2).to_string(index=False))
gu_hedonic.to_csv("../output/02_gu_hedonic_change.csv", index=False)

gangnam_gu = gu_hedonic[gu_hedonic["gu_name"] == "강남구"]
gangnam_dongs = eligible_wide.reset_index()
gangnam_dongs = gangnam_dongs[gangnam_dongs["gu_name"] == "강남구"].sort_values("yoy_change_pct")
print("\n=== 강남구 평균 vs 강남구 소속 동별 상승률 (같은 hedonic 기준) ===")
print(gangnam_gu.round(2).to_string(index=False))
print(gangnam_dongs[["dong", "yoy_change_pct"]].round(2).to_string(index=False))

print("\nCSV 저장 완료: eda/output/02_gu_yearly_price.csv, 02_gangnam_vs_rest.csv, "
      "02_dong_yoy_ranked.csv, 02_gu_hedonic_change.csv")
