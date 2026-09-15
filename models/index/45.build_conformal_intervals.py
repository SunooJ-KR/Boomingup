# ============================================================================
# 45.build_conformal_intervals.py
# ============================================================================
# Author:      yjkim
# Purpose:     44의 OOT 예측에 시간×동 이중 분할 split conformal 예측 구간을 붙이고 coverage를 잰다
# Description: 결정 12. 동만 나누면 시장 국면이 바뀔 때의 오차를 담지 못하므로 시간도 함께 나눈다.
#              - 시간 분할: 기점 t의 구간은 결과가 t까지 확정된 기점(s + h <= t)의 잔차만 쓴다
#              - 동 분할: 동을 고정 해시로 두 fold에 나누고, 반대 fold 동의 잔차만 쓴다
#              - 구간 = pred ± 보정 잔차의 ceil((n+1)·level)/n 분위수 (split conformal 유한표본 보정)
#              - 보정 잔차가 MIN_CALIBRATION개 미만인 기점은 구간을 만들지 않는다
#              표기: "추정 구간"이며 "80% 보장"이라고 쓰지 않는다 (AGENTS §6)
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import argparse
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"

COVERAGE_LEVEL = 0.80
MIN_CALIBRATION = 200

parser = argparse.ArgumentParser()
parser.add_argument("--predictions", default="44.1.oot_predictions.txt", help="output/ 아래 44 예측 파일 이름")
args = parser.parse_args()
predictions_path = output_dir / args.predictions


def dong_fold(dong):
    """실행마다 같은 fold가 나오도록 파이썬 hash 대신 crc32를 쓴다."""
    return zlib.crc32(dong.encode("utf-8")) % 2


def conformal_quantile(residuals, level):
    n = len(residuals)
    rank = min(int(np.ceil((n + 1) * level)), n)
    return np.sort(residuals)[rank - 1]


# ============================================================================
# 1. 예측 적재
# ============================================================================

predictions = pd.read_csv(predictions_path, sep="\t", dtype={"dong": str, "sggCd": str})
predictions["as_of_quarter"] = pd.PeriodIndex(predictions["as_of_quarter"], freq="Q")
predictions["fold"] = predictions["dong"].map(dong_fold)
predictions["abs_residual"] = (predictions["y"] - predictions["pred"]).abs()
print(f"===== 1. 예측 적재 완료: {len(predictions):,}행, h = {sorted(predictions['horizon_q'].unique())} =====")


# ============================================================================
# 2. 기점별 구간
# ============================================================================

frames = []
for horizon, by_horizon in predictions.groupby("horizon_q"):
    for origin, target_rows in by_horizon.groupby("as_of_quarter"):
        for fold, rows in target_rows.groupby("fold"):
            calibration = by_horizon[
                (by_horizon["as_of_quarter"] <= origin - horizon) & (by_horizon["fold"] != fold)
            ]["abs_residual"].to_numpy()
            rows = rows.copy()
            rows["n_calibration"] = len(calibration)
            if len(calibration) >= MIN_CALIBRATION:
                half_width = conformal_quantile(calibration, COVERAGE_LEVEL)
                rows["lower"] = rows["pred"] - half_width
                rows["upper"] = rows["pred"] + half_width
            else:
                rows["lower"] = np.nan
                rows["upper"] = np.nan
            frames.append(rows)

intervals = pd.concat(frames, ignore_index=True)
has_interval = intervals["lower"].notna()
intervals["covered"] = ((intervals["y"] >= intervals["lower"]) & (intervals["y"] <= intervals["upper"])).where(has_interval)
print("===== 2. 기점별 구간 완료 =====")


# ============================================================================
# 3. 저장 및 coverage
# ============================================================================

stem = predictions_path.name.replace("44.1.oot_predictions", "45.1.oot_intervals")
intervals_path = output_dir / stem
intervals.drop(columns=["abs_residual"]).to_csv(intervals_path, sep="\t", index=False, lineterminator="\n")

scored = intervals[has_interval].copy()
scored["year"] = scored["as_of_quarter"].dt.year
summary = (scored.groupby("horizon_q")
    .agg(n_rows=("covered", "size"), coverage=("covered", "mean"),
         median_width=("upper", lambda upper: (upper - scored.loc[upper.index, "lower"]).median()))
    .reset_index())
by_year = scored.groupby(["horizon_q", "year"])["covered"].mean().unstack("year").round(3)
print(f"\n===== 3. 목표 {COVERAGE_LEVEL:.0%} 대비 test coverage =====")
print(summary.round(4).to_string(index=False))
print("\n연도별 coverage")
print(by_year.to_string())
print(f"\n구간 없는 행(보정 잔차 {MIN_CALIBRATION}개 미만): {int((~has_interval).sum()):,}")
print(f"구간: {intervals_path}")
