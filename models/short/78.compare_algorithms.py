# ============================================================================
# 78.compare_algorithms.py
# MAIN 동 상대 target에서 algorithm별 expanding-window 성능을 비교한다.
# ============================================================================
import argparse
import time

import numpy as np
import pandas as pd
import sklearn

from _algos import fit_elastic, fit_ols, fit_rf, fit_svr
from _short_eval import (EVAL_FIRST, EVAL_LAST, FEATURES, PERIODS, add_features,
                         block_bootstrap, in_period, load_panel, origin_metrics, read_structure)
from _short_index import OUTPUT_DIR, ym_to_mi

MIN_ELIGIBLE, REFIT_EVERY = 10, 12
PERIOD_NAMES = ("2012-2019", "2020-2025.01")
MODELS = ("R0", "OLS", "Ridge", "ElasticNet", "RandomForest", "SVR_RBF", "LightGBM")


def zscore(frame, eligible):
    ref = frame[FEATURES].where(eligible)
    mean = ref.groupby(frame.origin).transform("mean")
    sd = ref.groupby(frame.origin).transform("std")
    return ((frame[FEATURES] - mean) / sd.where(sd > 0)).fillna(0).clip(-5, 5).to_numpy()


def improvement(values):
    return 1 - values[:, 0].mean() / values[:, 1].mean()


def difference_vs_ridge(values):
    """양수이면 후보의 relative MAE가 Ridge보다 낮다."""
    return (values[:, 1] - values[:, 0]).mean()


def prepare_panel():
    panel = add_features(load_panel(read_structure()), "MAIN")
    panel = panel[(panel.n_12m >= 1) & panel.y.notna()].reset_index(drop=True)
    panel["eligible"] = panel.n_3m >= MIN_ELIGIBLE
    panel["r"] = panel.y - panel.y.where(panel.eligible).groupby(panel.origin).transform("mean")
    assert panel.origin.max() <= EVAL_LAST == 202501, "sealed holdout origin이 포함됐다"
    return panel


def load_reference_predictions(panel):
    """64번에서 이미 계산한 MAIN Ridge·LightGBM fit 결과를 재사용한다."""
    path = OUTPUT_DIR / "64.3.predictions.txt"
    ref = pd.read_csv(path, sep="\t", dtype={"sggCd": str})
    ref = ref[ref.feature_set.eq("MAIN") & ref.origin.between(EVAL_FIRST, EVAL_LAST)]
    keys = ["dong", "origin"]
    if ref.duplicated(keys).any():
        raise ValueError("64.3 MAIN reference prediction key가 중복됐다")
    out = panel.merge(ref[keys + ["pred_ridge", "pred_lgbm"]], on=keys, how="left", validate="one_to_one")
    check = out.eligible & out.origin.between(EVAL_FIRST, EVAL_LAST)
    if out.loc[check, ["pred_ridge", "pred_lgbm"]].isna().any().any():
        raise ValueError("64.3 reference prediction이 일부 누락됐다")
    return out


def fit_candidates(panel, smoke=False):
    x_z = zscore(panel, panel.eligible)
    x_raw = panel[FEATURES].to_numpy()
    for name in ("OLS", "ElasticNet", "RandomForest", "SVR_RBF"):
        panel[f"pred_{name}"] = np.nan
    runtime = {name: 0.0 for name in MODELS}
    tuning = []
    starts = list(range(ym_to_mi(EVAL_FIRST), ym_to_mi(EVAL_LAST) + 1, REFIT_EVERY))
    if smoke:
        starts = starts[:2]
    for t0 in starts:
        train_mask = (panel.eligible & (panel.mi + 3 <= t0)).to_numpy()
        pred_mask = ((panel.mi >= t0) & (panel.mi < t0 + REFIT_EVERY) &
                     (panel.mi <= ym_to_mi(EVAL_LAST))).to_numpy()
        train = panel[train_mask]
        y = train.r.to_numpy()
        fitted = {}
        for name, builder, x in (
            ("OLS", lambda: (fit_ols(x_z[train_mask], y), None), x_z),
            ("ElasticNet", lambda: fit_elastic(train, x_z[train_mask]), x_z),
            ("RandomForest", lambda: fit_rf(train, x_raw[train_mask]), x_raw),
            ("SVR_RBF", lambda: fit_svr(train, x_z[train_mask]), x_z),
        ):
            tick = time.perf_counter()
            model, selected = builder()
            fitted[name] = model
            runtime[name] += time.perf_counter() - tick
            panel.loc[pred_mask, f"pred_{name}"] = model.predict(x[pred_mask])
            tuning.append({"refit_origin": int(panel.loc[pred_mask, "origin"].min()),
                           "model": name, "selected": str(selected), "n_train": len(train)})
    return panel, runtime, pd.DataFrame(tuning)


