# ============================================================================
# 65.compare_sparse_dongs.py
# ============================================================================
# Author:      yjkim
# Purpose:     파일럿 P5: MAIN feature 예측의 사후 구 shrink 실험
# Description: 64.3의 P4 최선 모델 예측(학습은 eligible 동만)을 그대로 쓴다. 다시 학습하지 않는다.
#              (a) 최근 3개월 거래 N건(10/20/30) 이상만 예측: 기점별 예측 동 수와 상대 지표
#              (b) 최근 12개월 거래 1건 이상인 동 전체를 예측하고 구 평균 쪽으로 shrink:
#                  pred_shrunk = w·pred + (1−w)·(같은 구 eligible 동 예측 평균), w = n_3m/(n_3m+10)
#                  거래량 구간별 상대 MAE·Spearman. r은 그 기점 예측 대상 전체의 평균을 뺀 값
#              주의: 거래가 없는 동의 target y도 ridge 때문에 구 변화 쪽으로 당겨져 있다
# ============================================================================

import time

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from _short_eval import EVAL_FIRST, EVAL_LAST, block_bootstrap
from _short_index import OUTPUT_DIR

THRESHOLDS = [10, 20, 30]
SHRINK_K = 10
BINS = [0, 1, 5, 10, 20, 30, np.inf]
BIN_LABELS = ["0", "1-4", "5-9", "10-19", "20-29", "30+"]
MIN_BIN_DONGS = 5


def relative_errors(frame, pred):
    """기점마다 frame 전체 평균을 뺀 예측·target의 절대오차."""
    p = frame[pred] - frame.groupby("origin")[pred].transform("mean")
    r = frame["y"] - frame.groupby("origin")["y"].transform("mean")
    return (p - r).abs()


def mean_spearman(frame, pred):
    rho = frame.groupby("origin")[[pred, "y"]].apply(
        lambda g: spearmanr(g[pred], g["y"])[0] if len(g) >= MIN_BIN_DONGS and g[pred].nunique() > 1 else np.nan)
    return rho.mean()


# ============================================================================
# 1. 입력
# ============================================================================

started = time.time()
summary64 = pd.read_csv(OUTPUT_DIR / "64.1.relative_model_summary.txt", sep="\t")
main_all = summary64[(summary64["feature_set"] == "MAIN") & (summary64["period"] == "all") &
                     summary64["model"].isin(["pred_ridge", "pred_lgbm"])]
best = main_all.sort_values("rel_mae")["model"].iloc[0]
pred = pd.read_csv(OUTPUT_DIR / "64.3.predictions.txt", sep="\t", dtype={"sggCd": str})
pred = pred[(pred["feature_set"] == "MAIN") & pred["origin"].between(EVAL_FIRST, EVAL_LAST)].copy()
pred["R0_zero"] = 0.0
print(f"P4 최선 모델: {best}, 행 {len(pred):,}")

# ============================================================================
# 2. (a) 제외 방식
# ============================================================================

exclusion_rows = []
total_dongs = pred.groupby("origin").size().mean()
for n_min in THRESHOLDS:
    rows = pred[pred["n_3m"] >= n_min].copy()
    model_err = relative_errors(rows, best).groupby(rows["origin"]).mean()
    ref_err = relative_errors(rows, "R0_zero").groupby(rows["origin"]).mean()
    both = pd.DataFrame({"m": model_err, "r": ref_err})
    imp, lo, hi = block_bootstrap(both, stat=lambda d: 1 - d[:, 0].mean() / d[:, 1].mean())
    exclusion_rows.append({"n_min": n_min, "mean_dongs_predicted": rows.groupby("origin").size().mean(),
                           "share_of_active_dongs": rows.groupby("origin").size().mean() / total_dongs,
                           "rel_mae_model": model_err.mean(), "rel_mae_R0": ref_err.mean(),
                           "improve_vs_R0": imp, "improve_ci_lo": lo, "improve_ci_hi": hi,
                           "spearman": mean_spearman(rows, best)})
exclusion = pd.DataFrame(exclusion_rows)

# ============================================================================
# 3. (b) pooling + 구 shrink, 거래량 구간별
# ============================================================================

gu_mean = pred[pred["eligible"]].groupby(["origin", "sggCd"])[best].mean().rename("gu_pred")
pred = pred.join(gu_mean, on=["origin", "sggCd"])
pred["gu_pred"] = pred["gu_pred"].fillna(pred.groupby("origin")[best].transform("mean"))
w = pred["n_3m"] / (pred["n_3m"] + SHRINK_K)
pred["pred_shrunk"] = w * pred[best] + (1 - w) * pred["gu_pred"]
pred["bin"] = pd.cut(pred["n_3m"], BINS, right=False, labels=BIN_LABELS)

methods = ["R0_zero", best, "pred_shrunk"]
errors = {m: relative_errors(pred, m) for m in methods}
pool_rows = []
for label, part in pred.groupby("bin", observed=True):
    row = {"n3m_bin": label, "mean_dongs_per_origin": part.groupby("origin").size().mean(),
           "share_no_target_sales": (part["n_target"] == 0).mean()}
    for m in methods:
        name = "raw" if m == best else m
        row[f"rel_mae_{name}"] = errors[m][part.index].groupby(part["origin"]).mean().mean()
        row[f"spearman_{name}"] = mean_spearman(part, m) if m != "R0_zero" else np.nan
        if m != "R0_zero":
            residual = part["y"] - part[m]
            row[f"interval_width80_{name}"] = residual.quantile(.9) - residual.quantile(.1)
    pool_rows.append(row)
overall = {"n3m_bin": "all", "mean_dongs_per_origin": pred.groupby("origin").size().mean(),
           "share_no_target_sales": (pred["n_target"] == 0).mean()}
for m in methods:
    name = "raw" if m == best else m
    overall[f"rel_mae_{name}"] = errors[m].groupby(pred["origin"]).mean().mean()
    overall[f"spearman_{name}"] = mean_spearman(pred, m) if m != "R0_zero" else np.nan
pooling = pd.DataFrame(pool_rows + [overall])

# ============================================================================
# 4. 저장
# ============================================================================

paths = {
    "exclusion": OUTPUT_DIR / "65.1.exclusion_by_threshold.txt",
    "pooling": OUTPUT_DIR / "65.2.pooling_by_volume.txt",
}
exclusion.assign(model=best).to_csv(paths["exclusion"], sep="\t", index=False, lineterminator="\n", float_format="%.5f")
pooling.assign(model=best).to_csv(paths["pooling"], sep="\t", index=False, lineterminator="\n", float_format="%.5f")
print(exclusion.to_string(index=False, float_format="%.4f"))
print(pooling.to_string(index=False, float_format="%.4f"))
print(f"===== 65 완료 ({time.time() - started:.0f}초) =====")
for path in paths.values():
    print(path)
