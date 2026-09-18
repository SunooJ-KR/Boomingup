# ============================================================================
# 64.evaluate_relative_models.py
# ============================================================================
# Author:      yjkim
# Purpose:     MAIN·SENS_LAG·SENS_CURRENT feature set으로 동 상대 변화를 평가한다
# Description: expanding window, 12개 기점마다 refit, s+3≤t purge를 적용한다.
# ============================================================================
import time
import lightgbm as lgb
import numpy as np
import pandas as pd
from _short_eval import (EVAL_FIRST, EVAL_LAST, FEATURE_GROUPS, FEATURES, PERIODS, add_features,
                         block_bootstrap, in_period, load_panel, origin_metrics, read_structure)
from _short_index import OUTPUT_DIR, mi_to_ym, ym_to_mi

MIN_ELIGIBLE, REFIT_EVERY = 10, 12
RIDGE_GRID = np.logspace(-2, 7, 10)
FEATURE_SETS = ("MAIN", "SENS_LAG", "SENS_CURRENT")
LGB_PARAMS = {"objective": "regression", "metric": "l1", "learning_rate": .03, "num_leaves": 15,
              "min_data_in_leaf": 100, "feature_fraction": .8, "lambda_l2": 1., "seed": 42,
              "feature_fraction_seed": 42, "bagging_seed": 42, "data_random_seed": 42,
              "deterministic": True, "force_row_wise": True, "num_threads": 8, "verbose": -1}

def zscore(frame, eligible):
    ref = frame[FEATURES].where(eligible)
    mean = ref.groupby(frame.origin).transform("mean"); sd = ref.groupby(frame.origin).transform("std")
    return ((frame[FEATURES] - mean) / sd.where(sd > 0)).fillna(0).clip(-5, 5).to_numpy()

def ridge_fit(x, y, lam):
    return np.linalg.solve(x.T @ x + lam * np.eye(x.shape[1]), x.T @ y)

def rel_mae(pred, target, origin):
    frame = pd.DataFrame({"p": np.asarray(pred), "t": np.asarray(target), "o": np.asarray(origin)})
    frame[["p", "t"]] -= frame.groupby("o")[["p", "t"]].transform("mean")
    return (frame.p - frame.t).abs().groupby(frame.o).mean().mean()

def inner_masks(train):
    origins = np.sort(train.mi.unique()); val_origins = origins[-24:]; val_start = val_origins[0]
    return (train.mi.add(3).le(val_start).to_numpy(), train.mi.isin(val_origins).to_numpy())

def choose_lambda(train, x):
    fit, val = inner_masks(train); scores = []
    for lam in RIDGE_GRID:
        beta = ridge_fit(x[fit], train.r.to_numpy()[fit], lam)
        scores.append(rel_mae(x[val] @ beta, train.r.to_numpy()[val], train.origin.to_numpy()[val]))
    return float(RIDGE_GRID[int(np.argmin(scores))])

