# ============================================================================
# 61.build_origin_panel.py
# ============================================================================
# Author:      yjkim
# Purpose:     기점별 hedonic 지수를 다시 추정해 동×기점 target·모멘텀 panel을 만든다 (구조 A·B)
# Description: target fit([t−35,t+3])과 feature용 pastfit([t−35,t])을 분리해 cache한다.
#              기점: 2009-01~2025-01 (월). 가격은 2025-04까지만 읽는다(_short_index.load_sales).
#              실행: .venv/bin/python models/short/61.build_origin_panel.py [--smoke]
# ============================================================================

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from _short_index import (FUTURE, LAST_PILOT_ORIGIN, OUTPUT_DIR, WINDOW_BACK, load_sales, mi_to_ym,
                          origin_rows, ym_to_mi)

SMOKE = "--smoke" in sys.argv
FIRST_ORIGIN = 200901
N_PROC = 12

sales = None


def fit_origin(task):
    origin, structure, include_future = task
    hi = origin + FUTURE if include_future else origin
    window = sales[(sales["mi"] >= origin - WINDOW_BACK) & (sales["mi"] <= hi)]
    return origin_rows(window, origin, structure)


# ============================================================================
# 1. 입력
# ============================================================================

started = time.time()
sales = load_sales()
assert mi_to_ym(sales["mi"].max()) <= 202504
origins = list(range(ym_to_mi(FIRST_ORIGIN), ym_to_mi(LAST_PILOT_ORIGIN) + 1))
if SMOKE:
    sales = sales[sales["sggCd"].isin(["11680", "11620"])]   # 강남구·관악구
    origins = origins[-12:]
print(f"거래 {len(sales):,}건, 기점 {len(origins)}개 ({mi_to_ym(origins[0])}~{mi_to_ym(origins[-1])})")

# 전체 실행 전 1회 시간을 먼저 재서 병렬화 비용을 가늠한다.
probe_started = time.time()
_ = fit_origin((origins[0], "B", False))
print(f"pastfit 1회 예측 시간 {time.time() - probe_started:.2f}초")

# ============================================================================
# 2. 기점별 추정 (A·B) + 누수 점검 재추정
# ============================================================================

tasks = [(o, s, True) for o in origins for s in ("A", "B")]
past_tasks = [(o, "B", False) for o in origins]

with Pool(N_PROC) as pool:
    results = pool.map(fit_origin, tasks + past_tasks, chunksize=1)
panel = pd.concat(results[:len(tasks)], ignore_index=True)
past_only = pd.concat(results[len(tasks):], ignore_index=True)
print(f"추정 {len(tasks) + len(past_tasks)}회 완료 ({time.time() - started:.0f}초)")

# ============================================================================
# 3. guard: pastfit은 자신의 기점 뒤 거래를 쓰지 않음
# ============================================================================

assert past_only["origin"].max() <= LAST_PILOT_ORIGIN
past_only["max_sale_ym"] = past_only["origin"]

# ============================================================================
# 4. 저장
# ============================================================================

suffix = ".smoke" if SMOKE else ""
paths = {
    "panel": OUTPUT_DIR / f"61.1.origin_panel{suffix}.txt",
    "past": OUTPUT_DIR / f"61.2.pastfit{suffix}.txt",
}
panel.to_csv(paths["panel"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
past_only.to_csv(paths["past"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
print(f"===== 61 완료 ({time.time() - started:.0f}초) =====")
for path in paths.values():
    print(path)
