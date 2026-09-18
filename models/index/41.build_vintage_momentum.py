# ============================================================================
# 41.build_vintage_momentum.py
# ============================================================================
# Author:      yjkim
# Purpose:     기점마다 그 시점까지의 거래로만 지수를 다시 추정해 모멘텀 feature를 만든다
# Description: 사전 등록 결정 6a. 전체 데이터 지수(40)는 미래 거래가 단지 FE를 통해
#              과거 값에 스며들므로 feature·baseline에는 이 vintage 값만 쓴다.
#              - mom_{k}q: 기점 t의 vintage 지수 − t−k 분기 vintage 지수 (log)
#              - mom_{k}q_gu_rel: 같은 구 동 평균 대비 차이
#              - n_sales_4q / eligible: 기점 포함 직전 4분기 매매 20건 이상 (결정 7)
#              - baseline B1 = mom_{h}q, B2 = 기점별 eligible 동의 mom_{h}q 평균 (결정 9)
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import time
from pathlib import Path

import numpy as np
import pandas as pd

from _dong_index import RIDGE_LAMBDA, estimate_hedonic_index, load_sales

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"

FIRST_ORIGIN = pd.Period("2011Q4", freq="Q")     # 전월세(2011Q1~)의 직전 4분기가 처음 채워지는 분기
LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
MOMENTUM_LAGS = [1, 2, 4, 8, 12]
MIN_SALES_4Q = 20


# ============================================================================
# 1. 매매 적재
# ============================================================================

sales = load_sales(output_dir / "11.1.trades_sale.txt")
sales = sales[sales["quarter"] <= LAST_COMPLETE_QUARTER].reset_index(drop=True)
first_origin = max(FIRST_ORIGIN, sales["quarter"].min() + 3)   # 4분기 누적이 가능한 첫 기점
origins = pd.period_range(first_origin, LAST_COMPLETE_QUARTER, freq="Q")
print("===== 1. 매매 적재 완료 =====")
print(f"  {len(sales):,}건 / 기점 {len(origins)}개 ({origins[0]} ~ {origins[-1]})")


# ============================================================================
# 2. 기점별 vintage 지수
# ============================================================================

frames = []
started = time.time()
for position, origin in enumerate(origins):
    vintage, diagnostics = estimate_hedonic_index(sales[sales["quarter"] <= origin], ridge_lambda=RIDGE_LAMBDA)
    wide = vintage.pivot(index="dong", columns="quarter", values="log_index")
    counts = vintage.pivot(index="dong", columns="quarter", values="n_sales")

    features = vintage.loc[vintage["quarter"] == origin, ["dong", "sggCd", "umdNm"]].set_index("dong")
    features["as_of_quarter"] = origin
    features["n_sales_4q"] = counts.loc[:, origin - 3:origin].sum(axis=1)
    for lag in MOMENTUM_LAGS:
        past = origin - lag
        column = f"mom_{lag}q"
        features[column] = wide[origin] - wide[past] if past in wide.columns else np.nan
        features[f"{column}_gu_rel"] = features[column] - features.groupby("sggCd")[column].transform("mean")
    frames.append(features.reset_index())

    elapsed = time.time() - started
    print(f"처리 중 [{position + 1}/{len(origins)}]: {origin} "
          f"(거래 {diagnostics['n_sales']:,}, lsqr {diagnostics['lsqr_iterations']}회, 누적 {elapsed:.0f}초)")

panel = pd.concat(frames, ignore_index=True)
panel["eligible"] = panel["n_sales_4q"].ge(MIN_SALES_4Q)
print("\n===== 2. vintage 지수 완료 =====")


# ============================================================================
# 3. 저장
# ============================================================================

panel_path = output_dir / "41.1.vintage_momentum.txt"
panel.to_csv(panel_path, sep="\t", index=False, lineterminator="\n")

summary = panel.groupby("as_of_quarter").agg(dongs=("dong", "size"), eligible=("eligible", "sum")).reset_index()
print(summary.tail(8).to_string(index=False))
print(f"\nvintage 모멘텀: {panel_path}")
