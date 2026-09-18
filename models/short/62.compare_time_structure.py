# ============================================================================
# 62.compare_time_structure.py
# ============================================================================
# Author:      yjkim
# Purpose:     파일럿 P2: 월 지수(A)와 3개월 겹침 창(B) target의 noise를 비교해 구조를 고른다
# Description: (i) split-half 신뢰도: 6번째 기점마다 창 안 거래를 무작위로 반씩 나눠
#                  (seed: default_rng([42, 기점])) 각각 다시 추정하고, 두 반쪽 y의 동 간 상관을
#                  Spearman-Brown으로 보정한다. noise SD = sd(y1 − y2) / 2 (전체 표본 기준)
#              (ii) 인접 non-overlapping 기간이지만 경계 지수 창을 공유하는 y_t, y_t+3 상관
#              (iii) 기점별 동 간 y 표준편차 대비 noise SD
#              권고는 post-hoc threshold가 아니라 거래량 bin별 split-half 신뢰도로 정한다.
#              실행: .venv/bin/python models/short/62.compare_time_structure.py [--smoke]
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
SUFFIX = ".smoke" if SMOKE else ""
SPLIT_EVERY = 6
MIN_ELIGIBLE = 10
VOLUME_BINS = [0, 10, 20, 30, 50, np.inf]
VOLUME_LABELS = ["0-9", "10-19", "20-29", "30-49", "50+"]
N_PROC = 12

sales = None


def fit_halves(task):
    origin, structure = task
    window = sales[(sales["mi"] >= origin - WINDOW_BACK) & (sales["mi"] <= origin + FUTURE)]
    in_first = np.random.default_rng([42, origin]).random(len(window)) < 0.5
    halves = [origin_rows(window[mask], origin, structure) for mask in (in_first, ~in_first)]
    return halves[0].merge(halves[1][["dong", "y"]], on="dong", suffixes=("_h1", "_h2"))


def spearman_brown(r):
    return 2 * r / (1 + r)


def volume_bin(n):
    return pd.cut(n, VOLUME_BINS, right=False, labels=VOLUME_LABELS)


# ============================================================================
# 1. 입력
# ============================================================================

started = time.time()
panel = pd.read_csv(OUTPUT_DIR / f"61.1.origin_panel{SUFFIX}.txt", sep="\t", dtype={"sggCd": str})
assert panel["origin"].max() <= LAST_PILOT_ORIGIN
sales = load_sales()
if SMOKE:
    sales = sales[sales["sggCd"].isin(panel["sggCd"].unique())]
origins = sorted(ym_to_mi(panel["origin"].unique()))[::SPLIT_EVERY]

# ============================================================================
# 2. (i) split-half 신뢰도
# ============================================================================

with Pool(N_PROC) as pool:
    parts = pool.map(fit_halves, [(o, s) for o in origins for s in ("A", "B")], chunksize=1)
split = pd.concat(parts, ignore_index=True)
full_n = panel[["dong", "origin", "structure", "n_3m"]]
split = split.drop(columns="n_3m").merge(full_n, on=["dong", "origin", "structure"])
split = split.dropna(subset=["y_h1", "y_h2"])
split["bin"] = volume_bin(split["n_3m"])
# 반쪽마다 서울 전체 수준 변화가 다르게 잡히므로 기점별 동 평균을 빼고 상관을 본다
for col in ("y_h1", "y_h2"):
    split[col] = split[col] - split.groupby(["structure", "origin"])[col].transform("mean")

bin_rows = []
for (structure, label), part in split.groupby(["structure", "bin"], observed=True):
    r = part["y_h1"].corr(part["y_h2"])
    bin_rows.append({"structure": structure, "n3m_bin": label, "n_rows": len(part), "r_half": r,
                     "reliability_sb": spearman_brown(r), "noise_sd": (part["y_h1"] - part["y_h2"]).std() / 2})