def summarize(panel, runtime):
    evaluated = panel[panel.eligible & panel.origin.between(EVAL_FIRST, EVAL_LAST)].copy()
    evaluated["pred_R0"] = 0.0
    evaluated["pred_Ridge"] = evaluated.pred_ridge
    evaluated["pred_LightGBM"] = evaluated.pred_lgbm
    per = {name: origin_metrics(evaluated, f"pred_{name}", y="r") for name in MODELS}
    rows = []
    for period in PERIOD_NAMES:
        base = per["R0"][in_period(per["R0"].index, period)]
        ridge = per["Ridge"][in_period(per["Ridge"].index, period)]
        for name in MODELS:
            part = per[name][in_period(per[name].index, period)]
            joined = pd.DataFrame({"candidate": part.rel_mae, "r0": base.rel_mae,
                                   "ridge": ridge.rel_mae}).dropna()
            imp, imp_lo, imp_hi = block_bootstrap(joined[["candidate", "r0"]], stat=improvement)
            diff, diff_lo, diff_hi = block_bootstrap(joined[["candidate", "ridge"]],
                                                      stat=difference_vs_ridge)
            rho = part.spearman.dropna()
            rho_mean, rho_lo, rho_hi = block_bootstrap(rho) if len(rho) >= 6 else (np.nan,) * 3
            rows.append({"period": period, "candidate": name, "n_origins": len(part),
                         "rel_mae_improve_vs_R0": imp, "improve_ci_lo": imp_lo,
                         "improve_ci_hi": imp_hi, "mean_spearman": rho_mean,
                         "spearman_ci_lo": rho_lo, "spearman_ci_hi": rho_hi,
                         "direction_accuracy": part.dir_acc.mean(), "mae_diff_vs_Ridge": diff,
                         "diff_ci_lo": diff_lo, "diff_ci_hi": diff_hi,
                         "runtime_seconds": runtime.get(name, 0.0)})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="처음 두 refit만 실행한다")
    args = parser.parse_args()
    started = time.perf_counter()
    panel = load_reference_predictions(prepare_panel())
    panel, runtime, tuning = fit_candidates(panel, smoke=args.smoke)
    if args.smoke:
        count = panel.filter(regex=r"^pred_(OLS|ElasticNet|RandomForest|SVR_RBF)$").notna().sum()
        print("smoke prediction counts:", count.to_dict())
        print("candidate runtimes:", {key: round(value, 1) for key, value in runtime.items()})
        print(f"scikit-learn={sklearn.__version__}, runtime={time.perf_counter() - started:.1f}s")
        return
    summary = summarize(panel, runtime)
    summary.to_csv(OUTPUT_DIR / "78.1.algorithm_comparison.txt", sep="\t", index=False,
                   lineterminator="\n", float_format="%.6f")
    tuning.to_csv(OUTPUT_DIR / "78.2.tuning.txt", sep="\t", index=False, lineterminator="\n")
    pd.DataFrame([{"candidate": name, "runtime_seconds": runtime[name]} for name in MODELS]).to_csv(
        OUTPUT_DIR / "78.3.runtimes.txt", sep="\t", index=False, lineterminator="\n", float_format="%.3f")
    print(summary.to_string(index=False, float_format="%.4f"))
    print(f"scikit-learn={sklearn.__version__}; total_runtime={time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
