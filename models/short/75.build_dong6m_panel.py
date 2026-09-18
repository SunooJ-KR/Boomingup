# ============================================================================
# 75.build_dong6m_panel.py
# ============================================================================
# Author:      yjkim
# Purpose:     법정동 6개월 target과 split-half reliability 입력을 cache한다
# Description: target fit은 [t−35,t+6] 거래를 쓰고 endpoint는 W(t+4..t+6)이다.
#              실행 전 target fit 1회의 시간을 재며, 전체 fit은 process 병렬화한다.
# ============================================================================

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from _dong6m import FIRST_ORIGIN, LAST_ORIGIN, target_rows
from _short_index import OUTPUT_DIR, WINDOW_BACK, load_sales, mi_to_ym, ym_to_mi

SMOKE = "--smoke" in sys.argv
N_PROC = 12
sales = None


def fit_target(task):
    origin, half = task
    window = sales[(sales["mi"] >= origin - WINDOW_BACK) & (sales["mi"] <= origin + 6)]
    if half:
        first = np.random.default_rng([42, origin]).random(len(window)) < .5
        window = window[first if half == 1 else ~first]
    result = target_rows(window, origin)
    if half:
        result = result.rename(columns={"y": f"y_h{half}", "n_target": f"n_target_h{half}"})
    return result


def main():
    global sales
    started = time.time()
    sales = load_sales()
    assert int(mi_to_ym(sales["mi"].max())) <= 202504
    origins = list(range(int(ym_to_mi(FIRST_ORIGIN)), int(ym_to_mi(LAST_ORIGIN)) + 1))
    if SMOKE:
        sales = sales[sales["sggCd"].isin(["11680", "11620"])]
        origins = origins[-48:]
    print(f"거래 {len(sales):,}건, origin {len(origins)}개 ({mi_to_ym(origins[0])}~{mi_to_ym(origins[-1])})")

    probe_started = time.time()
    _ = fit_target((origins[0], 0))
    probe = time.time() - probe_started
    estimated = probe * len(origins) * 3 / N_PROC
    print(f"target fit 1회 {probe:.2f}초, 병렬 예상 {estimated / 60:.1f}분")

    tasks = [(origin, half) for origin in origins for half in (0, 1, 2)]
    with Pool(N_PROC) as pool:
        results = pool.map(fit_target, tasks, chunksize=1)
    panel = pd.concat(results[0::3], ignore_index=True)
    halves = pd.concat([
        left.merge(right[["dong", "origin", "y_h2", "n_target_h2"]], on=["dong", "origin"])
        for left, right in zip(results[1::3], results[2::3])
    ], ignore_index=True)
    assert panel["origin"].max() <= LAST_ORIGIN
    assert halves["origin"].max() <= LAST_ORIGIN

    suffix = ".smoke" if SMOKE else ""
    paths = {
        "panel": OUTPUT_DIR / f"75.1.dong6m_panel{suffix}.txt",
        "halves": OUTPUT_DIR / f"75.2.dong6m_split_half{suffix}.txt",
    }
    panel.to_csv(paths["panel"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
    halves.to_csv(paths["halves"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
    print(f"75 완료 {time.time() - started:.1f}초, panel {len(panel):,}행, split {len(halves):,}행")
    for path in paths.values():
        print(path)


if __name__ == "__main__":
    main()
