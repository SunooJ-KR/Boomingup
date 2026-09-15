"""6번 축: 전세가율이 이후 매매가 상승을 선행하는지.

dong_feature의 기점 분기 전세가율(jeonse_ratio_4q)과 dong_index의
이후 h=4분기(1년) 뒤 log 변화율의 상관을 본다.
"""
import pandas as pd

from _db import query_df

pd.set_option("display.width", 120)

feat = query_df("""
    select dong, as_of_quarter, jeonse_ratio_4q, sale_n_all_4q
    from app.dong_feature
    where jeonse_ratio_4q is not null;
""")

idx = query_df("""
    select dong, quarter, log_index, eligible
    from app.dong_index
    where eligible = true;
""")

def add_quarters(q, n):
    y, qq = int(q[:4]), int(q[5])
    total = y * 4 + (qq - 1) + n
    return f"{total // 4}Q{total % 4 + 1}"

feat["future_quarter"] = feat["as_of_quarter"].apply(lambda q: add_quarters(q, 4))

idx_now = idx.rename(columns={"quarter": "as_of_quarter", "log_index": "log_index_now"})
idx_future = idx.rename(columns={"quarter": "future_quarter", "log_index": "log_index_future"})

m = feat.merge(idx_now[["dong", "as_of_quarter", "log_index_now"]], on=["dong", "as_of_quarter"], how="inner")
m = m.merge(idx_future[["dong", "future_quarter", "log_index_future"]], on=["dong", "future_quarter"], how="inner")
m["future_change_1y"] = m["log_index_future"] - m["log_index_now"]

# 최소 표본 조건 (기점 직전 4분기 거래 20건 이상, docs/decisions.md 결정 7과 동일)
m = m[m["sale_n_all_4q"] >= 20]

print(f"분석 대상 행 수: {len(m)} (동x기점 조합)")

corr = m[["jeonse_ratio_4q", "future_change_1y"]].corr().iloc[0, 1]
print(f"\n전세가율(기점) vs 1년 뒤 매매지수 변화의 상관계수: {corr:.3f}")

# 전세가율 5분위별 이후 1년 변화율
m["jeonse_bin"] = pd.qcut(m["jeonse_ratio_4q"], 5, labels=["Q1(낮음)", "Q2", "Q3", "Q4", "Q5(높음)"])
bin_summary = m.groupby("jeonse_bin", observed=True)["future_change_1y"].agg(n="size", median="median", mean="mean")
bin_summary["mean_pct"] = bin_summary["mean"] * 100
print("\n=== 전세가율 5분위별 1년 뒤 매매지수 변화(log, %) ===")
print(bin_summary.round(4).to_string())
bin_summary.to_csv("../output/06_jeonse_ratio_vs_future_change.csv")

print("\nCSV 저장 완료: eda/output/06_jeonse_ratio_vs_future_change.csv")
