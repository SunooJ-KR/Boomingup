# ============================================================================
# 67.evaluate_delta.py
# ============================================================================
# Author:      yjkim
# Purpose:     δ(동의 서울 대비 상대 변화) 예측이 기준선을 이기는지 판정한다
# Description: 계획 docs/model-develope-plan.md §2.3·§4, 진행 C-0/1·C-2·C-diag.
#
#              제품 성립 조건이 여기 걸려 있다. δ에서 기준선을 못 이기면 동별 예측을
#              화면에 낼 근거가 없다. 그래서 이 스크립트는 "좋은 모델 찾기"가 아니라
#              "사다리를 올라도 되는지 판정"이 목적이다.
#
#              y_i = μ + δ_i 로 나눈다. μ는 세대수가중 서울 공통 변화(결정 43),
#              δ는 나머지다. μ는 모델링하지 않는다(계획 §1).
#
#              후보 (복잡도 오름차순, 각 단은 아래 단을 유의하게 이겨야 한다)
#                C-0  δ̂ = 0                     기준선
#                C-1  구 평균 상대 모멘텀        두 번째 기준선
#                C-2  수축 모멘텀 (SE 기반 λ)    계획이 먼저 보라고 한 후보
#
#              누수 방지
#                - feature는 기점까지의 매매만으로 다시 추정한 vintage 지수로 만든다.
#                  전체 표본 지수로 feature를 만들면 미래가 새 들어온다
#                - target은 실현값이므로 전체 표본 지수를 쓴다
#                - 학습 표본은 s + h ≤ T (결정 41)
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from _dong_index import RIDGE_LAMBDA, estimate_hedonic_index, load_sales_any
from _dong_index_se import attach_standard_error
from _dong_weight import dong_households

work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"

HORIZON_Q = 4
FIRST_ORIGIN = pd.Period("2015Q1", freq="Q")
LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
LAST_ORIGIN = LAST_COMPLETE_QUARTER - HORIZON_Q     # target이 성숙한 기점까지만
MIN_SALES_4Q = 20
MOMENTUM_Q = 4
KEEP_Q = 9            # vintage에 남길 분기 수. 재추정이 40분 걸려 한 번에 넉넉히 받는다
BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 20260917

parser = argparse.ArgumentParser(description="δ 사다리 rolling-origin 평가")
parser.add_argument("--feature-lag", type=int, default=0,
                    help="feature 기점을 몇 분기 앞당길지. 1이면 측정오차 진단(계획 §4.4-1)")
parser.add_argument("--rebuild-vintage", action="store_true", help="vintage 지수를 다시 만든다")
parser.add_argument("--first-origin", default=None, help="기점 시작을 늦춘다 (점검용, 예: 2023Q1)")
args = parser.parse_args()

vintage_path = output_dir / "67.0.vintage_index.txt"
if args.first_origin:
    vintage_path = output_dir / f"67.0.vintage_index.trial_{args.first_origin}.txt"


# ============================================================================
# 1. 매매와 전체 표본 지수 (target용)
# ============================================================================

sales, source = load_sales_any(work_dir)
sales = sales[sales["quarter"] <= LAST_COMPLETE_QUARTER].reset_index(drop=True)
print("===== 1. 매매 적재 =====")
print(f"  원천: {source} / {len(sales):,}건")

final_index, diagnostics = estimate_hedonic_index(sales, ridge_lambda=RIDGE_LAMBDA)
final_index["n_sales_4q"] = (
    final_index.groupby("dong")["n_sales"].transform(lambda counts: counts.rolling(4, min_periods=4).sum())
)
final_index["eligible"] = final_index["n_sales_4q"].ge(MIN_SALES_4Q)
print(f"  확정 지수 {len(final_index):,}칸, 잔차 SD {diagnostics['residual_sd']:.4f}")

weights, coverage = dong_households(work_dir)
print(f"  세대수 가중치 {len(weights):,}개 동, 커버리지 {coverage:.1%}")


# ============================================================================
# 2. 기점별 vintage 지수 (feature용)
# ============================================================================

first_origin = pd.Period(args.first_origin, freq="Q") if args.first_origin else FIRST_ORIGIN
origins = pd.period_range(first_origin, LAST_ORIGIN, freq="Q")

if vintage_path.is_file() and not args.rebuild_vintage:
    vintage = pd.read_csv(vintage_path, sep="\t")
    vintage["as_of"] = pd.PeriodIndex(vintage["as_of"], freq="Q")
    vintage["quarter"] = pd.PeriodIndex(vintage["quarter"], freq="Q")
    print(f"\n===== 2. vintage 지수 (기존 파일 재사용) =====\n  {vintage_path}")
