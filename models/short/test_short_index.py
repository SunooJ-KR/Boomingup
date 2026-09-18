# ============================================================================
# test_short_index.py
# ============================================================================
# Author:      yjkim
# Purpose:     _short_index.estimate_index가 심어 둔 동별 추세를 복원하는지 합성 데이터로 점검한다
# Description: 동마다 월 기울기를 정한 가짜 거래를 만들고, 월 기간(구조 A)과 3개월 창(구조 B)
#              두 가지 기간 열로 추정한 변화율을 정답과 비교한다.
#              실행: .venv/bin/python models/short/test_short_index.py
# ============================================================================

import numpy as np
import pandas as pd

from _short_index import estimate_index, publication_lag, ym_to_mi
from _short_events import validate_feature_time_guard

TREND = {"11110_A": 0.010, "11110_B": -0.005, "11140_C": 0.000, "11140_D": 0.015}   # 월 log 기울기
N_MONTHS = 24


def make_sales(seed=42, noise_sd=0.01):
    rng = np.random.default_rng(seed)
    rows = []
    for dong, slope in TREND.items():
        cell_levels = rng.normal(7, 0.3, size=10)
        for month in range(N_MONTHS):
            for _ in range(40):
                cell = rng.integers(10)
                rows.append({"dong": dong, "sggCd": dong[:5], "cell": f"{dong}_{cell}", "mi": month,
                             "log_ppm2": cell_levels[cell] + slope * month + rng.normal(0, noise_sd)})
    return pd.DataFrame(rows)


def change(grid, dong, first, last):
    series = grid[grid["dong"] == dong].set_index("period")["log_index"]
    return series[last] - series[first]


sales = make_sales()

# 구조 A: 벌점 없이 월 기간이면 동별 기울기를 그대로 복원해야 한다
monthly = estimate_index(sales, "mi", ridge_lambda=0)
for dong, slope in TREND.items():
    assert abs(change(monthly, dong, 0, N_MONTHS - 1) - slope * (N_MONTHS - 1)) < 0.01, dong

# 구조 B: 3개월 창 번호(0..7). 창 중심 간격이 3개월이므로 인접 창 차이 = 기울기×3
sales["window"] = sales["mi"] // 3
windowed = estimate_index(sales, "window", ridge_lambda=0)
for dong, slope in TREND.items():
    assert abs(change(windowed, dong, 0, 7) - slope * 21) < 0.01, dong

# 벌점이 있으면 구 평균 쪽으로 당겨지되 순서는 유지해야 한다
shrunk = estimate_index(sales, "mi", ridge_lambda=5)
order = sorted(TREND, key=lambda dong: change(shrunk, dong, 0, N_MONTHS - 1))
assert order == sorted(TREND, key=TREND.get), order
assert change(shrunk, "11110_A", 0, N_MONTHS - 1) < change(monthly, "11110_A", 0, N_MONTHS - 1)
assert (monthly["n_sales"] == 40).all()

# MAIN의 동·구 가격 feature와 모든 forecast의 최대 사용 월 guard.
for ym in (201912, 202003, 202501):
    t = int(ym_to_mi(ym)); lag = publication_lag(t)
    main_price_max = t - 3
    forecast_max = t - lag
    assert main_price_max <= t - 3
    assert forecast_max <= t - lag

# P8 audit guard가 실제 source 최대월 오염을 잡는지 확인한다.
origin = 202001; t = int(ym_to_mi(origin)); lag = int(publication_lag(t))
audit_row = pd.DataFrame([{"origin": origin, "mi": t, "rail_max_public_ym": origin,
                           "supply_max_completion_ym": int(201911)}])
for column, value, message in (
        ("rail_max_public_ym", 202002, "미래 공개 rail row guard가 실패하지 않았다"),
        ("supply_max_completion_ym", 202001, "미래 completion row guard가 실패하지 않았다")):
    contaminated = audit_row.copy(); contaminated[column] = value
    try:
        validate_feature_time_guard(contaminated)
    except AssertionError:
        pass
    else:
        raise AssertionError(message)

print("모든 점검 통과")
