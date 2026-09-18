# ============================================================================
# 68.evaluate_event_supply_features.py
# ============================================================================
# Author:      yjkim
# Purpose:     MAIN에 rail·supply feature를 더했을 때 동 상대 예측 개선을 평가한다
# Description: P4와 같은 expanding window, purge, refit, bootstrap 규칙을 사용한다.
# ============================================================================
import argparse
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from _short_eval import (EVAL_FIRST, EVAL_LAST, FEATURE_GROUPS, FEATURES, PERIODS, add_features,
                         block_bootstrap, in_period, load_panel, origin_metrics, read_structure)
from _short_events import (RAIL_LINE_PATH, add_rail_features, add_supply_features, load_rail,
                           feature_time_audit, load_supply, rail_exposure, supply_match_counts,
                           validate_feature_time_guard)
from _short_index import OUTPUT_DIR, mi_to_ym, ym_to_mi

MIN_ELIGIBLE, REFIT_EVERY = 10, 12
RIDGE_GRID = np.logspace(-2, 7, 10)
RAIL_FEATURES = [f"rail_{kind}_{name}" for kind in ("plan", "construction", "open")
                 for name in ("months", "none", "count12")] + ["rail_open_exposure_500", "rail_open_exposure_1000"]
SUPPLY_FEATURES = [f"supply_{level}_{months}m" for months in (3, 6, 12)
                   for level in ("dong", "gu", "dong_trade_scaled")]
SET_FEATURES = {
    "MAIN": FEATURES,
    "MAIN+RAIL": FEATURES + RAIL_FEATURES,
    "MAIN+SUPPLY": FEATURES + SUPPLY_FEATURES,
    "MAIN+RAIL+SUPPLY": FEATURES + RAIL_FEATURES + SUPPLY_FEATURES,
}
LGB_PARAMS = {"objective": "regression", "metric": "l1", "learning_rate": .03, "num_leaves": 15,
              "min_data_in_leaf": 100, "feature_fraction": .8, "lambda_l2": 1., "seed": 42,
              "feature_fraction_seed": 42, "bagging_seed": 42, "data_random_seed": 42,
              "deterministic": True, "force_row_wise": True, "num_threads": 8, "verbose": -1}


def ridge_matrix(frame, features, eligible):
    ref = frame[features].where(eligible)
    mean = ref.groupby(frame.origin).transform("mean")
    sd = ref.groupby(frame.origin).transform("std")
    return ((frame[features] - mean) / sd.where(sd > 0)).fillna(0).clip(-5, 5).to_numpy()


def ridge_fit(x, y, lam):
    return np.linalg.solve(x.T @ x + lam * np.eye(x.shape[1]), x.T @ y)


def rel_mae(pred, target, origin):
    frame = pd.DataFrame({"p": np.asarray(pred), "t": np.asarray(target), "o": np.asarray(origin)})
    frame[["p", "t"]] -= frame.groupby("o")[["p", "t"]].transform("mean")
    return (frame.p - frame.t).abs().groupby(frame.o).mean().mean()


def inner_masks(train):
    origins = np.sort(train.mi.unique()); validation = origins[-24:]
    return (train.mi.add(3).le(validation[0]).to_numpy(), train.mi.isin(validation).to_numpy())


def choose_lambda(train, x):
    fit, validation = inner_masks(train); scores = []
    for lam in RIDGE_GRID:
        beta = ridge_fit(x[fit], train.r.to_numpy()[fit], lam)
        scores.append(rel_mae(x[validation] @ beta, train.r.to_numpy()[validation], train.origin.to_numpy()[validation]))
    return float(RIDGE_GRID[int(np.argmin(scores))])


def difference_ci(values, column):
    return block_bootstrap(values[[column]], stat=lambda x: np.nanmean(x[:, 0]))


parser = argparse.ArgumentParser(); parser.add_argument("--smoke", action="store_true")
args = parser.parse_args(); started = time.time()
target = load_panel(read_structure()); base = add_features(target, "MAIN")
base = base[(base.n_12m >= 1) & base.y.notna()].reset_index(drop=True)
base["eligible"] = base.n_3m >= MIN_ELIGIBLE
base["r"] = base.y - base.y.where(base.eligible).groupby(base.origin).transform("mean")
events = load_rail(); exposure = rail_exposure(events); supply = load_supply()
panel = add_supply_features(add_rail_features(base, events, exposure), supply)
guard_audit = validate_feature_time_guard(panel)
if args.smoke:
    eval_first, eval_last, refit_every, rounds, stopping = 201201, 201312, 12, 50, 10
