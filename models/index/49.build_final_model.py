# ============================================================================
# 49.build_final_model.py
# ============================================================================
# Author:      yjkim
# Purpose:     선택된 two-stage 설정으로 2026Q2 서비스 행을 계산한다
# ============================================================================

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


def load_evaluator(path):
    spec = importlib.util.spec_from_file_location("realtime_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def selected_models(log):
    select = log[log["record_type"].eq("selection") & log["selected"].astype(str).eq("True")]
    return select.loc[select.decision.eq("market"), "candidate"].iloc[0], select.loc[select.decision.eq("relative"), "candidate"].iloc[0]


def main():
    root = Path(__file__).resolve().parents[2]
    out = root / "output"; model_dir = out / "49.model"; model_dir.mkdir(exist_ok=True)
    ev = load_evaluator(Path(__file__).with_name("48.evaluate_realtime_two_stage.py"))
    vintage, targets, market, relative = ev.read_inputs(root)
    log = pd.read_csv(out / "48.4.selection_log.txt", sep="\t", keep_default_na=False)
    selected_market, selected_relative = selected_models(log)
    origin, horizon = pd.Period("2026Q2", freq="Q"), 4
    e = vintage[(vintage.as_of_quarter == origin) & vintage.eligible.astype(str).eq("True")].copy()
    market_train = market[(market.origin + horizon <= origin) & market[f"M_rt_h{horizon}"].notna()].copy()
    market_train["momentum_gap"] = market_train.S_mom_1q - market_train.S_mom_4q
    mrow = market[market.origin.eq(origin)].iloc[0]
    mhat = float(mrow[f"S_mom_{horizon}q"]); market_model = None
    if selected_market != "M0" and len(market_train) >= 12:
        extras = {"M1": [], "M2": ["overheated_share"], "M3": ["policy_net_4q"]}[selected_market]
        cols = ev.MARKET_FEATURES + extras; market_train["target"] = market_train[f"M_rt_h{horizon}"] - market_train[f"S_mom_{horizon}q"]
        market_model = ev.fit_ridge(market_train, cols, "target", ev.MARKET_RIDGE_ALPHA)
        one = pd.DataFrame([dict(mrow)]); one["momentum_gap"] = one.S_mom_1q - one.S_mom_4q
        mhat += float(ev.predict_ridge(market_model, one)[0])
    relative_model = None; rhat = np.zeros(len(e)); relative_train = ev.make_relative_training(relative, targets, market, horizon, origin-horizon)
    if selected_relative == "R1" and relative_train.origin.nunique() >= 8 and len(relative_train) >= 1500:
        relative_model = ev.fit_ridge(relative_train, ev.RELATIVE_R1, "r_rt", ev.RELATIVE_RIDGE_ALPHA); rhat = ev.predict_ridge(relative_model, e)
    elif selected_relative == "R2" and relative_train.origin.nunique() >= 8 and len(relative_train) >= 1500:
        relative_model = lgb.train(ev.lgb_params(), lgb.Dataset(relative_train[ev.RELATIVE_R2], relative_train.r_rt), num_boost_round=300)
        rhat = relative_model.predict(e[ev.RELATIVE_R2]); relative_model.save_model(str(model_dir / "relative_lightgbm.txt"))
    rhat -= rhat.mean(); assert abs(rhat.mean()) < 1e-9
    preds = pd.read_csv(out / "48.1.predictions.txt", sep="\t", dtype={"dong":str, "sggCd":str})
    gamma_rows = preds[(preds.variant.eq("SEL")) & (preds.prediction_origin.eq(str(origin))) & (preds.horizon_q.eq(horizon))]
    gamma = float(gamma_rows.gamma.iloc[0]) if not gamma_rows.empty else 0.0
    past = preds[(preds.variant.eq("SEL")) & (preds.horizon_q.eq(horizon)) & preds.in_T.astype(str).eq("True") & (pd.PeriodIndex(preds.prediction_origin, freq="Q") + horizon <= origin) & preds.y_rt.notna()].copy()
    take = sorted(past.prediction_origin.unique(), key=lambda x: pd.Period(x, freq="Q"))[-8:]; past = past[past.prediction_origin.isin(take)]
    q = ev.weighted_quantile((past.y_rt-past.y_hat).abs(), 1/past.groupby("prediction_origin").dong.transform("size"), .8) if len(take)==8 and len(past)>=1000 else np.nan
    all_rows = vintage[vintage.as_of_quarter.eq(origin)][["dong","sggCd","umdNm","n_sales_4q","eligible"]].copy()
    values = e[["dong"]].copy(); values["M_hat"], values["r_hat_centered"], values["gamma"] = mhat, rhat, gamma; values["y_hat"] = mhat + gamma*rhat
    values["change_pct_est"] = (np.exp(values.y_hat)-1)*100; values["lower_pct"]=(np.exp(values.y_hat-q)-1)*100; values["upper_pct"]=(np.exp(values.y_hat+q)-1)*100
    result = all_rows.merge(values,on="dong",how="left"); result["origin"],result["horizon_q"]=str(origin),horizon; result["status"]=np.where(result.eligible.astype(str).eq("True"),"PREDICTED","INSUFFICIENT_SALES")
    result.loc[result.status.ne("PREDICTED"),["M_hat","r_hat_centered","gamma","y_hat","change_pct_est","lower_pct","upper_pct"]]=np.nan
    result=result[["dong","sggCd","umdNm","origin","horizon_q","status","n_sales_4q","M_hat","r_hat_centered","gamma","y_hat","change_pct_est","lower_pct","upper_pct"]]
    assert not result.duplicated("dong").any(); assert result.dong.eq(result.sggCd+"_"+result.umdNm).all()
    inputs={name:sha256(out/name) for name in ["47.1.vintage_momentum_all.txt","47.2.realtime_targets.txt","47.3.seoul_market_panel.txt","47.4.dong_relative_features.txt","48.4.selection_log.txt"]}
    payload={"selected_market":selected_market,"selected_relative":selected_relative,"index_ridge_lambda":5,"market_ridge_alpha":ev.MARKET_RIDGE_ALPHA,"relative_ridge_alpha":ev.RELATIVE_RIDGE_ALPHA,"lightgbm_lambda_l2":ev.LIGHTGBM_LAMBDA_L2,"market_scaler":None if market_model is None else {k:np.asarray(market_model[k]).tolist() for k in ["features","mean","std"]},"market_coef":None if market_model is None else market_model["coef"].tolist(),"market_intercept":None if market_model is None else market_model["intercept"],"relative_scaler":None if selected_relative!="R1" or relative_model is None else {k:np.asarray(relative_model[k]).tolist() for k in ["features","mean","std"]},"relative_coef":None if selected_relative!="R1" or relative_model is None else relative_model["coef"].tolist(),"relative_intercept":None if selected_relative!="R1" or relative_model is None else relative_model["intercept"],"lightgbm_model": "relative_lightgbm.txt" if selected_relative=="R2" and relative_model is not None else None,"gamma":gamma,"interval_half_width":q,"n_calibration_origins":len(take),"train_origin_min":str(market_train.origin.min()),"train_origin_max":str(market_train.origin.max()),"label_vintage_max":str(market_train.origin.max()+horizon),"input_sha256":inputs,"created_at":datetime.now(timezone.utc).isoformat()}
    with open(model_dir/"model.json","w",encoding="utf-8") as handle: json.dump(payload,handle,ensure_ascii=False,indent=2)
    result.to_csv(out/"49.1.latest_predictions.txt",sep="\t",index=False,lineterminator="\n")
    print("===== 49 최종 model 생성 완료 ====="); print(f"PREDICTED 동 {int(result.status.eq('PREDICTED').sum()):,}개"); print(result.loc[result.status.eq('PREDICTED'),"y_hat"].describe().to_string()); print(out/"49.1.latest_predictions.txt")


if __name__ == "__main__": main()
