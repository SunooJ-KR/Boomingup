# ============================================================================
# _short_index.py
# ============================================================================
# Author:      yjkim
# Purpose:     3개월 예측 파일럿(60번대)이 함께 쓰는 거래 적재·hedonic 지수 추정 함수
# Description: models/index/_dong_index.py의 추정식을 기간 열을 자유롭게 고를 수 있게 옮겼다.
#              - hedonic: log(가격/㎡) = 단지×면적bin FE + 구×기간 + 동×기간 편차(ridge λ)
#              - 기간은 월(구조 A)이든 3개월 창 번호(구조 B)든 정수 열이면 된다
#              - holdout 보호: 가격을 읽는 모든 경로는 deal_ym > 202504 거래를 적재 시점에 버린다
#                (holdout 기점 2025-05~2026-04, docs/short-horizon-research-plan.md §3.6)
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr

AREA_BIN_M2 = 3
RIDGE_LAMBDA = 5
PRICE_LAST_YM = 202504     # 이 달 뒤의 가격은 파일럿에서 읽지 않는다
LAST_PILOT_ORIGIN = 202501 # target(t+3)이 PRICE_LAST_YM 안에서 끝나는 마지막 기점
SALE_COLUMNS = ["aptSeq", "sggCd", "umdNm", "excluUseAr", "deal_ym", "is_cancelled", "deal_amount_manwon"]

WORK_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = WORK_DIR / "output"


