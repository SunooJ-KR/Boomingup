# ============================================================================
# 76.evaluate_dong6m.py
# ============================================================================
# Author:      yjkim
# Purpose:     법정동 6개월 상대 가격의 reliability·baseline·model 성능을 평가한다
# Description: expanding window, 12개월 refit, s+6≤t purge, origin 동일 가중을 적용한다.
# ============================================================================

import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from _dong6m import (EVAL_FIRST, EVAL_LAST, HORIZON, LAST_ORIGIN, PERIODS, assert_time_rules,
                     block_bootstrap, in_period, interval_coverage, relative_metrics,
                     spearman_brown, volume_bin)
from _short_eval import FEATURES, add_features
from _short_index import OUTPUT_DIR, mi_to_ym, ym_to_mi

SMOKE = "--smoke" in sys.argv
MIN_ELIGIBLE = 10
REFIT_EVERY = 12
RIDGE_GRID = np.logspace(-2, 7, 10)
LGB_PARAMS = {
    "objective": "regression", "metric": "l1", "learning_rate": .03, "num_leaves": 15,
    "min_data_in_leaf": 100, "feature_fraction": .8, "lambda_l2": 1., "seed": 42,
    "feature_fraction_seed": 42, "bagging_seed": 42, "data_random_seed": 42,
    "deterministic": True, "force_row_wise": True, "num_threads": 8, "verbose": -1,
}


def zscore(frame):
    values = frame[FEATURES]
    mean = values.groupby(frame["origin"]).transform("mean")
    sd = values.groupby(frame["origin"]).transform("std")
    return ((values - mean) / sd.where(sd > 0)).fillna(0).clip(-5, 5).to_numpy()


def ridge_fit(x, y, ridge_lambda):
    return np.linalg.solve(x.T @ x + ridge_lambda * np.eye(x.shape[1]), x.T @ y)


def origin_equal_mae(prediction, target, origins):
    frame = pd.DataFrame({"prediction": prediction, "target": target, "origin": origins})
    return (frame["prediction"] - frame["target"]).abs().groupby(frame["origin"]).mean().mean()


def inner_masks(train):
    origins = np.sort(train["mi"].unique())
    validation_origins = origins[-24:]
    validation_start = validation_origins[0]
    fit = train["mi"].add(HORIZON).le(validation_start).to_numpy()
    validation = train["mi"].isin(validation_origins).to_numpy()
    assert (train.loc[fit, "mi"] + HORIZON <= validation_start).all()
    return fit, validation


def choose_lambda(train, x):
    fit, validation = inner_masks(train)
    scores = []
    for ridge_lambda in RIDGE_GRID:
        beta = ridge_fit(x[fit], train.loc[fit, "r"].to_numpy(), ridge_lambda)
        scores.append(origin_equal_mae(x[validation] @ beta, train.loc[validation, "r"],
                                       train.loc[validation, "origin"]))
    return float(RIDGE_GRID[int(np.argmin(scores))])


def summarize_reliability(halves):
    work = halves.dropna(subset=["y_h1", "y_h2"]).copy()
    work["volume_bin"] = volume_bin(work["n_3m"])
    for column in ("y_h1", "y_h2"):
        work[column] -= work.groupby("origin")[column].transform("mean")
    rows = []
    for label, part in work.groupby("volume_bin", observed=True):
        corr = part["y_h1"].corr(part["y_h2"])
        per_origin = part.groupby("origin").apply(
            lambda group: group["y_h1"].corr(group["y_h2"]) if len(group) >= 3 else np.nan,
            include_groups=False)
        rows.append({"volume_bin": str(label), "n_rows": len(part), "n_origins": part["origin"].nunique(),
                     "r_half_pooled": corr, "reliability_sb_pooled": spearman_brown(corr),
                     "mean_reliability_sb_origin": per_origin.map(spearman_brown).mean()})
    for threshold in (10, 20):
        part = work[work["n_3m"] >= threshold]
        corr = part["y_h1"].corr(part["y_h2"])
        rows.append({"volume_bin": f">={threshold}", "n_rows": len(part), "n_origins": part["origin"].nunique(),
                     "r_half_pooled": corr, "reliability_sb_pooled": spearman_brown(corr),
                     "mean_reliability_sb_origin": part.groupby("origin").apply(
                         lambda group: spearman_brown(group["y_h1"].corr(group["y_h2"])),
                         include_groups=False).mean()})
    return pd.DataFrame(rows)


def add_coverage(metrics, evaluated, method):
    coverage = interval_coverage(evaluated, method)
    return metrics.join(coverage)


