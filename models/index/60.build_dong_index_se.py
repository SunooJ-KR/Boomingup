# ============================================================================
# 60.build_dong_index_se.py
# ============================================================================
# Author:      yjkim
# Purpose:     동×분기 hedonic 지수를 추정오차(log_index_se)와 함께 만든다
# Description: 동 지수 추정오차 산출. 근거는 docs/decisions.md 결정 42.
#              40과 같은 추정식(_dong_index.py)을 쓰되 SE를 붙인다. SE가 없으면
#              Track 0 수축, gate 재설계, 구간 조정, 측정오차 진단이 모두 막히므로
#              재설계의 첫 산출물이다.
#
#              매매 원장은 output/11.1.trades_sale.txt가 있으면 그것을, 없으면
#              DB의 활성 sale batch를 읽는다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

from _dong_index import RIDGE_LAMBDA, estimate_hedonic_index, load_sales_any
from _dong_index_se import attach_standard_error

work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"

LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
MIN_SALES_4Q = 20


# ============================================================================
# 1. 매매 적재
# ============================================================================

sales, source = load_sales_any(work_dir)
sales = sales[sales["quarter"] <= LAST_COMPLETE_QUARTER].reset_index(drop=True)
print("===== 1. 매매 적재 완료 =====")
print(f"  원천: {source}")
print(f"  {len(sales):,}건 / 동 {sales['dong'].nunique()}개 / {sales['quarter'].min()} ~ {sales['quarter'].max()}")


# ============================================================================
# 2. hedonic 지수와 추정오차
# ============================================================================

index, diagnostics = estimate_hedonic_index(sales, ridge_lambda=RIDGE_LAMBDA)
index["n_sales_4q"] = (
    index.groupby("dong")["n_sales"].transform(lambda counts: counts.rolling(4, min_periods=4).sum())
)
index["eligible"] = index["n_sales_4q"].ge(MIN_SALES_4Q)

index, tau = attach_standard_error(index, diagnostics["residual_sd"], RIDGE_LAMBDA)
print("\n===== 2. 지수·추정오차 완료 =====")
for key, value in diagnostics.items():
    print(f"  {key}: {value}")
print(f"  동 편차 산포 τ: {tau:.4f} (log 단위)")
print(f"  결측 SE 칸: {int(index['log_index_se'].isna().sum())}개")


# ============================================================================
# 3. 완료 조건 점검 — 거래가 적을수록 SE가 큰가
# ============================================================================

bins = [-1, 0, 2, 5, 10, 20, 50, np.inf]
labels = ["0건", "1~2건", "3~5건", "6~10건", "11~20건", "21~50건", "50건 초과"]
index["n_bin"] = pd.cut(index["n_sales"], bins=bins, labels=labels)
check = (index.groupby("n_bin", observed=True)
    .agg(칸수=("log_index_se", "size"),
         SE중앙값=("log_index_se", "median"),
         SE평균=("log_index_se", "mean"))
    .reset_index())
print("\n===== 3. 거래 건수별 SE =====")
print(check.to_string(index=False))

medians = check["SE중앙값"].to_numpy()
if not np.all(np.diff(medians) < 0):
    raise RuntimeError(f"거래가 늘어도 SE가 줄지 않는다: {medians}")
print("  거래가 많을수록 SE가 단조 감소한다 — 완료 조건 충족")


# ============================================================================
# 4. 저장
# ============================================================================

index_path = output_dir / "60.1.dong_index_se.txt"
index.drop(columns=["n_bin"]).to_csv(index_path, sep="\t", index=False, lineterminator="\n")

print("\n===== 4. 저장 완료 =====")
eligible = index[index["eligible"]]
print(f"  eligible 칸 SE 중앙값 {eligible['log_index_se'].median():.4f}, "
      f"그 외 {index.loc[~index['eligible'], 'log_index_se'].median():.4f}")
print(f"지수: {index_path}")
