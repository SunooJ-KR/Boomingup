# ============================================================================
# test_dong_index.py
# ============================================================================
# Author:      yjkim
# Purpose:     _dong_index의 두 지수가 알려진 추세를 복원하는지 합성 데이터로 점검한다
# Description: 동마다 분기당 기울기가 정해진 가짜 거래를 만들고 추정 변화율을 비교한다.
#              실행: python models/index/test_dong_index.py
# ============================================================================

import numpy as np
import pandas as pd

from _dong_index import estimate_hedonic_index, estimate_repeat_sales_index

TREND = {"11110_A": 0.02, "11110_B": -0.01, "11140_C": 0.00, "11140_D": 0.03}
QUARTERS = pd.period_range("2020Q1", periods=12, freq="Q")


def make_sales(seed=42, noise_sd=0.005):
    # 셀 10개 × 분기 3건이면 반복거래 쌍이 인접 분기 사이에만 동당 약 105개 생긴다.
    # 쌍 잡음이 11개 분기에 누적되므로 noise_sd=0.02면 누적 SE≈0.03으로 허용오차를 넘는다
    rng = np.random.default_rng(seed)
    rows = []
    for dong, slope in TREND.items():
        cell_levels = rng.normal(7, 0.3, size=10)
        for q_pos, quarter in enumerate(QUARTERS):
            for _ in range(30):
                cell = rng.integers(10)
                rows.append({
                    "dong": dong, "sggCd": dong[:5], "umdNm": dong[6:], "cell": f"{dong}_{cell}",
                    "quarter": quarter, "log_ppm2": cell_levels[cell] + slope * q_pos + rng.normal(0, noise_sd),
                })
    return pd.DataFrame(rows)


def total_change(index, dong):
    series = index[index["dong"] == dong].set_index("quarter")["log_index"]
    return series.iloc[-1] - series.iloc[0]


sales = make_sales()
span = len(QUARTERS) - 1

# 벌점이 없으면 동별 추세를 그대로 복원해야 한다
unpenalized, _ = estimate_hedonic_index(sales, ridge_lambda=0)
for dong, slope in TREND.items():
    assert abs(total_change(unpenalized, dong) - slope * span) < 0.01, dong

# 벌점이 있으면 구 평균 쪽으로 당겨지되 동 간 순서는 유지해야 한다
shrunk, _ = estimate_hedonic_index(sales, ridge_lambda=5)
order = sorted(TREND, key=lambda dong: total_change(shrunk, dong))
assert order == sorted(TREND, key=TREND.get), order
assert total_change(shrunk, "11110_A") < total_change(unpenalized, "11110_A")

repeat = estimate_repeat_sales_index(sales)
for dong, slope in TREND.items():
    change = repeat[f"{dong}|{QUARTERS[-1]}"] - repeat[f"{dong}|{QUARTERS[0]}"]
    assert abs(change - slope * span) < 0.02, dong

print("모든 점검 통과")
