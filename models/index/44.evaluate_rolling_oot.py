# ============================================================================
# 44.evaluate_rolling_oot.py
# ============================================================================
# Author:      yjkim
# Purpose:     동별 h분기 log 변화 예측을 rolling-origin OOT로 평가하고 채택 기준을 판정한다
# Description: 사전 등록 docs/decisions.md 결정 7~11.
#              - 표본: 기점 t에 eligible(직전 4분기 매매 20건 이상)인 동
#              - target: 40 전체 데이터 지수의 t → t+h log 변화
#              - 학습: s + h <= t 인 기점 s만 (h분기 gap), LightGBM(임앤장 33 채택 설정)
#              - baseline: B1 동 직전 h분기 vintage 변화, B2 eligible 동 평균. 참고: B0 0, oracle 미래 평균
#              - 판정: 모델 MAE < B1·B2 이고 동 block bootstrap(1,000회, seed 42) 95% CI 상한 < 0
#              - 비교는 모델·B1·B2가 모두 있는 행에서만 한다
#              --first-eval-origin은 파이프라인 점검용이다. 판정은 기본값 2016Q1로만 한다
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import argparse
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"

LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
LGB_PARAMS = {
    "objective": "regression", "learning_rate": 0.05, "num_leaves": 31, "min_data_in_leaf": 40,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 1,
    "seed": 20260911, "verbosity": -1, "num_threads": -1,
}
NUM_BOOST_ROUND = 300
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 42
KEY_COLUMNS = {"dong", "sggCd", "umdNm", "as_of_quarter", "eligible"}

parser = argparse.ArgumentParser()
parser.add_argument("--first-eval-origin", default="2016Q1")
parser.add_argument("--horizons", default="2,4,8,12")
args = parser.parse_args()
first_eval_origin = pd.Period(args.first_eval_origin, freq="Q")
horizons = [int(value) for value in args.horizons.split(",")]
is_official = args.first_eval_origin == "2016Q1"


def read_panel(path, quarter_column):
    frame = pd.read_csv(path, sep="\t", dtype={"dong": str, "sggCd": str, "umdNm": str})
    frame[quarter_column] = pd.PeriodIndex(frame[quarter_column], freq="Q")
    return frame


# ============================================================================
# 1. 입력 결합
# ============================================================================

index = read_panel(output_dir / "40.1.dong_index.txt", "quarter")[["dong", "quarter", "log_index"]]
vintage = read_panel(output_dir / "41.1.vintage_momentum.txt", "as_of_quarter")
features = read_panel(output_dir / "42.1.dong_features.txt", "as_of_quarter").drop(columns=["sggCd", "umdNm"])
macro = read_panel(output_dir / "43.1.gu_macro_regulation.txt", "as_of_quarter")

panel = (vintage
    .merge(features, on=["dong", "as_of_quarter"], how="left")
    .merge(macro, on=["sggCd", "as_of_quarter"], how="left"))
panel = panel[panel["eligible"]].reset_index(drop=True)
feature_columns = [column for column in panel.columns if column not in KEY_COLUMNS]
print("===== 1. 입력 결합 완료 =====")
print(f"  eligible 행 {len(panel):,} / feature {len(feature_columns)}개 / 기점 {panel['as_of_quarter'].min()} ~ {panel['as_of_quarter'].max()}")


def add_target(frame, horizon):
    now = index.rename(columns={"quarter": "as_of_quarter", "log_index": "index_now"})
    future = index.rename(columns={"quarter": "as_of_quarter", "log_index": "index_future"})
    future["as_of_quarter"] = future["as_of_quarter"] - horizon
    result = frame.merge(now, on=["dong", "as_of_quarter"], how="left").merge(future, on=["dong", "as_of_quarter"], how="left")
    result["y"] = result["index_future"] - result["index_now"]
    return result.dropna(subset=["y"]).reset_index(drop=True)