started = time.time(); structure = read_structure(); target = load_panel(structure)
all_summary, all_importance, all_predictions, lambdas = [], [], [], []
for feature_set in FEATURE_SETS:
    panel = add_features(target, feature_set)
    panel = panel[(panel.n_12m >= 1) & panel.y.notna()].reset_index(drop=True)
    panel["eligible"] = panel.n_3m >= MIN_ELIGIBLE
    panel["r"] = panel.y - panel.y.where(panel.eligible).groupby(panel.origin).transform("mean")
    x_all = zscore(panel, panel.eligible); panel[["pred_ridge", "pred_lgbm"]] = np.nan
    importance_rows = []; rng = np.random.default_rng(42)
    for t0 in range(ym_to_mi(EVAL_FIRST), ym_to_mi(EVAL_LAST) + 1, REFIT_EVERY):
        train_mask = (panel.eligible & (panel.mi + 3 <= t0)).to_numpy()
        pred_mask = ((panel.mi >= t0) & (panel.mi < t0 + REFIT_EVERY) &
                     (panel.mi <= ym_to_mi(EVAL_LAST))).to_numpy()
        train, x_train = panel[train_mask], x_all[train_mask]
        fit, val = inner_masks(train); lam = choose_lambda(train, x_train)
        beta = ridge_fit(x_train, train.r.to_numpy(), lam)
        booster = lgb.train(LGB_PARAMS, lgb.Dataset(train.loc[fit, FEATURES], label=train.loc[fit, "r"]),
                            num_boost_round=2000,
                            valid_sets=[lgb.Dataset(train.loc[val, FEATURES], label=train.loc[val, "r"])],
                            callbacks=[lgb.early_stopping(100, verbose=False)])
        panel.loc[pred_mask, "pred_ridge"] = x_all[pred_mask] @ beta
        panel.loc[pred_mask, "pred_lgbm"] = booster.predict(panel.loc[pred_mask, FEATURES],
                                                             num_iteration=booster.best_iteration)
        lambdas.append({"feature_set": feature_set, "refit_origin": int(mi_to_ym(t0)),
                        "n_train": int(train_mask.sum()), "ridge_lambda": lam,
                        "lambda_at_edge": lam in (RIDGE_GRID[0], RIDGE_GRID[-1]),
                        "lgb_best_iteration": booster.best_iteration})
        eval_mask = pred_mask & panel.eligible.to_numpy(); eval_rows = panel[eval_mask]; x_eval = x_all[eval_mask]
        origins = eval_rows.origin.to_numpy()
        base = {"ridge": rel_mae(x_eval @ beta, eval_rows.r, origins),
                "lgbm": rel_mae(booster.predict(eval_rows[FEATURES]), eval_rows.r, origins)}
        perm = np.arange(len(eval_rows))
        for origin in np.unique(origins):
            idx = np.flatnonzero(origins == origin); perm[idx] = rng.permutation(idx)
        for group, cols in FEATURE_GROUPS.items():
            indexes = [FEATURES.index(col) for col in cols]
            xp = x_eval.copy(); xp[:, indexes] = x_eval[perm][:, indexes]
            raw = eval_rows[FEATURES].copy(); raw[cols] = eval_rows[cols].to_numpy()[perm]
            importance_rows.append({"feature_set": feature_set, "refit_origin": int(mi_to_ym(t0)),
                                    "group": group, "n_eval_origins": len(np.unique(origins)),
                                    "ridge": rel_mae(xp @ beta, eval_rows.r, origins) - base["ridge"],
                                    "lgbm": rel_mae(booster.predict(raw), eval_rows.r, origins) - base["lgbm"]})
    evaluated = panel[panel.eligible & panel.origin.between(EVAL_FIRST, EVAL_LAST)].copy()
    evaluated["R0_zero"] = 0.; per = {m: origin_metrics(evaluated, m) for m in ("R0_zero", "pred_ridge", "pred_lgbm")}
    for period in PERIODS:
        ref = per["R0_zero"][in_period(per["R0_zero"].index, period)]
        for model, metrics in per.items():
            part = metrics[in_period(metrics.index, period)]
            both = pd.DataFrame({"model": part.rel_mae, "ref": ref.rel_mae})
            imp, ilo, ihi = block_bootstrap(both, stat=lambda d: 1 - d[:, 0].mean() / d[:, 1].mean())
            rho = part.spearman; rest, rlo, rhi = block_bootstrap(rho) if rho.notna().all() else (np.nan,) * 3
            all_summary.append({"feature_set": feature_set, "period": period, "model": model,
                                "n_origins": len(part), "mean_dongs": part.n_dongs.mean(),
                                "rel_mae": part.rel_mae.mean(), "rel_mae_improve_vs_R0": imp,
                                "improve_ci_lo": ilo, "improve_ci_hi": ihi, "spearman": rest,
                                "spearman_ci_lo": rlo, "spearman_ci_hi": rhi})
    all_importance.extend(importance_rows)
    keep = ["dong", "sggCd", "origin", "y", "n_3m", "n_12m", "n_target", "eligible", "pred_ridge", "pred_lgbm"]
    all_predictions.append(panel.loc[panel.origin >= EVAL_FIRST, keep].assign(feature_set=feature_set))

summary = pd.DataFrame(all_summary); importance = pd.DataFrame(all_importance)
for col in ("ridge", "lgbm"): importance[col] *= importance.n_eval_origins
imp_summary = importance.groupby(["feature_set", "group"])[["ridge", "lgbm", "n_eval_origins"]].sum()
imp_summary[["ridge", "lgbm"]] = imp_summary[["ridge", "lgbm"]].div(imp_summary.n_eval_origins, axis=0)
imp_summary = imp_summary.drop(columns="n_eval_origins").reset_index()
paths = {"summary": OUTPUT_DIR / "64.1.relative_model_summary.txt", "importance": OUTPUT_DIR / "64.2.permutation_importance.txt",
         "pred": OUTPUT_DIR / "64.3.predictions.txt", "lambda": OUTPUT_DIR / "64.4.ridge_lambda.txt"}
summary.to_csv(paths["summary"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
imp_summary.to_csv(paths["importance"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
pd.concat(all_predictions).to_csv(paths["pred"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
pd.DataFrame(lambdas).to_csv(paths["lambda"], sep="\t", index=False, lineterminator="\n")
print(summary[summary.model != "R0_zero"].to_string(index=False, float_format="%.4f"))
print(pd.DataFrame(lambdas).groupby("feature_set").lambda_at_edge.agg(["sum", "count"]).to_string())
print(f"===== 64 완료 ({time.time() - started:.0f}초) =====")
for path in paths.values(): print(path)