def summarize_method(per_origin, method, period, n_min):
    part = per_origin[in_period(per_origin.index, period)]
    values = {column: part[column].mean() for column in
              ("n_dongs", "rel_mae", "spearman", "direction_accuracy", "coverage", "interval_width")}
    return {"n_min": n_min, "period": period, "method": method, "n_origins": len(part), **values}


def main():
    started = time.time()
    suffix = ".smoke" if SMOKE else ""
    panel = pd.read_csv(OUTPUT_DIR / f"75.1.dong6m_panel{suffix}.txt", sep="\t", dtype={"sggCd": str})
    halves = pd.read_csv(OUTPUT_DIR / f"75.2.dong6m_split_half{suffix}.txt", sep="\t", dtype={"sggCd": str})
    assert panel["origin"].max() <= LAST_ORIGIN
    reliability = summarize_reliability(halves)

    panel["mi"] = ym_to_mi(panel["origin"])
    # smoke도 48개월 학습 이력을 쓰므로 완전한 read-only pastfit cache에서 필요한 동만 가져온다.
    past_path = OUTPUT_DIR / "61.2.pastfit.txt"
    panel = add_features(panel, "MAIN", past_path=past_path)
    assert_time_rules(panel)
    panel = panel[panel["y"].notna()].reset_index(drop=True)
    panel["eligible"] = panel["n_3m"] >= MIN_ELIGIBLE
    panel["r"] = panel["y"] - panel["y"].where(panel["eligible"]).groupby(panel["origin"]).transform("mean")
    panel["R0"] = 0.
    panel["dong_momentum"] = panel["mom_0_3"].fillna(panel["gu_mom_0_3"]).fillna(panel["local_seoul_mom_0_3"])
    panel["gu_momentum"] = panel["gu_mom_0_3"].fillna(panel["local_seoul_mom_0_3"])
    for column in ("dong_momentum", "gu_momentum"):
        panel[column] -= panel[column].where(panel["eligible"]).groupby(panel["origin"]).transform("mean")
    panel[["Ridge", "LightGBM"]] = np.nan
    x_all = zscore(panel)
    tuning_rows = []

    first_eval = max(int(ym_to_mi(EVAL_FIRST)), int(panel["mi"].min()) + 36)
    last_eval = min(int(ym_to_mi(EVAL_LAST)), int(panel["mi"].max()))
    for refit in range(first_eval, last_eval + 1, REFIT_EVERY):
        train_mask = (panel["eligible"] & (panel["mi"] + HORIZON <= refit)).to_numpy()
        predict_mask = ((panel["mi"] >= refit) & (panel["mi"] < refit + REFIT_EVERY) &
                        (panel["mi"] <= last_eval)).to_numpy()
        train, x_train = panel.loc[train_mask], x_all[train_mask]
        assert (train["mi"] + HORIZON <= refit).all()
        fit, validation = inner_masks(train)
        ridge_lambda = choose_lambda(train, x_train)
        beta = ridge_fit(x_train, train["r"].to_numpy(), ridge_lambda)
        booster = lgb.train(
            LGB_PARAMS,
            lgb.Dataset(train.loc[fit, FEATURES], label=train.loc[fit, "r"]),
            num_boost_round=2000,
            valid_sets=[lgb.Dataset(train.loc[validation, FEATURES], label=train.loc[validation, "r"])],
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        panel.loc[predict_mask, "Ridge"] = x_all[predict_mask] @ beta
        panel.loc[predict_mask, "LightGBM"] = booster.predict(
            panel.loc[predict_mask, FEATURES], num_iteration=booster.best_iteration)
        tuning_rows.append({"refit_origin": int(mi_to_ym(refit)), "n_train": int(train_mask.sum()),
                            "ridge_lambda": ridge_lambda,
                            "lambda_at_edge": ridge_lambda in (RIDGE_GRID[0], RIDGE_GRID[-1]),
                            "lgb_best_iteration": booster.best_iteration})

    methods = ("R0", "dong_momentum", "gu_momentum", "Ridge", "LightGBM")
    all_per_method, baseline_rows, model_rows = {}, [], []
    for n_min in (10, 20):
        evaluated = panel[(panel["n_3m"] >= n_min) & panel["origin"].between(EVAL_FIRST, EVAL_LAST)].copy()
        evaluated["r"] = evaluated["y"] - evaluated.groupby("origin")["y"].transform("mean")
        # 모든 후보를 같은 origin cross-section의 상대 예측으로 맞춘다.
        for method in methods:
            evaluated[method] -= evaluated.groupby("origin")[method].transform("mean")
        per_method = {method: add_coverage(relative_metrics(evaluated.dropna(subset=[method]), method),
                                           evaluated.dropna(subset=[method]), method)
                      for method in methods}
        all_per_method[n_min] = per_method
        baseline_rows.extend(
            summarize_method(per_method[method], method, period, n_min)
            for period in PERIODS for method in methods[:3]
        )
        reference = per_method["R0"]
        for period in PERIODS:
            ref = reference[in_period(reference.index, period)]
            for method in methods[3:]:
                metrics = per_method[method]
                part = metrics[in_period(metrics.index, period)]
                joined = pd.DataFrame({"model": part["rel_mae"], "reference": ref["rel_mae"]}).dropna()
                improve = lambda values: 1 - values[:, 0].mean() / values[:, 1].mean()
                estimate, improve_lo, improve_hi = block_bootstrap(joined, stat=improve)
                rho = part["spearman"].dropna()
                rho_est, rho_lo, rho_hi = block_bootstrap(rho)
                model_rows.append({
                    **summarize_method(part, method, period, n_min),
                    "rel_mae_improve_vs_R0": estimate, "improve_ci_lo": improve_lo, "improve_ci_hi": improve_hi,
                    "spearman_ci_lo": rho_lo, "spearman_ci_hi": rho_hi,
                })
    baseline_summary = pd.DataFrame(baseline_rows)
    model_summary = pd.DataFrame(model_rows)

    verdicts = []
    for method in methods[3:]:
        rows = model_summary[(model_summary["method"] == method) & (model_summary["n_min"] == 10)].set_index("period")
        directions = rows.loc[["2012-2019", "2020-2025.01"], "rel_mae_improve_vs_R0"] > 0
        overall = rows.loc["all"]
        killed = (directions.nunique() > 1 or overall["improve_ci_lo"] <= 0 or
                  overall["spearman_ci_lo"] <= .10)
        reasons = []
        if directions.nunique() > 1:
            reasons.append("기간별 개선 방향 불일치")
        if overall["improve_ci_lo"] <= 0:
            reasons.append("상대 MAE 개선 CI 하한≤0")
        if overall["spearman_ci_lo"] <= .10:
            reasons.append("Spearman CI 하한≤0.10")
        verdicts.append({"method": method, "verdict": "중단" if killed else "통과",
                         "reason": "; ".join(reasons) if reasons else "kill criterion 모두 통과"})
    verdict = pd.DataFrame(verdicts)

    origin_rows = []
    for n_min, per_method in all_per_method.items():
        for method, metrics in per_method.items():
            origin_rows.append(metrics.assign(method=method, n_min=n_min).reset_index())
    paths = {
        "reliability": OUTPUT_DIR / f"76.1.reliability{suffix}.txt",
        "baseline": OUTPUT_DIR / f"76.2.baseline_summary{suffix}.txt",
        "model": OUTPUT_DIR / f"76.3.model_summary{suffix}.txt",
        "origin": OUTPUT_DIR / f"76.4.metrics_by_origin{suffix}.txt",
        "tuning": OUTPUT_DIR / f"76.5.tuning{suffix}.txt",
        "verdict": OUTPUT_DIR / f"76.6.kill_verdict{suffix}.txt",
    }
    frames = {"reliability": reliability, "baseline": baseline_summary, "model": model_summary,
              "origin": pd.concat(origin_rows), "tuning": pd.DataFrame(tuning_rows), "verdict": verdict}
    for name, path in paths.items():
        frames[name].to_csv(path, sep="\t", index=False, lineterminator="\n", float_format="%.6f")

    print("reliability: bin rows origins pooled_SB mean_origin_SB")
    for row in reliability.itertuples():
        print(f"{row.volume_bin} {row.n_rows} {row.n_origins} {row.reliability_sb_pooled:.3f} "
              f"{row.mean_reliability_sb_origin:.3f}")
    print("baseline N=10 all: method rel_MAE rho dir coverage")
    for row in baseline_summary[(baseline_summary["n_min"] == 10) &
                                (baseline_summary["period"] == "all")].itertuples():
        print(f"{row.method} {row.rel_mae:.4f} {row.spearman:.4f} {row.direction_accuracy:.4f} {row.coverage:.4f}")
    print("models N=10: period method improve[CI] rho[CI] dir coverage")
    for row in model_summary[model_summary["n_min"] == 10].itertuples():
        print(f"{row.period} {row.method} {row.rel_mae_improve_vs_R0:.4f}"
              f"[{row.improve_ci_lo:.4f},{row.improve_ci_hi:.4f}] {row.spearman:.4f}"
              f"[{row.spearman_ci_lo:.4f},{row.spearman_ci_hi:.4f}] "
              f"{row.direction_accuracy:.4f} {row.coverage:.4f}")
    for row in verdict.itertuples():
        print(f"kill {row.method}: {row.verdict} ({row.reason})")
    print(f"76 완료 {time.time() - started:.1f}초")
    print("저장: " + ", ".join(str(path) for path in paths.values()))


if __name__ == "__main__":
    main()