else:
    print(f"\n===== 2. vintage 지수 추정 ({len(origins)}개 기점) =====")
    frames = []
    # 기점마다 그때까지의 매매만으로 다시 추정한다. feature가 미래를 보지 않게 하는
    # 유일한 방법이다. 기점당 1분 안팎 걸린다
    for position, as_of in enumerate(origins, start=1):
        subset = sales[sales["quarter"] <= as_of].reset_index(drop=True)
        grid, grid_diagnostics = estimate_hedonic_index(subset, ridge_lambda=RIDGE_LAMBDA)
        grid["n_sales_4q"] = (
            grid.groupby("dong")["n_sales"].transform(lambda counts: counts.rolling(4, min_periods=4).sum())
        )
        grid["eligible"] = grid["n_sales_4q"].ge(MIN_SALES_4Q)
        grid, _ = attach_standard_error(grid, grid_diagnostics["residual_sd"], RIDGE_LAMBDA)
        # 기점 기준 최근 KEEP_Q개 분기를 남긴다. feature 기점을 앞당기는 진단(§4.4)과
        # 더 긴 창을 쓰는 C-3까지 같은 파일로 덮으려고 모멘텀 창보다 넉넉히 둔다
        keep = grid["quarter"] > as_of - KEEP_Q
        grid = grid[keep & (grid["quarter"] <= as_of)].copy()
        grid["as_of"] = as_of
        frames.append(grid[["as_of", "dong", "sggCd", "quarter", "log_index",
                            "log_index_se", "n_sales", "n_sales_4q", "eligible"]])
        print(f"  [{position}/{len(origins)}] {as_of} 완료 ({len(subset):,}건)")

    vintage = pd.concat(frames, ignore_index=True)
    vintage.to_csv(vintage_path, sep="\t", index=False, lineterminator="\n")
    print(f"  저장: {vintage_path}")


# ============================================================================
# 3. target — 실현된 δ
# ============================================================================

level = final_index.set_index(["dong", "quarter"])["log_index"]


def realized_change(dongs, start, end):
    """동별 log 지수 변화. 확정 지수를 쓴다(실현값이므로 누수가 아니다)."""
    begin = level.reindex(pd.MultiIndex.from_product([dongs, [start]])).to_numpy()
    finish = level.reindex(pd.MultiIndex.from_product([dongs, [end]])).to_numpy()
    return finish - begin


targets = []
for as_of in origins:
    dongs = sorted(final_index["dong"].unique())
    change = realized_change(dongs, as_of, as_of + HORIZON_Q)
    frame = pd.DataFrame({"origin": as_of, "dong": dongs, "y": change})
    frame["weight"] = frame["dong"].map(weights).fillna(0.0)
    frame = frame[frame["y"].notna()].reset_index(drop=True)
    # μ는 세대수가중 서울 공통 변화. δ는 나머지다
    mu = float(np.average(frame["y"], weights=frame["weight"])) if frame["weight"].sum() > 0 else float(frame["y"].mean())
    frame["mu"] = mu
    frame["delta"] = frame["y"] - mu
    targets.append(frame)

target_panel = pd.concat(targets, ignore_index=True)
print(f"\n===== 3. target =====")
print(f"  {len(target_panel):,}행, 기점 {target_panel['origin'].nunique()}개")
print(f"  μ 평균 {target_panel.groupby('origin')['mu'].first().mean():+.4f}, "
      f"δ 표준편차 {target_panel['delta'].std():.4f}")


# ============================================================================
# 4. feature — 기점까지의 vintage 지수로만 만든다
# ============================================================================

def momentum_at(as_of):
    """기점 as_of에서 본 동별 상대 모멘텀과 SE."""
    block = vintage[vintage["as_of"] == as_of]
    if block.empty:
        return None
    start, end = as_of - MOMENTUM_Q - args.feature_lag, as_of - args.feature_lag
    wide = block.pivot_table(index="dong", columns="quarter", values="log_index")
    if start not in wide.columns or end not in wide.columns:
        return None

    frame = pd.DataFrame({"dong": wide.index, "change": (wide[end] - wide[start]).to_numpy()})
    latest = block[block["quarter"] == as_of].set_index("dong")
    frame["sggCd"] = frame["dong"].map(latest["sggCd"])
    frame["se"] = frame["dong"].map(latest["log_index_se"])
    frame["eligible"] = frame["dong"].map(latest["eligible"]).fillna(False)
    frame["weight"] = frame["dong"].map(weights).fillna(0.0)

    # 서울 공통 몫을 빼서 상대 모멘텀으로 만든다. target의 δ와 같은 방식이다
    usable = frame["change"].notna()
    if not usable.any():
        return None
    common = float(np.average(frame.loc[usable, "change"], weights=frame.loc[usable, "weight"])) \
        if frame.loc[usable, "weight"].sum() > 0 else float(frame.loc[usable, "change"].mean())
    frame["relative"] = frame["change"] - common
    # 구 평균 상대 모멘텀 (C-1)
    frame["gu_relative"] = frame.groupby("sggCd")["relative"].transform("mean")
    return frame.dropna(subset=["relative"]).reset_index(drop=True)


