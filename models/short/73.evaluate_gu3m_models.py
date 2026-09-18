# ============================================================================
# 73.evaluate_gu3m_models.py
# ============================================================================
# Purpose: 자치구 3개월 상대 가격 baseline·Ridge·LightGBM을 rolling-origin으로 평가한다
# 실행: .venv/bin/python models/short/73.evaluate_gu3m_models.py [--smoke]
# ============================================================================

import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from _gu3m import (RIDGE_GRID, add_intervals, aggregate_gu, block_bootstrap, center_by_origin,
                   choose_lambda, origin_metrics, ridge_fit, zscore_by_origin)
from _short_eval import FEATURES, add_features
from _short_index import LAST_PILOT_ORIGIN, OUTPUT_DIR, mi_to_ym, publication_lag, ym_to_mi

SMOKE = "--smoke" in sys.argv
SUFFIX = ".smoke" if SMOKE else ""
EVAL_FIRST, EVAL_LAST, REFIT_EVERY = 201201, LAST_PILOT_ORIGIN, 12
PERIODS = {"all": (201201, 202501), "2012-2019": (201201, 201912), "2020-2025.01": (202001, 202501)}
LGB_PARAMS = {"objective": "regression", "metric": "l1", "learning_rate": .03, "num_leaves": 10,
              "min_data_in_leaf": 20, "feature_fraction": .8, "lambda_l2": 1., "seed": 42,
              "feature_fraction_seed": 42, "bagging_seed": 42, "data_random_seed": 42,
              "deterministic": True, "force_row_wise": True, "num_threads": 8, "verbose": -1}

started = time.time()
dong = pd.read_csv(OUTPUT_DIR / "61.1.origin_panel.txt", sep="\t", dtype={"sggCd": str})
dong = dong[(dong["structure"] == "B") & (dong["origin"] <= EVAL_LAST)].copy()
assert dong["origin"].max() <= LAST_PILOT_ORIGIN
dong["mi"] = ym_to_mi(dong["origin"])
dong["eligible"] = dong["n_3m"] >= 10
featured = add_features(dong, "MAIN")
lag = publication_lag(featured["mi"].to_numpy())
assert (featured["local_max_sale_mi"] <= featured["mi"] - 3).all()
assert (featured["forecast_max_sale_mi"] <= featured["mi"] - lag).all()

value_cols = list(dict.fromkeys(["y", "gu_mom_0_3", "seoul_mom_0_3"] + FEATURES))
panel = aggregate_gu(featured, value_cols)
panel["r"] = panel["y"] - panel.groupby("origin")["y"].transform("mean")
panel["pred_gu_momentum"] = panel["gu_mom_0_3"] - panel.groupby("origin")["gu_mom_0_3"].transform("mean")
# 서울 momentum은 같은 origin의 모든 구에 동일하므로 상대 예측으로 바꾸면 정확히 0이다.
panel["pred_seoul_implied"] = 0.
panel["mi"] = ym_to_mi(panel["origin"])
panel["pred_R0"] = 0.
panel[["pred_ridge", "pred_lgbm"]] = np.nan
x_ridge = zscore_by_origin(panel, FEATURES).to_numpy()

first_prediction = ym_to_mi(EVAL_FIRST)
if SMOKE:
    first_prediction = ym_to_mi(EVAL_LAST) - 11
tuning = []
for t0 in range(first_prediction, ym_to_mi(EVAL_LAST) + 1, REFIT_EVERY):
    train_mask = (panel["mi"] + 3 <= t0).to_numpy()
    pred_mask = ((panel["mi"] >= t0) & (panel["mi"] < t0 + REFIT_EVERY) & (panel["mi"] <= ym_to_mi(EVAL_LAST))).to_numpy()
    train = panel[train_mask]
    x_train = x_ridge[train_mask]
    lam, fit, val = choose_lambda(train, x_train)
    beta = ridge_fit(x_train, train["r"].to_numpy(), lam)
    booster = lgb.train(LGB_PARAMS, lgb.Dataset(train.loc[fit, FEATURES], label=train.loc[fit, "r"]),
                        num_boost_round=2000,
                        valid_sets=[lgb.Dataset(train.loc[val, FEATURES], label=train.loc[val, "r"])],
                        callbacks=[lgb.early_stopping(100, verbose=False)])
    panel.loc[pred_mask, "pred_ridge"] = x_ridge[pred_mask] @ beta
    panel.loc[pred_mask, "pred_lgbm"] = booster.predict(panel.loc[pred_mask, FEATURES], num_iteration=booster.best_iteration)
    tuning.append({"refit_origin": int(mi_to_ym(t0)), "n_train": int(train_mask.sum()), "ridge_lambda": lam,
                   "lambda_at_edge": lam in (RIDGE_GRID[0], RIDGE_GRID[-1]), "lgb_best_iteration": booster.best_iteration})

