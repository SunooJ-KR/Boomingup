# ============================================================================
# _dong_index_se.py
# ============================================================================
# Author:      yjkim
# Purpose:     동×분기 지수의 추정 불확실성(log_index_se)을 구하는 공용 함수
# Description: 계획 docs/model-develope-plan.md §2.1, 진행 docs/model-build-process.md P0-1.
#              지수를 쓰는 쪽(shrinkage·gate·구간·측정오차 진단)이 모두 같은 SE 정의를
#              쓰도록 한 곳에 둔다.
#
#              SE의 뜻: "보고한 동 지수가 참 동 지수에서 얼마나 떨어져 있을 수 있는가".
#              두 성분을 합친다.
#                (1) 표본 잡음  — 거래가 적을수록 커진다
#                (2) 수축 편향  — 거래가 없으면 지수가 구 지수로 되돌아가므로,
#                                참 동 편차만큼 모른다
#              n=0이면 SE가 동 편차의 산포 τ가 되고, n이 크면 0으로 간다. 표본 잡음만
#              쓰면 거래 0건 동의 SE가 0이 되어 정반대로 틀린다.
# ============================================================================

import numpy as np
import pandas as pd


def deviation_scale(dq_effect, n_sales, residual_sd, ridge_lambda):
    """참 동 편차의 산포 τ를 적률법으로 추정한다.

    관측된 편차의 분산은 (참 편차 분산 + 표본 잡음 분산)을 수축계수로 누른 값이다.
    수축 전 분산으로 되돌린 뒤 잡음 몫을 빼서 τ²를 남긴다. 거래가 많은 칸일수록
    잡음 몫이 작아 τ 추정에 유리하므로 상위 절반만 쓴다.
    """
    usable = n_sales > 0
    if usable.sum() < 30:
        raise ValueError("τ를 추정할 동×분기 칸이 너무 적다")
    cutoff = np.median(n_sales[usable])
    pick = usable & (n_sales >= cutoff)

    n = n_sales[pick].astype(float)
    unshrunk = dq_effect[pick] * (n + ridge_lambda) / n     # 수축 전 편차로 되돌린다
    noise_var = residual_sd**2 / n
    tau_sq = float(np.mean(unshrunk**2 - noise_var))
    # ponytail: τ를 전 구간·전 자치구 공통 상수로 둔다. 국면·자치구별로 나누는 것은
    # T0-A에서 수축 성능을 볼 때 필요하면 그때 쪼갠다
    return float(np.sqrt(max(tau_sq, 1e-8)))


def index_standard_error(n_sales, residual_sd, tau, ridge_lambda):
    """동×분기 log 지수의 표준오차.

    ridge 추정량 d̂ = Σresid / (n + λ)에 대해
        Var(d̂ − d) = σ²n/(n+λ)²  +  τ²λ²/(n+λ)²
                      └ 표본 잡음 ┘   └ 구 지수로 되돌아간 몫 ┘
    n=0이면 τ, n→∞이면 σ/√n이 된다.
    """
    n = np.asarray(n_sales, dtype=float)
    denominator = (n + ridge_lambda) ** 2
    return np.sqrt((residual_sd**2 * n + tau**2 * ridge_lambda**2) / denominator)


def attach_standard_error(index, residual_sd, ridge_lambda):
    """지수 격자(`dq_effect`, `n_sales` 필요)에 `log_index_se`를 붙이고 (격자, τ)를 돌려준다."""
    dq_effect = index["dq_effect"].to_numpy()
    n_sales = index["n_sales"].to_numpy()

    tau = deviation_scale(dq_effect, n_sales, residual_sd, ridge_lambda)
    out = index.copy()
    out["log_index_se"] = index_standard_error(n_sales, residual_sd, tau, ridge_lambda)
    return out, tau


def se_grade(log_index_se, edges):
    """SE를 3구간 등급으로 나눈다. 화면 신뢰도 블록과 gate가 같은 경계를 쓴다."""
    return pd.cut(log_index_se, bins=[-np.inf, *edges, np.inf], labels=["A", "B", "C"])
