# ============================================================================
# 48.evaluate_realtime_two_stage.py
# ============================================================================
# Author:      yjkim
# Purpose:     real-time target의 two-stage rolling OOT 결과를 탐색적으로 요약한다
# ============================================================================

import itertools
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HORIZONS = [2, 4, 8, 12]
GAMMAS = [0, 0.25, 0.5, 0.75, 1]
MARKET_FEATURES = ["momentum_gap", "rate_chg_4q", "S_sale_vol_chg_4q"]
RELATIVE_R1 = ["mom_1q_rel", "mom_4q_rel", "mom_12q_rel", "price_rank", "jeonse_ratio_rel", "sale_vol_chg_rel"]
RELATIVE_R2 = RELATIVE_R1 + ["old30_share_4q", "median_age_4q", "jeonse_share_4q", "rent_n_log_change_4q", "mom_2q_gu_rel", "mom_8q_gu_rel"]
MARKET_RIDGE_ALPHA = 10
RELATIVE_RIDGE_ALPHA = 10
LIGHTGBM_LAMBDA_L2 = 5
SEED = 20260915


def quarter(value):
    return value if isinstance(value, pd.Period) else pd.Period(value, freq="Q")


def origin_quarters(frame):
    """prediction_origin을 Period로 바꿔 둔다. 평가 루프가 같은 프레임을 수백 번 훑으므로 조합마다 다시 변환하지 않는다."""
    return pd.PeriodIndex(frame["prediction_origin"], freq="Q").to_series(index=frame.index)


def fit_ridge(frame, features, target, alpha):
    """제곱합 손실 기준의 표준화 ridge를 적합한다."""
    x = frame[features].to_numpy(dtype=float)
    y = frame[target].to_numpy(dtype=float)
    mean, std = np.nanmean(x, axis=0), np.nanstd(x, axis=0, ddof=0)
    mean = np.where(np.isfinite(mean), mean, 0.0)
    std = np.where(np.isfinite(std) & (std > 0), std, 1.0)
    z = (np.nan_to_num(x, nan=0.0) - mean) / std
    b = float(np.mean(y))
    coef = np.linalg.solve(z.T @ z + alpha * np.eye(len(features)), z.T @ (y - b))
    return {"features": features, "mean": mean, "std": std, "coef": coef, "intercept": b, "alpha": alpha}


def predict_ridge(model, frame):
    x = frame[model["features"]].to_numpy(dtype=float)
    z = (np.nan_to_num(x, nan=0.0) - model["mean"]) / model["std"]
    return model["intercept"] + z @ model["coef"]


def choose_gamma(history, origin, horizon):
    """기점 동일 가중 MAE의 최소 gamma를 고른다."""
    usable = history[(history["origin"] + horizon <= origin) & history["status"].eq("ok")]
    if usable["origin"].nunique() < 8 or len(usable) < 1000:
        return 0.0
    scores = []
    for gamma in GAMMAS:
        per_origin = usable.assign(error=(gamma * usable["centered"] - usable["r_rt"]).abs()).groupby("origin")["error"].mean()
        scores.append((float(per_origin.mean()), gamma))
    return min(scores, key=lambda item: (item[0], item[1]))[1]


def weighted_quantile(values, weights, level):
    """누적 가중치가 level에 처음 도달하는 경험적 분위수다."""
    values, weights = np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    return float(values[np.flatnonzero(np.cumsum(weights) >= weights.sum() * level)[0]])


