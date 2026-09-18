# ============================================================================
# _gu3m.py
# ============================================================================
# Purpose: 자치구 3개월 상대 가격 실험의 집계·평가 공통 함수
# ============================================================================

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

MIN_DONGS = 3
RIDGE_GRID = np.logspace(-2, 7, 10)


def aggregate_gu(frame, value_cols, eligible_col="eligible"):
    """eligible 법정동을 동일가중해 자치구×기점 panel을 만든다."""
    use = frame[frame[eligible_col]].copy()
    counts = use.groupby(["origin", "sggCd"]).size().rename("n_dongs")
    values = use.groupby(["origin", "sggCd"])[value_cols].mean()
    out = values.join(counts).reset_index()
    return out[out["n_dongs"] >= MIN_DONGS].reset_index(drop=True)


def center_by_origin(frame, columns):
    out = frame.copy()
    out[columns] = out[columns] - out.groupby("origin")[columns].transform("mean")
    return out


def zscore_by_origin(frame, columns):
    mean = frame.groupby("origin")[columns].transform("mean")
    sd = frame.groupby("origin")[columns].transform("std").replace(0, np.nan)
    return ((frame[columns] - mean) / sd).fillna(0).clip(-5, 5)


def ridge_fit(x, y, lam):
    return np.linalg.solve(x.T @ x + lam * np.eye(x.shape[1]), x.T @ y)


def relative_mae(pred, target, origin):
    data = pd.DataFrame({"pred": pred, "target": target, "origin": origin})
    data = center_by_origin(data, ["pred", "target"])
    return data.assign(error=(data["pred"] - data["target"]).abs()).groupby("origin")["error"].mean().mean()


def choose_lambda(train, x, target="r", validation_origins=24):
    origins = np.sort(train["mi"].unique())
    if len(origins) <= validation_origins + 3:
        raise ValueError("purged inner validation에 필요한 origin이 부족합니다")
    val_origins = origins[-validation_origins:]
    val_start = val_origins[0]
    fit = train["mi"].add(3).le(val_start).to_numpy()
    val = train["mi"].isin(val_origins).to_numpy()
    scores = []
    for lam in RIDGE_GRID:
        beta = ridge_fit(x[fit], train[target].to_numpy()[fit], lam)
        scores.append(relative_mae(x[val] @ beta, train[target].to_numpy()[val], train["origin"].to_numpy()[val]))
    return float(RIDGE_GRID[int(np.argmin(scores))]), fit, val


def origin_metrics(frame, pred, target="r"):
    def one(group):
        p = group[pred].to_numpy()
        y = group[target].to_numpy()
        rho = spearmanr(p, y).statistic if np.ptp(p) > 0 and len(p) >= 3 else np.nan
        return pd.Series({
            "n_gu": len(group),
            "rel_mae": np.abs(p - y).mean(),
            "spearman": rho,
            "direction_accuracy": np.mean(np.sign(p) == np.sign(y)),
        })
    return frame.groupby("origin")[[pred, target]].apply(one)


def add_intervals(frame, pred, target="r", level=0.8):
    frame = frame.reset_index(drop=True)
    residual = frame[target] - frame[pred]
    rows = []
    for origin, idx in frame.groupby("origin").indices.items():
        mi = int(frame.loc[idx[0], "mi"])
        past = residual[frame["mi"] + 3 <= mi].dropna()
        if len(past) < 100:
            continue
        lo, hi = np.quantile(past, [(1 - level) / 2, 1 - (1 - level) / 2])
        rows.append({"origin": origin, "coverage": ((residual.loc[idx] >= lo) & (residual.loc[idx] <= hi)).mean(),
                     "interval_width": hi - lo})
    return pd.DataFrame(rows).set_index("origin")


def block_bootstrap(values, stat=np.mean, block=6, reps=2000, seed=42):
    array = np.asarray(values)
    n = len(array)
    starts = np.random.default_rng(seed).integers(0, n - block + 1, size=(reps, int(np.ceil(n / block))))
    indexes = (starts[:, :, None] + np.arange(block)).reshape(reps, -1)[:, :n]
    draws = np.asarray([stat(array[index]) for index in indexes])
    return float(stat(array)), float(np.nanquantile(draws, .025)), float(np.nanquantile(draws, .975))


def spearman_brown(correlation):
    return 2 * correlation / (1 + correlation)