def bootstrap_mae_diff(frame, column_a, column_b):
    """동 단위 block bootstrap으로 MAE(a) − MAE(b)의 95% CI를 구한다."""
    per_dong = (frame
        .assign(err_a=(frame[column_a] - frame["y"]).abs(), err_b=(frame[column_b] - frame["y"]).abs())
        .groupby("dong")[["err_a", "err_b"]].agg(["sum", "count"]))
    sum_a = per_dong[("err_a", "sum")].to_numpy()
    sum_b = per_dong[("err_b", "sum")].to_numpy()
    count = per_dong[("err_a", "count")].to_numpy()
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.integers(0, len(count), size=(N_BOOTSTRAP, len(count)))
    diffs = (sum_a[draws].sum(axis=1) - sum_b[draws].sum(axis=1)) / count[draws].sum(axis=1)
    return np.percentile(diffs, [2.5, 97.5])


# ============================================================================
# 2. 기간별 rolling-origin 평가
# ============================================================================

prediction_frames = []
metric_rows = []
for horizon in horizons:
    data = add_target(panel, horizon)
    eval_origins = pd.period_range(first_eval_origin, LAST_COMPLETE_QUARTER - horizon, freq="Q")
    momentum = f"mom_{horizon}q"

    horizon_frames = []
    for position, origin in enumerate(eval_origins):
        train = data[data["as_of_quarter"] <= origin - horizon]
        test = data[data["as_of_quarter"] == origin]
        if train.empty or test.empty:
            continue
        booster = lgb.train(LGB_PARAMS, lgb.Dataset(train[feature_columns], train["y"]), num_boost_round=NUM_BOOST_ROUND)

        result = test[["dong", "sggCd", "as_of_quarter", "y"]].copy()
        result["horizon_q"] = horizon
        result["pred"] = booster.predict(test[feature_columns])
        result["b1"] = test[momentum]
        result["b2"] = panel.loc[panel["as_of_quarter"] == origin, momentum].mean()
        result["b0"] = 0.0
        result["oracle"] = test["y"].mean()
        result["n_train"] = len(train)
        horizon_frames.append(result)
        print(f"처리 중 h={horizon} [{position + 1}/{len(eval_origins)}]: {origin} (학습 {len(train):,}, 평가 {len(test)})")

    if not horizon_frames:
        print(f"  h={horizon}: 평가 가능한 기점 없음")
        continue
    predictions = pd.concat(horizon_frames, ignore_index=True)
    prediction_frames.append(predictions)

    compared = predictions.dropna(subset=["pred", "b1", "b2"])
    mae = {name: (compared[name] - compared["y"]).abs().mean() for name in ["pred", "b1", "b2", "b0", "oracle"]}
    ci_b1 = bootstrap_mae_diff(compared, "pred", "b1")
    ci_b2 = bootstrap_mae_diff(compared, "pred", "b2")
    passed = mae["pred"] < mae["b1"] and mae["pred"] < mae["b2"] and ci_b1[1] < 0 and ci_b2[1] < 0
    metric_rows.append({
        "horizon_q": horizon, "n_rows": len(compared), "n_dongs": compared["dong"].nunique(),
        "n_origins": compared["as_of_quarter"].nunique(), "dropped_missing_baseline": len(predictions) - len(compared),
        "mae_model": mae["pred"], "mae_b1": mae["b1"], "mae_b2": mae["b2"], "mae_b0_ref": mae["b0"], "mae_oracle_ref": mae["oracle"],
        "diff_b1_ci_low": ci_b1[0], "diff_b1_ci_high": ci_b1[1], "diff_b2_ci_low": ci_b2[0], "diff_b2_ci_high": ci_b2[1],
        "passed": passed, "official": is_official,
    })
print("\n===== 2. rolling-origin 평가 완료 =====")


# ============================================================================
# 3. 저장 및 판정
# ============================================================================

suffix = "" if is_official else ".trial"
predictions_path = output_dir / f"44.1.oot_predictions{suffix}.txt"
metrics_path = output_dir / f"44.2.oot_metrics{suffix}.txt"
pd.concat(prediction_frames, ignore_index=True).to_csv(predictions_path, sep="\t", index=False, lineterminator="\n")
metrics = pd.DataFrame(metric_rows)
metrics.to_csv(metrics_path, sep="\t", index=False, lineterminator="\n")

print("\n===== 3. 판정 (결정 10) =====")
if not is_official:
    print("  ※ 점검용 실행(--first-eval-origin 변경)이라 판정으로 쓰지 않는다")
print(metrics.round(4).to_string(index=False))
print(f"\n예측: {predictions_path}")
print(f"지표: {metrics_path}")