def moving_block_bootstrap(differences, block_length, n_boot=2000, seed=42):
    """결측 없는 연속 block만 사용하는 non-circular moving-block bootstrap이다."""
    values = np.asarray(differences, dtype=float)
    valid_starts = [i for i in range(len(values) - block_length + 1) if np.isfinite(values[i:i + block_length]).all()]
    if not valid_starts:
        return (np.nan, np.nan, np.nan, 0)
    # draw × block 인덱스를 한 번에 만들어 평균한다. block을 이어붙인 뒤 원 길이만큼 자르는 규칙은 그대로다.
    rng = np.random.default_rng(seed)
    n_blocks = -(-len(values) // block_length)
    starts = np.asarray(valid_starts)[rng.integers(len(valid_starts), size=(n_boot, n_blocks))]
    index = (starts[:, :, None] + np.arange(block_length)).reshape(n_boot, -1)[:, :len(values)]
    draws = values[index].mean(axis=1)
    return (float(np.mean(differences[np.isfinite(differences)])), *np.percentile(draws, [2.5, 97.5], method="linear"), n_boot)


def assert_prediction_lineage(frame):
    active = frame[frame["market_max_label_vintage"].notna()]
    assert (pd.PeriodIndex(active["market_max_label_vintage"], freq="Q") <= pd.PeriodIndex(active["prediction_origin"], freq="Q")).all()
    active = frame[frame["relative_max_label_vintage"].notna()]
    assert (pd.PeriodIndex(active["relative_max_label_vintage"], freq="Q") <= pd.PeriodIndex(active["prediction_origin"], freq="Q")).all()


def lgb_params():
    return {"objective": "regression_l1", "metric": "l1", "verbosity": -1, "num_leaves": 15,
            "min_data_in_leaf": 100, "learning_rate": 0.03, "feature_fraction": 0.7, "bagging_fraction": 0.8,
            "bagging_freq": 1, "lambda_l2": LIGHTGBM_LAMBDA_L2, "seed": SEED, "bagging_seed": SEED,
            "feature_fraction_seed": SEED, "data_random_seed": SEED, "deterministic": True,
            "force_row_wise": True, "num_threads": 8}


def read_inputs(root):
    out = root / "output"
    vintage = pd.read_csv(out / "47.1.vintage_momentum_all.txt", sep="\t", dtype={"dong": str, "sggCd": str, "umdNm": str})
    targets = pd.read_csv(out / "47.2.realtime_targets.txt", sep="\t", dtype={"dong": str, "sggCd": str}, keep_default_na=False)
    market = pd.read_csv(out / "47.3.seoul_market_panel.txt", sep="\t")
    relative = pd.read_csv(out / "47.4.dong_relative_features.txt", sep="\t", dtype={"dong": str, "sggCd": str})
    for frame, col in [(vintage, "as_of_quarter"), (targets, "origin"), (market, "origin"), (relative, "origin")]:
        frame[col] = pd.PeriodIndex(frame[col], freq="Q")
    for col in ["y_rt", "y_full", "horizon_q"]:
        targets[col] = pd.to_numeric(targets[col], errors="coerce")
    targets["target_observed"] = targets["target_observed"].astype(str).eq("True")
    return vintage, targets, market, relative


def make_relative_training(relative, targets, market, horizon, before_or_equal):
    target = targets[(targets["horizon_q"] == horizon) & targets["target_observed"] & (targets["origin"] <= before_or_equal)].copy()
    target = target.merge(market[["origin", f"M_rt_h{horizon}"]], on="origin", how="left")
    target["r_rt"] = target["y_rt"] - target[f"M_rt_h{horizon}"]
    return target.merge(relative, on=["dong", "sggCd", "origin"], how="inner")


def build_predictions(vintage, targets, market, relative):
    records, histories = [], {name: pd.DataFrame(columns=["origin", "centered", "r_rt", "status"]) for name in ["R1", "R2"]}
    origins = pd.period_range("2008Q1", "2026Q2", freq="Q")
    for horizon in HORIZONS:
        for pos, origin in enumerate(origins):
            e = vintage[(vintage["as_of_quarter"] == origin) & vintage["eligible"].astype(str).eq("True")].copy()
            if e.empty: continue
            e = e.merge(targets[(targets["origin"] == origin) & (targets["horizon_q"] == horizon)], on=["dong", "sggCd"], how="left")
            e = e.drop(columns=["mom_2q_gu_rel", "mom_8q_gu_rel"], errors="ignore")
            e = e.merge(relative[relative["origin"] == origin].drop(columns="origin"), on=["dong", "sggCd"], how="left")
            mrow = market[market["origin"] == origin].iloc[0]
            eligible_origins = market[(market["origin"] + horizon <= origin) & market[f"M_rt_h{horizon}"].notna()]
            market_predictions = {}
            for name, extras in [("M0", []), ("M1", []), ("M2", ["overheated_share"]), ("M3", ["policy_net_4q"])]:
                baseline = float(mrow[f"S_mom_{horizon}q"])
                status, model = "baseline", None
                if name != "M0":
                    train = eligible_origins.copy()
                    train["momentum_gap"] = train["S_mom_1q"] - train["S_mom_4q"]
                    cols = MARKET_FEATURES + extras
                    if len(train) >= 12:
                        train["target"] = train[f"M_rt_h{horizon}"] - train[f"S_mom_{horizon}q"]
                        model, status = fit_ridge(train, cols, "target", MARKET_RIDGE_ALPHA), "ok"
                        one = pd.DataFrame([dict(mrow)])
                        one["momentum_gap"] = one["S_mom_1q"] - one["S_mom_4q"]
                        value = baseline + float(predict_ridge(model, one)[0])
                    else: value, status = baseline, "insufficient_train"
                else: value = baseline
                market_predictions[name] = (value, status, len(eligible_origins),
                                            str(eligible_origins["origin"].max()) if len(eligible_origins) else np.nan,
                                            str((eligible_origins["origin"].max() + horizon)) if len(eligible_origins) else np.nan)
            relative_predictions = {"R0": (np.zeros(len(e)), "baseline", 0, 0, np.nan, np.nan, 0.0)}
            for name, cols in [("R1", RELATIVE_R1), ("R2", RELATIVE_R2)]:
                train = make_relative_training(relative, targets, market, horizon, origin - horizon)
                n_origins, n_rows = train["origin"].nunique(), len(train)
                if origin < pd.Period("2011Q4", freq="Q"):
                    raw, status = np.zeros(len(e)), "no_features"
                elif n_origins < 8 or n_rows < 1500:
                    raw, status = np.zeros(len(e)), "insufficient_train"
                elif name == "R1":
                    model = fit_ridge(train, cols, "r_rt", RELATIVE_RIDGE_ALPHA)
                    raw, status = predict_ridge(model, e), "ok"
                else:
                    model = lgb.train(lgb_params(), lgb.Dataset(train[cols], train["r_rt"]), num_boost_round=300)
                    raw, status = model.predict(e[cols]), "ok"
                centered = raw - np.mean(raw)
                assert abs(np.mean(centered)) < 1e-9
                gamma = choose_gamma(histories[name], origin, horizon)
                relative_predictions[name] = (centered, status, n_origins, n_rows,
                                              str(train["origin"].max()) if n_origins else np.nan,
                                              str((train["origin"].max() + horizon)) if n_origins else np.nan, gamma)
                now = e[["origin", "dong"]].copy(); now["origin"] = origin; now["centered"] = centered
                now["r_rt"] = e["y_rt"] - mrow[f"M_rt_h{horizon}"]; now["status"] = status
                histories[name] = pd.concat([histories[name], now[["origin", "centered", "r_rt", "status"]]], ignore_index=True)
            def append_variant(variant, m_name, r_name, baseline=False):
                mhat, mstatus, mn, mmax, mlabel = market_predictions[m_name]
                centered, rstatus, rn, rr, rmax, rlabel, gamma = relative_predictions[r_name]
                if variant == "B1":
                    raw = e[f"mom_{horizon}q"].to_numpy() - float(mrow[f"S_mom_{horizon}q"]); centered, gamma = raw, 1.0
                    mstatus, rstatus, mn, rn, rr = "baseline", "baseline", np.nan, np.nan, np.nan
                if variant == "B2": mstatus, rstatus, mn, rn, rr, gamma = "baseline", "baseline", np.nan, np.nan, np.nan, 0.0
                result = e[["dong", "sggCd", "origin", "target_observed", "y_rt", "y_full"]].copy()
                result["prediction_origin"], result["horizon_q"], result["variant"] = str(origin), horizon, variant
                result["market_model"], result["market_status"] = m_name if not baseline else "baseline", mstatus
                result["relative_model"], result["r_model_status"] = r_name if not baseline else "baseline", rstatus
                result["in_T"] = result.pop("target_observed")
                result["M_hat"], result["M_rt"] = mhat, mrow[f"M_rt_h{horizon}"]
                result["r_hat_raw"], result["r_hat_centered"], result["gamma"] = centered, centered, gamma
                result["y_hat"] = mhat + gamma * centered
                result["market_n_train_origins"], result["market_max_train_origin"], result["market_max_label_vintage"] = mn, mmax, mlabel
                result["market_ridge_alpha"] = MARKET_RIDGE_ALPHA if m_name != "M0" else np.nan
                result["relative_n_train_origins"], result["relative_n_train_rows"] = rn, rr
                result["relative_max_train_origin"], result["relative_max_label_vintage"] = rmax, rlabel
                result["relative_ridge_alpha"] = RELATIVE_RIDGE_ALPHA if r_name == "R1" else np.nan
                result["lightgbm_lambda_l2"] = LIGHTGBM_LAMBDA_L2 if r_name == "R2" else np.nan
                for col in ["lower", "upper", "n_calibration_origins", "n_calibration_rows"]: result[col] = np.nan
                records.append(result)
            append_variant("B1", "M0", "R0", True); append_variant("B2", "M0", "R0", True)
            for m, r in itertools.product(["M0", "M1", "M2", "M3"], ["R0", "R1", "R2"]): append_variant(f"{m}_{r}", m, r)
            print(f"처리 중 h={horizon} [{pos + 1}/{len(origins)}]: {origin} (E {len(e):,})")
    predictions = pd.concat(records, ignore_index=True)
    assert_prediction_lineage(predictions)
    assert not predictions.duplicated(["dong", "prediction_origin", "horizon_q", "variant"]).any()
    return predictions


def metric_rows(predictions):
    rows = []
    origin_q = origin_quarters(predictions)
    segments = {"tuning": ("2016Q1", "2020Q4"), "recent": ("2021Q1", "2025Q2"), "all": ("2016Q1", "2025Q2")}
    for h, segment, basis, variant in itertools.product(HORIZONS, segments, ["rt", "full"], predictions["variant"].unique()):
        lo, hi = map(quarter, segments[segment]); col = f"y_{basis}"
        scored = predictions[(predictions["horizon_q"] == h) & origin_q.between(lo, hi) & predictions[col].notna() & predictions["in_T"]]
        scored = scored[scored["variant"] == variant].copy()
        if scored.empty: continue
        per = scored.assign(error=(scored["y_hat"] - scored[col]).abs()).groupby("prediction_origin")["error"].mean()
        market_target = scored.groupby("prediction_origin")[col].mean() if basis == "rt" else scored.groupby("prediction_origin")[col].mean()
        market_hat = scored.groupby("prediction_origin")["M_hat"].first()
        rel_actual = scored[col] - scored["prediction_origin"].map(market_target)
        rel_pred = scored["gamma"] * scored["r_hat_centered"]
        corrs = scored.assign(actual=rel_actual, pred=rel_pred).groupby("prediction_origin").apply(lambda x: x["actual"].corr(x["pred"]), include_groups=False)
        values = {"mae_origin": per.mean(), "mae_row": (scored["y_hat"] - scored[col]).abs().mean(),
                  "market_mae": (market_hat - market_target).abs().mean(), "relative_mae": (rel_pred-rel_actual).abs().groupby(scored["prediction_origin"]).mean().mean(),
                  "relative_corr": corrs.mean(), "market_sign_hit": (np.sign(market_hat) == np.sign(market_target)).mean()}
        for metric, value in values.items(): rows.append({"horizon_q": h, "segment": segment, "target_basis": basis, "variant": variant, "metric": metric, "value": value, "n_origins": len(per), "n_rows": len(scored)})
    return pd.DataFrame(rows)


def select_and_log(metrics):
    def value(candidate, metric):
        x = metrics[(metrics.horizon_q == 4) & (metrics.segment == "tuning") & (metrics.target_basis == "rt") & (metrics.variant == candidate) & (metrics.metric == metric)]
        return float(x.value.iloc[0]) if len(x) else np.nan
    records = []
    m0, m1 = value("M0_R0", "market_mae"), value("M1_R0", "market_mae")
    selected_m = "M1" if (m0-m1)/m0 >= .02 else "M0"
    for candidate, score in [("M0", m0), ("M1", m1)]: records.append({"record_type":"selection","decision":"market","candidate":candidate,"slice_id":"all","tuning_mae":score,"baseline_mae":m0,"improvement_ratio":(m0-score)/m0,"selected":candidate==selected_m,"reason":"2% 문턱"})
    r_scores = {r: value(f"M0_{r}", "relative_mae") for r in ["R0", "R1", "R2"]}; base = r_scores["R0"]
    candidates = [r for r in ["R1", "R2"] if (base-r_scores[r])/base >= .02]
    selected_r = min(candidates, key=lambda r: (-((base-r_scores[r])/base), ["R0","R1","R2"].index(r))) if candidates else "R0"
    for candidate, score in r_scores.items(): records.append({"record_type":"selection","decision":"relative","candidate":candidate,"slice_id":"all","tuning_mae":score,"baseline_mae":base,"improvement_ratio":(base-score)/base,"selected":candidate==selected_r,"reason":"2% 문턱"})
    return selected_m, selected_r, pd.DataFrame(records)


def add_selection_intervals(predictions, selected_m, selected_r):
    selected_variant = f"{selected_m}_{selected_r}"
    selected = predictions[predictions.variant.eq(selected_variant)].copy(); selected["variant"] = "SEL"
    for h in HORIZONS:
        data = selected[selected.horizon_q.eq(h)]
        for origin in sorted(data.prediction_origin.unique(), key=quarter):
            past = data[(data.prediction_origin.map(quarter) + h <= quarter(origin)) & data.in_T & data.y_rt.notna()].copy()
            take = sorted(past.prediction_origin.unique(), key=quarter)[-8:]; past = past[past.prediction_origin.isin(take)]
            mask = (selected.horizon_q.eq(h) & selected.prediction_origin.eq(origin))
            selected.loc[mask, "n_calibration_origins"], selected.loc[mask, "n_calibration_rows"] = len(take), len(past)
            if len(take) == 8 and len(past) >= 1000:
                weights = 1 / past.groupby("prediction_origin")["dong"].transform("size")
                q = weighted_quantile((past.y_rt-past.y_hat).abs(), weights, .8)
                selected.loc[mask, "lower"], selected.loc[mask, "upper"] = selected.loc[mask,"y_hat"]-q, selected.loc[mask,"y_hat"]+q
    return pd.concat([predictions, selected], ignore_index=True)


def bootstrap_rows(predictions, selected_m, selected_r):
    rows=[]; origin_q=origin_quarters(predictions); selected=f"{selected_m}_{selected_r}"; pairs=[("SEL-B2","SEL","B2","mae_origin"),("SEL-B1","SEL","B1","mae_origin"),("M1-M0","M1_R0","M0_R0","market_mae"),("R1-R0","M0_R1","M0_R0","relative_mae"),("R2-R0","M0_R2","M0_R0","relative_mae")]
    for h, segment, basis, pair in itertools.product(HORIZONS,["tuning","recent","all"],["rt","full"],pairs):
        name,a,b,metric=pair; lo,hi=map(quarter,{"tuning":("2016Q1","2020Q4"),"recent":("2021Q1","2025Q2"),"all":("2016Q1","2025Q2")}[segment]); col=f"y_{basis}"
        window=(predictions.horizon_q==h)&predictions[col].notna()&predictions.in_T&origin_q.between(lo,hi)
        aa=predictions[window&(predictions.variant==a)].copy(); bb=predictions[window&(predictions.variant==b)].copy()
        def by_origin(x):
            if metric=="market_mae": return x.groupby("prediction_origin").apply(lambda z: abs(z.M_hat.iloc[0]-z[col].mean()),include_groups=False)
            if metric=="relative_mae": return x.assign(r=(x[col]-x.groupby("prediction_origin")[col].transform("mean")-x.gamma*x.r_hat_centered).abs()).groupby("prediction_origin").r.mean()
            return x.assign(e=(x.y_hat-x[col]).abs()).groupby("prediction_origin").e.mean()
        diff=by_origin(aa).subtract(by_origin(bb)); grid=pd.period_range(lo,hi,freq="Q"); values=np.array([diff.get(str(q),np.nan) for q in grid])
        for block in [4,6]:
            mean,low,high,n= moving_block_bootstrap(values,block); rows.append({"horizon_q":h,"segment":segment,"target_basis":basis,"comparison":name,"block_length":block,"n_origins":np.isfinite(values).sum(),"n_missing_origins":np.isnan(values).sum(),"mean_diff":mean,"ci_low":low,"ci_high":high,"n_boot":n,"seed":42})
    return pd.DataFrame(rows)


def interval_coverage(predictions):
    rows=[]; origin_q=origin_quarters(predictions)
    for h,segment in itertools.product(HORIZONS,["tuning","recent","all"]):
        lo,hi=map(quarter,{"tuning":("2016Q1","2020Q4"),"recent":("2021Q1","2025Q2"),"all":("2016Q1","2025Q2")}[segment]); x=predictions[(predictions.variant=="SEL")&(predictions.horizon_q==h)&predictions.y_rt.notna()&predictions.lower.notna()&origin_q.between(lo,hi)]
        rows.append({"horizon_q":h,"segment":segment,"n_origins_with_interval":x.prediction_origin.nunique(),"n_rows":len(x),"coverage":((x.y_rt>=x.lower)&(x.y_rt<=x.upper)).mean(),"median_half_width":((x.upper-x.lower)/2).median()})
    return pd.DataFrame(rows)


def main():
    root=Path(__file__).resolve().parents[2]; out=root/"output"; vintage,targets,market,relative=read_inputs(root)
    predictions=build_predictions(vintage,targets,market,relative); metrics=metric_rows(predictions); sm,sr,log=select_and_log(metrics)
    predictions=add_selection_intervals(predictions,sm,sr); metrics=metric_rows(predictions)
    # basis별 모든 variant가 동일한 평가 행을 쓴다.
    origin_q=origin_quarters(predictions)
    for h,seg,basis in itertools.product(HORIZONS,["tuning","recent","all"],["rt","full"]):
        lo,hi=map(quarter,{"tuning":("2016Q1","2020Q4"),"recent":("2021Q1","2025Q2"),"all":("2016Q1","2025Q2")}[seg]); sets=[]
        for variant in predictions.variant.unique():
            x=predictions[(predictions.horizon_q==h)&(predictions.variant==variant)&predictions[f"y_{basis}"].notna()&predictions.in_T&origin_q.between(lo,hi)]; sets.append(set(zip(x.dong,x.prediction_origin)))
        assert all(s==sets[0] for s in sets)
    boot=bootstrap_rows(predictions,sm,sr); coverage=interval_coverage(predictions)
    predictions.to_csv(out/"48.1.predictions.txt",sep="\t",index=False,lineterminator="\n"); metrics.to_csv(out/"48.2.metrics.txt",sep="\t",index=False,lineterminator="\n"); boot.to_csv(out/"48.3.bootstrap.txt",sep="\t",index=False,lineterminator="\n"); log.to_csv(out/"48.4.selection_log.txt",sep="\t",index=False,lineterminator="\n"); coverage.to_csv(out/"48.5.interval_coverage.txt",sep="\t",index=False,lineterminator="\n")
    print("===== 48 평가 완료 ====="); print(log.to_string(index=False)); print(f"예측: {out/'48.1.predictions.txt'}")


if __name__ == "__main__": main()