evaluation = panel[panel["origin"].between(int(mi_to_ym(first_prediction)), EVAL_LAST)].copy()
methods = ["pred_R0", "pred_seoul_implied", "pred_gu_momentum", "pred_ridge", "pred_lgbm"]
per_origin = []
for method in methods:
    metrics = origin_metrics(evaluation, method).join(add_intervals(evaluation, method), how="left")
    per_origin.append(metrics.assign(method=method).reset_index())
per_origin = pd.concat(per_origin, ignore_index=True)

summary_rows = []
for period, (lo, hi) in PERIODS.items():
    if SMOKE and period != "all":
        continue
    part_all = per_origin[per_origin["origin"].between(max(lo, int(mi_to_ym(first_prediction))), hi)]
    reference = part_all[part_all["method"] == "pred_R0"].sort_values("origin")
    for method in methods:
        part = part_all[part_all["method"] == method].sort_values("origin")
        if part.empty:
            continue
        paired = np.column_stack([part["rel_mae"], reference["rel_mae"]])
        improvement = block_bootstrap(paired, stat=lambda x: 1 - x[:, 0].mean() / x[:, 1].mean())
        finite_rho = part["spearman"].dropna().to_numpy()
        rho = block_bootstrap(finite_rho) if len(finite_rho) >= 6 else (np.nan,) * 3
        summary_rows.append({"period": period, "model": method, "n_origins": len(part), "mean_gu": part["n_gu"].mean(),
                             "rel_mae": part["rel_mae"].mean(), "improve_vs_R0": improvement[0],
                             "improve_ci_lo": improvement[1], "improve_ci_hi": improvement[2],
                             "n_spearman_origins": len(finite_rho), "spearman": rho[0],
                             "spearman_ci_lo": rho[1], "spearman_ci_hi": rho[2],
                             "direction_accuracy": part["direction_accuracy"].mean(),
                             "coverage_80": part["coverage"].mean(), "interval_width": part["interval_width"].mean()})
summary = pd.DataFrame(summary_rows)
kill_candidates = summary[(summary["period"] == "all") & summary["model"].isin(["pred_ridge", "pred_lgbm"])]
kill = kill_candidates.assign(kill=lambda d: (
    ((d["improve_vs_R0"] < .02) | ((d["improve_ci_lo"] <= 0) & (d["improve_ci_hi"] >= 0)))
    & (d["spearman_ci_lo"].isna() | (d["spearman_ci_lo"] <= .10))))

paths = {"summary": OUTPUT_DIR / f"73.1.gu3m_summary{SUFFIX}.txt",
         "origin": OUTPUT_DIR / f"73.2.gu3m_by_origin{SUFFIX}.txt",
         "predictions": OUTPUT_DIR / f"73.3.gu3m_predictions{SUFFIX}.txt",
         "tuning": OUTPUT_DIR / f"73.4.gu3m_tuning{SUFFIX}.txt",
         "kill": OUTPUT_DIR / f"73.5.gu3m_kill{SUFFIX}.txt"}
summary.to_csv(paths["summary"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
per_origin.to_csv(paths["origin"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
evaluation[["origin", "sggCd", "n_dongs", "r"] + methods].to_csv(paths["predictions"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
pd.DataFrame(tuning).to_csv(paths["tuning"], sep="\t", index=False, lineterminator="\n")
kill.to_csv(paths["kill"], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
print(summary.to_string(index=False, float_format="%.4f"))
print("kill=" + ", ".join(f"{row.model}:{bool(row.kill)}" for row in kill.itertuples()))
print(f"73 runtime_seconds={time.time() - started:.2f}")
for path in paths.values():
    print(path)
