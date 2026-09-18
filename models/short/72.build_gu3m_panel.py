# ============================================================================
# 72.build_gu3m_panel.py
# ============================================================================
# Purpose: 기존 61 panel에서 자치구 3개월 상대 target을 만들고 split-half reliability를 잰다
# 실행: .venv/bin/python models/short/72.build_gu3m_panel.py [--smoke]
# ============================================================================

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from _gu3m import aggregate_gu, center_by_origin, spearman_brown
from _short_index import FUTURE, LAST_PILOT_ORIGIN, OUTPUT_DIR, WINDOW_BACK, load_sales, mi_to_ym, origin_rows, ym_to_mi

SMOKE = "--smoke" in sys.argv
SUFFIX = ".smoke" if SMOKE else ""
EVAL_FIRST = 201201
sales = None
eligibility = None


def fit_split(origin):
    window = sales[(sales["mi"] >= origin - WINDOW_BACK) & (sales["mi"] <= origin + FUTURE)]
    first = np.random.default_rng([42, origin]).random(len(window)) < .5
    halves = []
    for mask, label in ((first, "y_h1"), (~first, "y_h2")):
        part = origin_rows(window[mask], origin, "B")[["dong", "y"]].rename(columns={"y": label})
        halves.append(part)
    joined = halves[0].merge(halves[1], on="dong").merge(eligibility[eligibility["origin"] == int(mi_to_ym(origin))], on="dong")
    gu = aggregate_gu(joined, ["y_h1", "y_h2"])
    return center_by_origin(gu, ["y_h1", "y_h2"])


started = time.time()
raw = pd.read_csv(OUTPUT_DIR / "61.1.origin_panel.txt", sep="\t", dtype={"sggCd": str})
raw = raw[(raw["structure"] == "B") & raw["origin"].between(EVAL_FIRST, LAST_PILOT_ORIGIN)].copy()
assert raw["origin"].max() <= LAST_PILOT_ORIGIN
raw["eligible"] = raw["n_3m"] >= 10
eligibility = raw[["dong", "sggCd", "origin", "eligible"]]
gu = aggregate_gu(raw, ["y"])
gu = center_by_origin(gu, ["y"]).rename(columns={"y": "r"})
gu["mi"] = ym_to_mi(gu["origin"])

all_pairs = raw.groupby(["origin", "sggCd"]).size().rename("all_gu_origins")
eligible_pairs = raw[raw["eligible"]].groupby(["origin", "sggCd"]).size().rename("eligible_dongs")
qc = pd.concat([all_pairs, eligible_pairs], axis=1).fillna(0).reset_index()
qc["kept"] = qc["eligible_dongs"] >= 3

sales = load_sales()
origins = sorted(ym_to_mi(raw["origin"].unique()))
if SMOKE:
    origins = origins[-4:]
with Pool(min(12, len(origins))) as pool:
    split = pd.concat(pool.map(fit_split, origins, chunksize=1), ignore_index=True)

rows = []
for origin, part in split.groupby("origin"):
    correlation = part["y_h1"].corr(part["y_h2"])
    rows.append({"origin": origin, "n_gu": len(part), "r_half": correlation,
                 "reliability_sb": spearman_brown(correlation)})
reliability = pd.DataFrame(rows)
summary = pd.DataFrame([{
    "n_origins": len(reliability),
    "mean_gu": reliability["n_gu"].mean(),
    "mean_r_half": reliability["r_half"].mean(),
    "mean_reliability_sb": reliability["reliability_sb"].mean(),
    "gu_origins_total": len(qc),
    "gu_origins_dropped_lt3": int((~qc["kept"]).sum()),
}])

paths = {
    "panel": OUTPUT_DIR / f"72.1.gu3m_panel{SUFFIX}.txt",
    "qc": OUTPUT_DIR / f"72.2.gu3m_eligibility{SUFFIX}.txt",
    "reliability": OUTPUT_DIR / f"72.3.gu3m_reliability_by_origin{SUFFIX}.txt",
    "summary": OUTPUT_DIR / f"72.4.gu3m_reliability_summary{SUFFIX}.txt",
}
gu.to_csv(paths["panel"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
qc.to_csv(paths["qc"], sep="\t", index=False, lineterminator="\n")
reliability.to_csv(paths["reliability"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
summary.to_csv(paths["summary"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
print(summary.to_string(index=False, float_format="%.4f"))
print(f"72 runtime_seconds={time.time() - started:.2f}")
for path in paths.values():
    print(path)
