# ============================================================================
# test_dong_index_se.py
# ============================================================================
# Author:      yjkim
# Purpose:     지수 SE 계산이 참 동 편차와의 거리를 맞게 재는지 합성 데이터로 점검한다
# Description: 참 편차 τ와 잡음 σ를 정해 두고 지수를 만든 뒤, 되돌려 추정한 SE가
#              (1) 거래가 적을수록 크고 (2) 실제 오차 크기와 맞는지 본다.
#              docs/model-build-process.md P0-1의 완료 조건을 코드로 고정한 것이다.
# ============================================================================

import numpy as np

from _dong_index_se import deviation_scale, index_standard_error

RIDGE_LAMBDA = 5
TRUE_TAU = 0.08          # 참 동 편차의 산포 (log 단위)
RESIDUAL_SD = 0.25       # 거래 1건의 잔차 SD


def make_cells(rng, n_cells=20000):
    """거래 건수가 제각각인 동×분기 칸을 만들고 ridge 추정을 흉내 낸다."""
    n_sales = rng.integers(0, 60, size=n_cells)
    true_deviation = rng.normal(0, TRUE_TAU, size=n_cells)

    # 거래가 있는 칸은 평균 잔차만큼 흔들린 값을, ridge가 0 쪽으로 누른다
    noisy = np.where(n_sales > 0,
                     true_deviation + rng.normal(0, RESIDUAL_SD / np.sqrt(np.maximum(n_sales, 1))),
                     0.0)
    estimated = noisy * n_sales / (n_sales + RIDGE_LAMBDA)
    return n_sales, true_deviation, estimated


def test_tau_recovered():
    rng = np.random.default_rng(20260917)
    n_sales, _, estimated = make_cells(rng)
    tau = deviation_scale(estimated, n_sales, RESIDUAL_SD, RIDGE_LAMBDA)
    assert abs(tau - TRUE_TAU) < 0.2 * TRUE_TAU, f"τ 추정 {tau:.4f}, 참값 {TRUE_TAU}"


def test_se_decreases_with_sales():
    se = index_standard_error([0, 1, 5, 20, 100], RESIDUAL_SD, TRUE_TAU, RIDGE_LAMBDA)
    assert np.all(np.diff(se) < 0), f"거래가 늘수록 SE가 줄어야 한다: {se}"
    assert abs(se[0] - TRUE_TAU) < 1e-9, "거래 0건이면 SE는 동 편차 산포 τ다"


def test_se_is_calibrated():
    """SE가 실제 오차 크기와 맞는지 — 표준화 오차의 SD가 1 근처여야 한다."""
    rng = np.random.default_rng(31415)
    n_sales, true_deviation, estimated = make_cells(rng)
    se = index_standard_error(n_sales, RESIDUAL_SD, TRUE_TAU, RIDGE_LAMBDA)
    standardized = (estimated - true_deviation) / se
    assert abs(standardized.std() - 1.0) < 0.1, f"표준화 오차 SD {standardized.std():.3f}"

    within = np.mean(np.abs(standardized) <= 1.0)
    assert 0.63 < within < 0.73, f"±1 SE 안에 드는 비율 {within:.3f} (정규면 0.68)"


if __name__ == "__main__":
    test_tau_recovered()
    test_se_decreases_with_sales()
    test_se_is_calibrated()
    print("dong_index_se 점검 통과")