else:
    eval_first, eval_last, refit_every, rounds, stopping = EVAL_FIRST, EVAL_LAST, REFIT_EVERY, 2000, 100

predictions = []; lambda_rows = []; importance_rows = []
for feature_set, features in SET_FEATURES.items():
    current = panel.copy(); x_all = ridge_matrix(current, features, current.eligible)
    current[["pred_ridge", "pred_lgbm"]] = np.nan; rng = np.random.default_rng(42)
    groups = dict(FEATURE_GROUPS)
    if "RAIL" in feature_set: groups["rail"] = RAIL_FEATURES
    if "SUPPLY" in feature_set: groups["supply"] = SUPPLY_FEATURES
    for t0 in range(ym_to_mi(eval_first), ym_to_mi(eval_last) + 1, refit_every):
        train_mask = (current.eligible & (current.mi + 3 <= t0)).to_numpy()
        pred_mask = ((current.mi >= t0) & (current.mi < t0 + refit_every)
                     & (current.mi <= ym_to_mi(eval_last))).to_numpy()
        train = current[train_mask]; x_train = x_all[train_mask]
        fit, validation = inner_masks(train); lam = choose_lambda(train, x_train)
        beta = ridge_fit(x_train, train.r.to_numpy(), lam)
        booster = lgb.train(LGB_PARAMS, lgb.Dataset(train.loc[fit, features], label=train.loc[fit, "r"]),
                            num_boost_round=rounds,
                            valid_sets=[lgb.Dataset(train.loc[validation, features], label=train.loc[validation, "r"])],
                            callbacks=[lgb.early_stopping(stopping, verbose=False)])
        current.loc[pred_mask, "pred_ridge"] = x_all[pred_mask] @ beta
        current.loc[pred_mask, "pred_lgbm"] = booster.predict(current.loc[pred_mask, features],
                                                                num_iteration=booster.best_iteration)
        lambda_rows.append({"feature_set": feature_set, "refit_origin": int(mi_to_ym(t0)),
                            "n_train": int(train_mask.sum()), "ridge_lambda": lam,
                            "lambda_at_edge": lam in (RIDGE_GRID[0], RIDGE_GRID[-1]),
                            "lgb_best_iteration": booster.best_iteration})
        eval_mask = pred_mask & current.eligible.to_numpy(); evaluated = current[eval_mask]; xe = x_all[eval_mask]
        origins = evaluated.origin.to_numpy()
        baseline = {"ridge": rel_mae(xe @ beta, evaluated.r, origins),
                    "lgbm": rel_mae(booster.predict(evaluated[features]), evaluated.r, origins)}
        perm = np.arange(len(evaluated))
        for origin in np.unique(origins):
            idx = np.flatnonzero(origins == origin); perm[idx] = rng.permutation(idx)
        for group, cols in groups.items():
            indexes = [features.index(col) for col in cols]
            xp = xe.copy(); xp[:, indexes] = xe[perm][:, indexes]
            raw = evaluated[features].copy(); raw[cols] = evaluated[cols].to_numpy()[perm]
            importance_rows.append({"feature_set": feature_set, "refit_origin": int(mi_to_ym(t0)), "group": group,
                                    "n_eval_origins": len(np.unique(origins)),
                                    "ridge": rel_mae(xp @ beta, evaluated.r, origins) - baseline["ridge"],
                                    "lgbm": rel_mae(booster.predict(raw), evaluated.r, origins) - baseline["lgbm"]})
    keep = ["dong", "sggCd", "origin", "r", "eligible", "pred_ridge", "pred_lgbm"]
    predictions.append(current.loc[current.origin.between(eval_first, eval_last), keep].assign(feature_set=feature_set))

pred = pd.concat(predictions, ignore_index=True)
# 모델별 기점 지표를 long table로 만든 뒤 MAIN과 paired difference를 계산한다.
metrics = {}
for feature_set, part in pred[pred.eligible].groupby("feature_set"):
    for model in ("ridge", "lgbm"):
        metrics[(feature_set, model)] = origin_metrics(part, f"pred_{model}", y="r")
