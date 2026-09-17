# ============================================================================
# 63.shrink_dong_index.py
# ============================================================================
# Author:      yjkim
# Purpose:     동 지수의 수축 강도를 데이터로 정하고, 수축 전후 안정성을 비교한다
# Description: 계획 docs/model-develope-plan.md §2.1 후보 0-A, 진행 P0/T0-A.
#              지금 지수는 ridge λ=5로 동 편차를 구 지수 쪽으로 누른다. 이 5는 사람이
#              고른 값이다. Empirical Bayes로 풀면 최적 수축은 λ* = σ²/τ²로,
#              잔차 산포와 동 편차 산포가 정한다. 둘 다 이미 추정했으므로 계산만 하면 된다.
#
#              "수축하면 분산이 준다"는 어떤 수축이든 참이라 판정 근거가 못 된다.
#              그래서 매매를 무작위 반으로 갈라 각각 지수를 만들고, 한쪽을 수축해
#              다른 쪽을 얼마나 잘 맞히는지로 강도를 고른다. 반대쪽은 잡음이 있지만
#              참 편차에 대해 치우쳐 있지 않으므로, 이 오차를 최소로 만드는 강도가
#              과하지도 모자라지도 않은 수축이다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

from _dong_index import RIDGE_LAMBDA, estimate_hedonic_index, load_sales_any
from _dong_index_se import attach_standard_error, index_standard_error

work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"

LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
MIN_SALES_4Q = 20
SPLIT_SEED = 20260917
N_SPLITS = 3          # 분할 한 번의 최적값은 seed에 따라 흔들린다. 여러 번 갈라 평균 곡선을 본다
LAMBDA_GRID = np.round(np.arange(1.0, 16.5, 0.5), 2)


def unshrink(dq_effect, n_sales, ridge_lambda):
    """ridge가 누른 편차를 누르기 전 값으로 되돌린다. 거래가 없으면 되돌릴 것이 없다."""
    n = np.asarray(n_sales, dtype=float)
    return np.where(n > 0, dq_effect * (n + ridge_lambda) / np.maximum(n, 1), 0.0)


def shrink(raw_deviation, n_sales, ridge_lambda):
    """수축 강도 λ로 편차를 구 지수 쪽으로 누른다."""
    n = np.asarray(n_sales, dtype=float)
    return raw_deviation * n / (n + ridge_lambda)


# ============================================================================
# 1. 전체 표본 지수
# ============================================================================

sales, source = load_sales_any(work_dir)
sales = sales[sales["quarter"] <= LAST_COMPLETE_QUARTER].reset_index(drop=True)
print("===== 1. 매매 적재 =====")
print(f"  원천: {source} / {len(sales):,}건")

index, diagnostics = estimate_hedonic_index(sales, ridge_lambda=RIDGE_LAMBDA)
index["n_sales_4q"] = (
    index.groupby("dong")["n_sales"].transform(lambda counts: counts.rolling(4, min_periods=4).sum())
)
index["eligible"] = index["n_sales_4q"].ge(MIN_SALES_4Q)
index, tau = attach_standard_error(index, diagnostics["residual_sd"], RIDGE_LAMBDA)

sigma = diagnostics["residual_sd"]
lambda_eb = sigma**2 / tau**2
print("\n===== 2. Empirical Bayes 최적 수축 =====")
print(f"  잔차 산포 σ {sigma:.4f}, 동 편차 산포 τ {tau:.4f}")
print(f"  λ* = σ²/τ² = {lambda_eb:.2f}  (현행 λ = {RIDGE_LAMBDA})")
print(f"  현행은 EB 최적보다 {RIDGE_LAMBDA / lambda_eb:.2f}배 {'세게' if RIDGE_LAMBDA > lambda_eb else '약하게'} 누른다")


# ============================================================================
# 3. 반쪽 나누기로 수축 강도 고르기
# ============================================================================

def split_scores(half_mask, label):
    """한쪽을 수축해 다른 쪽을 맞히는 오차를 λ별로 잰다."""
    left, _ = estimate_hedonic_index(sales[half_mask].reset_index(drop=True), ridge_lambda=RIDGE_LAMBDA)
    right, _ = estimate_hedonic_index(sales[~half_mask].reset_index(drop=True), ridge_lambda=RIDGE_LAMBDA)

    pair = (left[["dong", "quarter", "dq_effect", "n_sales"]]
            .merge(right[["dong", "quarter", "dq_effect", "n_sales"]],
                   on=["dong", "quarter"], suffixes=("_a", "_b")))
    # 양쪽 모두 거래가 있어야 "맞혔는지"를 물을 수 있다
    pair = pair[(pair["n_sales_a"] > 0) & (pair["n_sales_b"] > 0)].reset_index(drop=True)

    raw_a = unshrink(pair["dq_effect_a"].to_numpy(), pair["n_sales_a"], RIDGE_LAMBDA)
    raw_b = unshrink(pair["dq_effect_b"].to_numpy(), pair["n_sales_b"], RIDGE_LAMBDA)
    scores = {candidate: float(np.mean((shrink(raw_a, pair["n_sales_a"], candidate) - raw_b) ** 2))
              for candidate in LAMBDA_GRID}

    best = min(scores, key=scores.get)
    print(f"\n  [{label}] A {int(half_mask.sum()):,}건 / B {int((~half_mask).sum()):,}건, 비교 칸 {len(pair):,}개")
    print(f"    가장 잘 맞히는 λ = {best:g} (MSE {scores[best]:.6f})")
    print(f"    현행 λ={RIDGE_LAMBDA}의 MSE {scores[float(RIDGE_LAMBDA)]:.6f} — 최적 대비 {scores[float(RIDGE_LAMBDA)] / scores[best] - 1:+.2%}")
    return best, scores


