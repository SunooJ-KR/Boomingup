# ============================================================================
# 40.build_dong_index.py
# ============================================================================
# Author:      yjkim
# Purpose:     법정동×분기 hedonic 가격 지수(target 원천)를 만들고 반복거래 지수로 점검한다
# Description: 사전 등록 docs/decisions.md 결정 4~7을 구현한다.
#              - 전체 데이터로 한 번 추정한 지수다. feature용 vintage 지수는 여기서 만들지 않는다(결정 6a)
#              - 마지막 완결 분기(2026Q2)까지만 쓴다. 2026-07~08은 분기가 끝나지 않았다
#              - eligible: 해당 분기 포함 직전 4분기 매매 20건 이상 (결정 7)
#              - 점검: 동별 연간(Q4→Q4) 변화의 hedonic vs 반복거래 Spearman (결정 5c, 판정에 쓰지 않음)
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from _dong_index import RIDGE_LAMBDA, estimate_hedonic_index, estimate_repeat_sales_index, load_sales

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"

LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
MIN_SALES_4Q = 20


# ============================================================================
# 1. 매매 적재
# ============================================================================

sales = load_sales(output_dir / "11.1.trades_sale.txt")
sales = sales[sales["quarter"] <= LAST_COMPLETE_QUARTER].reset_index(drop=True)
print("===== 1. 매매 적재 완료 =====")
print(f"  {len(sales):,}건 / 동 {sales['dong'].nunique()}개 / {sales['quarter'].min()} ~ {sales['quarter'].max()}")


# ============================================================================
# 2. hedonic 지수
# ============================================================================

index, diagnostics = estimate_hedonic_index(sales, ridge_lambda=RIDGE_LAMBDA)
index["n_sales_4q"] = (
    index.groupby("dong")["n_sales"].transform(lambda counts: counts.rolling(4, min_periods=4).sum())
)
index["eligible"] = index["n_sales_4q"].ge(MIN_SALES_4Q)
print("\n===== 2. hedonic 지수 완료 =====")
for key, value in diagnostics.items():
    print(f"  {key}: {value}")


# ============================================================================
# 3. 반복거래 지수 점검
# ============================================================================

repeat = estimate_repeat_sales_index(sales)

q4 = index[index["quarter"].dt.quarter == 4].copy()
q4["year"] = q4["quarter"].dt.year
q4["d_hedonic"] = q4.groupby("dong")["log_index"].diff()
q4["repeat_index"] = (q4["dong"] + "|" + q4["quarter"].astype(str)).map(repeat)
q4["d_repeat"] = q4.groupby("dong")["repeat_index"].diff()
check = q4.loc[q4["eligible"] & q4["d_hedonic"].notna() & q4["d_repeat"].notna(),
               ["dong", "year", "d_hedonic", "d_repeat"]]
rho = spearmanr(check["d_hedonic"], check["d_repeat"]).statistic
print("\n===== 3. 반복거래 점검 완료 =====")
print(f"  동-연도 {len(check):,}개, Spearman {rho:.3f}")


# ============================================================================
# 4. 저장
# ============================================================================

index_path = output_dir / "40.1.dong_index.txt"
check_path = output_dir / "40.2.index_repeat_check.txt"
index.to_csv(index_path, sep="\t", index=False, lineterminator="\n")
check.to_csv(check_path, sep="\t", index=False, lineterminator="\n")


# ============================================================================
# 5. 요약
# ============================================================================

print("\n===== 5. 연도별 eligible 동 수 (Q4 기준) =====")
summary = (q4.groupby("year")
    .agg(dongs=("dong", "size"), eligible=("eligible", "sum"),
         median_sales_4q=("n_sales_4q", "median"))
    .reset_index())
print(summary.to_string(index=False))
print(f"\n  잔차 SD {diagnostics['residual_sd']:.3f} (log 단위), 결측 지수 칸 {int(index['log_index'].isna().sum())}개")
print(f"\n지수: {index_path}")
print(f"점검: {check_path}")