features = {as_of: momentum_at(as_of) for as_of in origins}
features = {as_of: frame for as_of, frame in features.items() if frame is not None}
print(f"\n===== 4. feature =====")
print(f"  기점 {len(features)}개에서 상대 모멘텀 생성 (feature 기점 지연 {args.feature_lag}분기)")


# ============================================================================
# 5. 후보 — 사다리
# ============================================================================

def c0(frame, _history):
    return np.zeros(len(frame))


def c1(frame, _history):
    return frame["gu_relative"].to_numpy()


def fitted_scale(feature, history, column):
    """feature × 계수. 계수는 기점 이전 자료로만 적합한다(원점 통과 회귀)."""
    if history is None or len(history) < 500:
        return np.zeros(len(feature))
    x = history[column].to_numpy()
    denominator = float(np.dot(x, x))
    coefficient = float(np.dot(x, history["delta"].to_numpy()) / denominator) if denominator > 0 else 0.0
    return coefficient * feature.to_numpy()


def c1f(frame, history):
    """C-1f: 구 모멘텀 × 적합 계수. 계획 §2.3 분기 규칙의 전제 검증.

    C-1이 C-0보다 나빴던 것이 정보 부재 때문인지, 계수 1이 크기를 과대 예측한 탓인지
    가른다. 계수가 0 근처면 정보가 없는 것이고, 0.2~0.5로 잡히면서 C-0을 이기면
    그룹 모멘텀에 쓸 만한 정보가 있는 것이다.
    """
    return fitted_scale(frame["gu_relative"], history, "gu_relative")


def c2(frame, history):
    """수축 모멘텀. 계수는 기점 이전 자료로만 적합한다.

    λ(SE)는 측정오차가 큰 동일수록 모멘텀을 더 누른다. 계획 §2.3 C-2가 겨냥한 것이
    바로 가짜 평균회귀이므로, 수축 없이 모멘텀을 그대로 쓰면 안 된다.
    """
    if history is None or len(history) < 500:
        return np.zeros(len(frame))
    weight = history["se"].median() ** 2
    shrunk_history = history["relative"] * history["se"].median() ** 2 / (history["se"] ** 2 + weight)
    coefficient = float(np.dot(shrunk_history, history["delta"]) / np.dot(shrunk_history, shrunk_history)) \
        if np.dot(shrunk_history, shrunk_history) > 0 else 0.0
    shrunk = frame["relative"] * weight / (frame["se"] ** 2 + weight)
    return coefficient * shrunk.to_numpy()


CANDIDATES = {"C-0 (δ̂=0)": c0, "C-1 (구 평균)": c1, "C-1f (구 평균·적합)": c1f, "C-2 (수축 모멘텀)": c2}


# ============================================================================
# 6. rolling-origin 평가
# ============================================================================

joined = {}
for as_of, frame in features.items():
    block = target_panel[target_panel["origin"] == as_of][["dong", "delta"]]
    merged = frame.merge(block, on="dong", how="inner")
    merged = merged[merged["eligible"]].reset_index(drop=True)   # gate 적용(계획 §4.6)
    if len(merged) >= 30:
        joined[as_of] = merged

print(f"\n===== 5. 평가 =====")
print(f"  gate 통과 기점 {len(joined)}개, 기점당 동 중앙값 "
      f"{int(np.median([len(frame) for frame in joined.values()]))}개")

rows = []
for as_of in sorted(joined):
    # 학습 표본은 target이 확정된 기점만 (결정 41)
    past = [other for other in sorted(joined) if other + HORIZON_Q <= as_of]
    history = pd.concat([joined[other] for other in past], ignore_index=True) if past else None

    frame = joined[as_of]
    record = {"origin": as_of, "n_dong": len(frame)}
    for name, predict in CANDIDATES.items():
        estimate = predict(frame, history)
        record[f"mae::{name}"] = float(np.mean(np.abs(frame["delta"].to_numpy() - estimate)))
        record[f"rho::{name}"] = float(spearmanr(estimate, frame["delta"]).statistic) \
            if np.std(estimate) > 0 else np.nan
    rows.append(record)