by_bin = pd.DataFrame(bin_rows)

# ============================================================================
# 3. (ii) 자기상관, (iii) 동 간 SD vs noise SD — 평가 대상(최근 3개월 10건 이상) 동
# ============================================================================

summary_rows = []
autocorr_rows = []
for structure in ("A", "B"):
    part = panel[(panel["structure"] == structure) & (panel["n_3m"] >= MIN_ELIGIBLE)].dropna(subset=["y"]).copy()
    part["mi"] = ym_to_mi(part["origin"])
    part["r"] = part["y"] - part.groupby("origin")["y"].transform("mean")
    later = part[["dong", "mi", "y", "r"]].assign(mi=lambda d: d["mi"] - 3)
    pairs = part.merge(later, on=["dong", "mi"], suffixes=("", "_next"))
    pairs["bin"] = volume_bin(pairs["n_3m"])
    for label, sub in pairs.groupby("bin", observed=True):
        autocorr_rows.append({"structure": structure, "n3m_bin": label, "n_pairs": len(sub),
                              "autocorr_raw": sub["y"].corr(sub["y_next"]),
                              "autocorr_relative": sub["r"].corr(sub["r_next"])})

    halves = split[(split["structure"] == structure) & (split["n_3m"] >= MIN_ELIGIBLE)]
    per_origin = halves.groupby("origin").apply(
        lambda g: pd.Series({"r": g["y_h1"].corr(g["y_h2"]), "noise_sd": (g["y_h1"] - g["y_h2"]).std() / 2}),
        include_groups=False)
    cross_sd = part.groupby("origin")["y"].std()
    noise_sd = per_origin["noise_sd"].mean()
    summary_rows.append({
        "structure": structure,
        "split_origins": len(per_origin),
        "mean_r_half": per_origin["r"].mean(),
        "mean_reliability_sb": spearman_brown(per_origin["r"]).mean(),
        "autocorr_raw": pairs["y"].corr(pairs["y_next"]),
        "autocorr_relative": pairs["r"].corr(pairs["r_next"]),
        "cross_dong_sd": cross_sd.mean(),
        "noise_sd": noise_sd,
        "noise_to_cross_sd": noise_sd / cross_sd.mean(),
        "mean_eligible_dongs": part.groupby("origin").size().mean(),
    })
summary = pd.DataFrame(summary_rows).set_index("structure")

# 각 volume bin에서 split-half 신뢰도가 더 높은 구조를 권고한다. 동률은 전체 평균으로 결정한다.
pivot = by_bin.pivot(index="n3m_bin", columns="structure", values="reliability_sb").dropna()
wins_b = int((pivot["B"] > pivot["A"]).sum())
chosen = "B" if wins_b > len(pivot) / 2 else summary["mean_reliability_sb"].idxmax()
summary["recommended"] = chosen

# ============================================================================
# 4. 저장
# ============================================================================

paths = {
    "summary": OUTPUT_DIR / f"62.1.structure_summary{SUFFIX}.txt",
    "split": OUTPUT_DIR / f"62.2.split_half_by_volume{SUFFIX}.txt",
    "autocorr": OUTPUT_DIR / f"62.3.autocorr_by_volume{SUFFIX}.txt",
}
summary.reset_index().to_csv(paths["summary"], sep="\t", index=False, lineterminator="\n", float_format="%.4f")
by_bin.to_csv(paths["split"], sep="\t", index=False, lineterminator="\n", float_format="%.4f")
pd.DataFrame(autocorr_rows).to_csv(paths["autocorr"], sep="\t", index=False, lineterminator="\n", float_format="%.4f")

print(summary.drop(columns="recommended").T.round(4).to_string())
print(f"권고 구조: {chosen} (B가 split-half 신뢰도가 높은 volume bin {wins_b}/{len(pivot)})")
print(f"===== 62 완료 ({time.time() - started:.0f}초) =====")
for path in paths.values():
    print(path)