summary_rows = []
periods = ({"2012-2019": PERIODS["2012-2019"]} if args.smoke
           else {k: v for k, v in PERIODS.items() if k != "all"})
for feature_set in SET_FEATURES:
    for model in ("ridge", "lgbm"):
        current = metrics[(feature_set, model)]; main = metrics[("MAIN", model)]
        for period in periods:
            mask = in_period(current.index, period); cur = current[mask]; ref = main[mask]
            r0 = pred[(pred.feature_set == feature_set) & pred.eligible].copy()
            r0["zero"] = 0.; r0m = origin_metrics(r0, "zero", y="r"); r0m = r0m[in_period(r0m.index, period)]
            improve_r0 = 1 - cur.rel_mae.mean() / r0m.rel_mae.mean()
            rel_diff = pd.DataFrame({"value": cur.rel_mae - ref.rel_mae})
            rho_diff = pd.DataFrame({"value": cur.spearman - ref.spearman})
            d, dlo, dhi = difference_ci(rel_diff, "value")
            rd, rdlo, rdhi = difference_ci(rho_diff.dropna(), "value")
            summary_rows.append({"feature_set": feature_set, "period": period, "model": model,
                                 "n_origins": len(cur), "mean_dongs": cur.n_dongs.mean(),
                                 "rel_mae": cur.rel_mae.mean(), "rel_mae_improve_vs_R0": improve_r0,
                                 "rel_mae_improve_vs_MAIN": 1 - cur.rel_mae.mean() / ref.rel_mae.mean(),
                                 "rel_mae_diff_vs_MAIN": d, "rel_mae_diff_ci_lo": dlo, "rel_mae_diff_ci_hi": dhi,
                                 "spearman": cur.spearman.mean(), "spearman_diff_vs_MAIN": rd,
                                 "spearman_diff_ci_lo": rdlo, "spearman_diff_ci_hi": rdhi})

importance = pd.DataFrame(importance_rows)
for col in ("ridge", "lgbm"): importance[col] *= importance.n_eval_origins
importance = importance.groupby(["feature_set", "group"])[["ridge", "lgbm", "n_eval_origins"]].sum()
importance[["ridge", "lgbm"]] = importance[["ridge", "lgbm"]].div(importance.n_eval_origins, axis=0)
importance = importance.drop(columns="n_eval_origins").reset_index()
unmatched_rows, unmatched_dongs = supply_match_counts(supply)
line_excluded = sum(1 for _ in open(RAIL_LINE_PATH, encoding="utf-8")) - 1
qc = guard_audit.copy()
for column in ("rail_max_public_mi", "rail_allowed_mi", "supply_max_completion_mi", "supply_allowed_mi"):
    qc[column.replace("_mi", "_ym")] = qc[column].map(
        lambda value: int(mi_to_ym(value)) if pd.notna(value) else np.nan)
qc = qc.drop(columns=[c for c in qc if c.endswith("_mi")])
qc["unmatched_supply_rows"] = unmatched_rows; qc["unmatched_supply_dongs"] = unmatched_dongs
qc["line_events_excluded"] = line_excluded; qc["scheduled_open_rows_excluded"] = 34
qc["runtime_seconds"] = time.time() - started
suffix = ".smoke" if args.smoke else ""
paths = [OUTPUT_DIR / f"68.1{suffix}.comparison.txt", OUTPUT_DIR / f"68.2{suffix}.permutation_importance.txt",
         OUTPUT_DIR / f"68.3{suffix}.predictions.txt", OUTPUT_DIR / f"68.4{suffix}.ridge_lambda.txt",
         OUTPUT_DIR / f"68.5{suffix}.qc.txt"]
pd.DataFrame(summary_rows).to_csv(paths[0], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
importance.to_csv(paths[1], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
pred.to_csv(paths[2], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
pd.DataFrame(lambda_rows).to_csv(paths[3], sep="\t", index=False, lineterminator="\n")
qc.to_csv(paths[4], sep="\t", index=False, lineterminator="\n", float_format="%.3f")
print(pd.DataFrame(summary_rows).to_string(index=False)); print(f"===== 68 완료 ({time.time() - started:.1f}초) =====")
for path in paths: print(path)