print("\n===== 3. 반쪽 나누기로 수축 강도 고르기 =====")

# 행 단위 분할은 단지×면적bin 고정효과가 한쪽에만 있는 셀을 대량으로 만든다.
# 그런 셀의 거래는 FE가 통째로 흡수해 동 편차에 기여하지 않으므로 편차가 0 쪽으로 눌리고,
# 그만큼 "덜 수축해야 한다"는 쪽으로 답이 기운다. 셀 단위 분할과 나란히 봐야 하는 이유다
rng = np.random.default_rng(SPLIT_SEED)
best_row, _ = split_scores(rng.random(len(sales)) < 0.5, "행 단위 분할 (셀이 양쪽에 쪼개짐)")

# 분할 한 번의 결과만 보면 seed를 쫓게 된다. 여러 번 갈라 최적값이 얼마나 흔들리는지 본다
cells = sales["cell"].unique()
cell_bests, cell_scores_list = [], []
for seed_offset in range(N_SPLITS):
    split_rng = np.random.default_rng(SPLIT_SEED + seed_offset)
    left_cells = set(cells[split_rng.random(len(cells)) < 0.5])
    best, scores = split_scores(sales["cell"].isin(left_cells).to_numpy(),
                                f"셀 단위 분할 {seed_offset + 1}/{N_SPLITS} (셀은 한쪽에만)")
    cell_bests.append(best)
    cell_scores_list.append(scores)

# λ별 오차를 분할 평균으로 모아 하나의 곡선으로 본다
cell_scores = {candidate: float(np.mean([scores[candidate] for scores in cell_scores_list]))
               for candidate in LAMBDA_GRID}
best_cell = min(cell_scores, key=cell_scores.get)

print(f"\n  EB 계산값 λ* = {lambda_eb:.2f}")
print(f"  행 단위 최적 {best_row:g}")
print(f"  셀 단위 최적 분할별 {[f'{value:g}' for value in cell_bests]} → 평균 곡선 최적 {best_cell:g}")

# ============================================================================
# 4. 수축 전후 안정성 비교
# ============================================================================

# 셀 단위 분할이 고정효과 구조를 깨지 않으므로 그쪽을 믿는다. 다만 개선폭이 작으면
# 바꾸지 않는다. 반쪽 나누기 자체에 잡음이 있어 소수점 차이를 쫓으면 seed를 쫓는 꼴이다.
# 문턱 2%는 결정 36이 모델 채택에 쓴 기준과 같다
MIN_GAIN = 0.02
gain = cell_scores[float(RIDGE_LAMBDA)] / cell_scores[best_cell] - 1
adopted_lambda = float(best_cell) if gain >= MIN_GAIN else float(RIDGE_LAMBDA)
print(f"\n  현행 λ={RIDGE_LAMBDA} 대비 개선폭 {gain:+.2%}, 채택 문턱 {MIN_GAIN:.0%}")
print(f"  → λ {adopted_lambda:g} {'채택' if adopted_lambda != RIDGE_LAMBDA else '유지 (바꾸지 않는다)'}")
raw_full = unshrink(index["dq_effect"].to_numpy(), index["n_sales"], RIDGE_LAMBDA)
index["dq_effect_shrunk"] = shrink(raw_full, index["n_sales"], adopted_lambda)
index["log_index_shrunk"] = index["log_index"] - index["dq_effect"] + index["dq_effect_shrunk"]
index["log_index_se_shrunk"] = index_standard_error(index["n_sales"], sigma, tau, adopted_lambda)


def stability(frame, column):
    """분기 간 변화의 산포. 지수가 실제 움직임 없이 튀면 이 값이 커진다."""
    change = frame.sort_values(["dong", "quarter"]).groupby("dong")[column].diff()
    return float(change.std())


low_trade = index["n_sales"] <= 5


def describe(label, candidate):
    """수축 강도 하나를 적용했을 때의 안정성 지표."""
    deviation = shrink(raw_full, index["n_sales"], candidate)
    shifted = index["log_index"] - index["dq_effect"] + deviation
    frame = index.assign(_index=shifted, _deviation=deviation)
    se = index_standard_error(index["n_sales"], sigma, tau, candidate)
    return {
        "지수": label,
        "λ": candidate,
        "반쪽 MSE": cell_scores.get(candidate, np.nan),
        "분기 간 변화 SD": stability(frame, "_index"),
        "저거래 동 편차 SD": float(frame.loc[low_trade, "_deviation"].std()),
        "SE 중앙값": float(np.median(se)),
        "eligible SE 중앙값": float(np.median(se[index["eligible"].to_numpy()])),
    }


# 채택 여부와 상관없이 셋을 나란히 남긴다. 나중에 "왜 안 바꿨나"를 이 표로 답한다
comparison = pd.DataFrame([
    describe("현행", float(RIDGE_LAMBDA)),
    describe("EB 계산값", float(np.round(lambda_eb * 2) / 2)),
    describe("셀 단위 분할 최적", float(best_cell)),
])

print("\n===== 4. 수축 전후 안정성 =====")
print(comparison.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


# ============================================================================
# 5. 저장
# ============================================================================

index_path = output_dir / "63.1.dong_index_shrunk.txt"
index.to_csv(index_path, sep="\t", index=False, lineterminator="\n")
comparison_path = output_dir / "63.2.shrink_comparison.txt"
comparison.to_csv(comparison_path, sep="\t", index=False, lineterminator="\n")

print(f"\n지수: {index_path}")
print(f"비교표: {comparison_path}")
print(f"\n채택 λ {adopted_lambda:g} — docs/model-performance.md와 결정 기록에 옮길 것")