def ym_to_mi(ym):
    """YYYYMM 정수 → 월 번호(연×12 + 월−1). 월 산술을 정수 덧셈으로 하려고 쓴다."""
    ym = np.asarray(ym, dtype=int)
    return (ym // 100) * 12 + (ym % 100) - 1


def mi_to_ym(mi):
    mi = np.asarray(mi, dtype=int)
    return (mi // 12) * 100 + mi % 12 + 1


def load_sales(path=OUTPUT_DIR / "11.1.trades_sale.txt"):
    """해제 제외·가격/면적 양수·aptSeq 있는 매매만 남긴다. holdout 가격은 여기서 버린다."""
    sales = pd.read_csv(path, sep="\t", dtype=str, usecols=SALE_COLUMNS)
    area = pd.to_numeric(sales["excluUseAr"], errors="coerce")
    price = pd.to_numeric(sales["deal_amount_manwon"], errors="coerce")
    keep = (
        sales["is_cancelled"].eq("False")
        & sales["aptSeq"].notna()
        & sales["sggCd"].notna()
        & sales["umdNm"].notna()
        & area.gt(0)
        & price.gt(0)
        & sales["deal_ym"].str.fullmatch(r"\d{6}", na=False)
    )
    deal_ym = pd.to_numeric(sales["deal_ym"], errors="coerce")
    keep &= deal_ym.le(PRICE_LAST_YM)   # holdout 보호
    sales = sales[keep].copy()
    area, price = area[keep], price[keep]

    out = pd.DataFrame({
        "dong": sales["sggCd"] + "_" + sales["umdNm"],
        "sggCd": sales["sggCd"],
        "cell": sales["aptSeq"] + "_" + (area // AREA_BIN_M2).astype(int).astype(str),
        "mi": ym_to_mi(sales["deal_ym"].astype(int)),
        "log_ppm2": np.log(price / area),
    }).reset_index(drop=True)
    assert out["mi"].max() <= ym_to_mi(PRICE_LAST_YM), "holdout 가격이 적재됐다"
    return out


def estimate_index(sales, period_col, ridge_lambda=RIDGE_LAMBDA):
    """동×기간 log 지수를 돌려준다. 열: dong, sggCd, period, log_index, n_sales.

    구×기간 효과가 없는(그 구에 거래가 없는) 칸은 NaN이다. 동에 거래가 없으면 편차 0,
    즉 구 지수를 그대로 쓴다. 지수 수준은 해석하지 않고 같은 동 안의 차이만 쓴다.
    """
    period = sales[period_col].to_numpy()
    cell_code, _ = pd.factorize(sales["cell"])
    gp_code, gp_keys = pd.factorize(pd.MultiIndex.from_arrays([sales["sggCd"].to_numpy(), period]))
    dp_code, dp_keys = pd.factorize(pd.MultiIndex.from_arrays([sales["dong"].to_numpy(), period]))

    n_rows, n_cell = len(sales), cell_code.max() + 1
    n_gp, n_dp = len(gp_keys), len(dp_keys)
    design = sparse.csr_matrix(
        (np.ones(3 * n_rows),
         (np.tile(np.arange(n_rows), 3),
          np.concatenate([cell_code, n_cell + gp_code, n_cell + n_gp + dp_code]))),
        shape=(n_rows, n_cell + n_gp + n_dp),
    )
    # ridge는 동×기간 편차 열에만 건다: 해당 열에 sqrt(λ) 가짜 관측(목표 0)을 붙인다
    penalty = sparse.csr_matrix(
        (np.full(n_dp, np.sqrt(ridge_lambda)), (np.arange(n_dp), n_cell + n_gp + np.arange(n_dp))),
        shape=(n_dp, design.shape[1]),
    )
    y = sales["log_ppm2"].to_numpy()
    solution = lsqr(sparse.vstack([design, penalty]).tocsr(), np.concatenate([y, np.zeros(n_dp)]),
                    atol=1e-10, btol=1e-10, iter_lim=20000)
    if solution[1] not in (1, 2):
        raise RuntimeError(f"lsqr 미수렴: istop={solution[1]}, iterations={solution[2]}")
    coef = solution[0]

    gp_effect = pd.Series(coef[n_cell:n_cell + n_gp], index=gp_keys)
    dp_effect = pd.Series(coef[n_cell + n_gp:], index=dp_keys)

    dongs = sales[["dong", "sggCd"]].drop_duplicates("dong")
    grid = dongs.merge(pd.DataFrame({"period": np.unique(period)}), how="cross")
    gp_index = pd.MultiIndex.from_arrays([grid["sggCd"].to_numpy(), grid["period"].to_numpy()])
    dp_index = pd.MultiIndex.from_arrays([grid["dong"].to_numpy(), grid["period"].to_numpy()])
    grid["log_index"] = gp_effect.reindex(gp_index).to_numpy() + dp_effect.reindex(dp_index).fillna(0.0).to_numpy()
    counts = pd.Series(np.bincount(dp_code, minlength=n_dp), index=dp_keys)
    grid["n_sales"] = counts.reindex(dp_index).fillna(0).astype(int).to_numpy()
    return grid


WINDOW_BACK = 35   # 기점 t의 추정 창은 [t−35, t+3]개월
FUTURE = 3


def publication_lag(origin):
    """기점 월 번호의 신고 publication lag. 2020-03 이전 2개월, 이후 1개월이다."""
    cutoff = int(ym_to_mi(202003))
    values = np.asarray(origin)
    out = np.where(values < cutoff, 2, 1)
    return int(out) if out.ndim == 0 else out


def label_periods(window, origin, structure):
    """추정 창 거래에 기간 번호를 붙인다.

    A: 월 번호 그대로. B: t 이하 달은 (t−m)//3 (0이 t−2..t 창), 미래 t+1..t+3은 −1.
    """
    if structure == "A":
        return window["mi"].to_numpy()
    back = (origin - window["mi"].to_numpy()) // 3
    return np.where(window["mi"].to_numpy() > origin, -1, back)


def origin_rows(window, origin, structure, ridge_lambda=RIDGE_LAMBDA):
    """기점 하나의 동별 target·모멘텀·거래량 행을 돌려준다.

    target: A는 I(t+3)−I(t), B는 W(t+1..t+3)−W(t−2..t).
    모멘텀: 최근 3개월(mom_0_3), 3~6개월(mom_3_6), 6~12개월(mom_6_12) 변화.
    창에 t+1..t+3 거래가 없으면(누수 점검용 재추정) y는 NaN이다.
    """
    window = window.assign(period=label_periods(window, origin, structure))
    grid = estimate_index(window, "period", ridge_lambda)
    wide = grid.pivot(index="dong", columns="period", values="log_index")
    get = lambda p: wide[p] if p in wide.columns else pd.Series(np.nan, index=wide.index)
    if structure == "A":
        t = origin
        out = pd.DataFrame({
            "y": get(t + 3) - get(t),
            "mom_0_3": get(t) - get(t - 3),
            "mom_3_6": get(t - 3) - get(t - 6),
            "mom_6_12": get(t - 6) - get(t - 12),
        })
    else:
        out = pd.DataFrame({
            "y": get(-1) - get(0),
            "mom_0_3": get(0) - get(1),
            "mom_3_6": get(1) - get(2),
            "mom_6_12": get(2) - get(4),
        })
    months = window.groupby(["dong", "mi"]).size().unstack(fill_value=0)
    count = lambda lo, hi: months.loc[:, [m for m in months.columns if lo <= m <= hi]].sum(axis=1)
    out["n_3m"] = count(origin - 2, origin)
    out["n_12m"] = count(origin - 11, origin)
    out["n_target"] = count(origin + 1, origin + FUTURE)
    out[["n_3m", "n_12m", "n_target"]] = out[["n_3m", "n_12m", "n_target"]].fillna(0).astype(int)
    out = out.join(grid.drop_duplicates("dong").set_index("dong")["sggCd"])
    out["origin"] = int(mi_to_ym(origin))
    out["structure"] = structure
    return out.reset_index()[["dong", "sggCd", "origin", "structure", "y", "mom_0_3", "mom_3_6", "mom_6_12",
                              "n_3m", "n_12m", "n_target"]]