result = pd.DataFrame(rows)
mae_columns = [f"mae::{name}" for name in CANDIDATES]
summary = pd.DataFrame({
    "후보": list(CANDIDATES),
    "δ MAE": [result[column].mean() for column in mae_columns],
    "Spearman 중앙값": [result[f"rho::{name}"].median() for name in CANDIDATES],
    "Spearman > 0 기점 비율": [float((result[f"rho::{name}"] > 0).mean()) for name in CANDIDATES],
})
print("\n  기점 동일 가중 성능:")
print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


# ============================================================================
# 7. 판정 — 블록 bootstrap과 DM 검정
# ============================================================================

rng = np.random.default_rng(BOOTSTRAP_SEED)
years = result["origin"].dt.year.to_numpy()
unique_years = np.unique(years)


def block_bootstrap_gain(column_a, column_b):
    """기점 연도 블록으로 재표본한 (A − B) MAE 차이의 95% 구간."""
    gains = []
    for _ in range(BOOTSTRAP_ROUNDS):
        drawn = rng.choice(unique_years, size=len(unique_years), replace=True)
        picked = np.concatenate([np.where(years == year)[0] for year in drawn])
        gains.append(result[column_a].to_numpy()[picked].mean() - result[column_b].to_numpy()[picked].mean())
    return np.percentile(gains, [2.5, 97.5])


def diebold_mariano(column_a, column_b, lag=HORIZON_Q - 1):
    """중첩 horizon을 HAC로 보정한 DM 통계량과 p값."""
    difference = result[column_a].to_numpy() - result[column_b].to_numpy()
    n = len(difference)
    centered = difference - difference.mean()
    variance = np.dot(centered, centered) / n
    for shift in range(1, lag + 1):
        covariance = np.dot(centered[shift:], centered[:-shift]) / n
        variance += 2 * (1 - shift / (lag + 1)) * covariance
    if variance <= 0:
        return np.nan, np.nan
    statistic = difference.mean() / np.sqrt(variance / n)
    from scipy.stats import norm
    return statistic, float(2 * (1 - norm.cdf(abs(statistic))))


print("\n===== 6. 판정 (기준선 대비) =====")
verdicts = []
for name in ["C-1 (구 평균)", "C-1f (구 평균·적합)", "C-2 (수축 모멘텀)"]:
    for baseline in ["C-0 (δ̂=0)", "C-1 (구 평균)"]:
        if name == baseline:
            continue
        low, high = block_bootstrap_gain(f"mae::{baseline}", f"mae::{name}")
        statistic, p_value = diebold_mariano(f"mae::{baseline}", f"mae::{name}")
        gain = result[f"mae::{baseline}"].mean() - result[f"mae::{name}"].mean()
        beats = bool(low > 0 and p_value is not np.nan and p_value < 0.05)
        verdicts.append({"후보": name, "기준선": baseline, "MAE 개선": gain,
                         "구간 하한": low, "구간 상한": high, "DM p": p_value, "통과": beats})
print(pd.DataFrame(verdicts).to_string(index=False, float_format=lambda value: f"{value:.4f}"))

passed = [row for row in verdicts if row["후보"] == "C-2 (수축 모멘텀)" and row["통과"]]
premise = [row for row in verdicts if row["후보"] == "C-1f (구 평균·적합)" and row["기준선"] == "C-0 (δ̂=0)"]
if premise:
    print(f"  전제 검증 C-1f가 C-0을 이겼는가: {'예' if premise[0]['통과'] else '아니오'} (계획 §2.3 분기 규칙)")
print(f"\n  C-2가 두 기준선을 모두 이겼는가: {'예' if len(passed) == 2 else '아니오'}")
print("  성립 조건(계획 §4.2)은 C-0과 C-1 둘 다를 유의하게 이기는 것이다")


# ============================================================================
# 8. 저장
# ============================================================================

# 기점을 줄인 점검 실행이 정식 산출물을 덮어쓰지 않게 한다 (models/AGENTS.md의 .trial_ 규칙)
suffix = f".lag{args.feature_lag}" if args.feature_lag else ""
if args.first_origin:
    suffix += f".trial_{args.first_origin}"
result.to_csv(output_dir / f"67.1.delta_by_origin{suffix}.txt", sep="\t", index=False, lineterminator="\n")
pd.DataFrame(verdicts).to_csv(output_dir / f"67.2.delta_verdict{suffix}.txt",
                              sep="\t", index=False, lineterminator="\n")
print(f"\n기점별: {output_dir / f'67.1.delta_by_origin{suffix}.txt'}")
print(f"판정: {output_dir / f'67.2.delta_verdict{suffix}.txt'}")
