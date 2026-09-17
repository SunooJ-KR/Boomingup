# ============================================================================
# _dong_index.py
# ============================================================================
# Author:      yjkim
# Purpose:     법정동×분기 가격 지수(hedonic, 반복거래)를 추정하는 공용 함수
# Description: 40(전체 데이터 target 지수)과 이후 feature 단계(기점별 vintage 지수)가
#              같은 추정식을 쓰도록 한 곳에 둔다. 사전 등록: docs/decisions.md 결정 5.
#              - hedonic: log(가격/㎡) = 단지×면적bin FE + 구×분기 + 동×분기 편차(ridge λ)
#              - 반복거래: 같은 단지×면적bin의 연속 거래 쌍 (점검용)
# ============================================================================

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import lsqr

AREA_BIN_M2 = 3        # 1㎡ 반올림은 84.6/85.0㎡처럼 같은 평형을 가르고, 5㎡ 폭은 다른 평형을 섞는다
RIDGE_LAMBDA = 5       # 결정 5a
SALE_COLUMNS = ["aptSeq", "sggCd", "umdNm", "excluUseAr", "deal_ym", "dealDay", "is_cancelled", "deal_amount_manwon"]
SALES_FRAME_COLUMNS = ["dong", "sggCd", "umdNm", "aptSeq", "cell", "quarter", "deal_date", "log_ppm2"]


def load_sales(path):
    """취소 제외·가격/면적 양수·aptSeq 있는 매매만 남기고 동·분기·셀 키를 붙인다."""
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
    sales = sales[keep].copy()
    area = area[keep]
    price = price[keep]

    sales["dong"] = sales["sggCd"] + "_" + sales["umdNm"]
    sales["quarter"] = pd.to_datetime(sales["deal_ym"], format="%Y%m").dt.to_period("Q")
    sales["cell"] = sales["aptSeq"] + "_" + (area // AREA_BIN_M2).astype(int).astype(str)
    sales["deal_date"] = pd.to_datetime(
        sales["deal_ym"] + sales["dealDay"].str.zfill(2), format="%Y%m%d", errors="coerce")
    sales["log_ppm2"] = np.log(price / area)
    return sales[SALES_FRAME_COLUMNS].reset_index(drop=True)


def load_sales_from_db(work_dir):
    """활성 sale batch를 읽어 load_sales와 같은 모양으로 돌려준다."""
    import importlib.util
    import psycopg

    loader_path = work_dir / "data" / "db" / "50.load_db.py"
    spec = importlib.util.spec_from_file_location("boomingup_load_db", loader_path)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)

    query = """
        select t.sgg_cd, t.umd_nm, t.apt_seq, t.exclu_use_ar, t.deal_ym, t.deal_day,
               t.deal_amount_manwon
        from app.trade_sale t
        join app.trade_batch b on b.batch_id = t.batch_id
        where b.kind = 'sale' and b.is_active
          and t.is_cancelled is not true
          and t.apt_seq is not null and t.sgg_cd is not null and t.umd_nm is not null
          and t.exclu_use_ar > 0 and t.deal_amount_manwon > 0
          and t.deal_ym ~ '^[0-9]{6}$'
        -- 정렬이 없으면 실행마다 행 순서가 달라져 factorize 코드와 무작위 분할이 흔들린다
        order by t.batch_id, t.row_no
    """
    with psycopg.connect(loader.database_url("DATABASE_READONLY_URL")) as connection:
        sales = pd.DataFrame(
            connection.execute(query).fetchall(),
            columns=["sggCd", "umdNm", "aptSeq", "excluUseAr", "deal_ym", "dealDay",
                     "deal_amount_manwon"],
        )

    area = pd.to_numeric(sales["excluUseAr"], errors="coerce")
    price = pd.to_numeric(sales["deal_amount_manwon"], errors="coerce")
    sales["dong"] = sales["sggCd"] + "_" + sales["umdNm"]
    sales["quarter"] = pd.to_datetime(sales["deal_ym"], format="%Y%m").dt.to_period("Q")
    sales["cell"] = sales["aptSeq"] + "_" + (area // AREA_BIN_M2).astype(int).astype(str)
    sales["deal_date"] = pd.to_datetime(
        sales["deal_ym"] + sales["dealDay"].astype("string").str.zfill(2),
        format="%Y%m%d", errors="coerce")
    sales["log_ppm2"] = np.log(price / area)
    return sales[SALES_FRAME_COLUMNS].reset_index(drop=True)


def load_sales_any(work_dir):
    """매매 원장을 읽고 (원장, 원천 설명)을 돌려준다.

    output/11.1이 있으면 그것을 쓰고, 없으면 DB의 활성 sale batch를 읽는다.
    수집 스크립트를 돌린 사람과 DB만 있는 사람이 같은 코드를 쓰게 하려는 것이다.
    """
    sales_file = work_dir / "output" / "11.1.trades_sale.txt"
    if sales_file.is_file():
        return load_sales(sales_file), str(sales_file.relative_to(work_dir))
    return load_sales_from_db(work_dir), "DB app.trade_sale (활성 batch)"


def _solve(matrix, target, **kwargs):
    solution = lsqr(matrix, target, atol=1e-10, btol=1e-10, iter_lim=20000, **kwargs)
    coef, istop, n_iter = solution[0], solution[1], solution[2]
    if istop not in (1, 2):   # 7 = 반복 한도 도달. 수렴하지 않은 지수를 조용히 쓰지 않는다
        raise RuntimeError(f"lsqr 미수렴: istop={istop}, iterations={n_iter}")
    return coef, istop, n_iter


def estimate_hedonic_index(sales, ridge_lambda=RIDGE_LAMBDA, with_components=False):
    """동×분기 log 지수 격자와 진단값을 돌려준다.

    구×분기 효과와 단지 FE는 구마다 상수 하나만큼 식별되지 않지만, 같은 동 안의
    시점 간 차이(변화율)에서는 상쇄된다. 지수 수준 자체는 해석하지 않는다.
    거래가 없는 동×분기는 편차 0, 즉 구 지수를 그대로 쓴다.
    """
    quarter_str = sales["quarter"].astype(str)
    cell_code, cell_keys = pd.factorize(sales["cell"])
    gq_code, gq_keys = pd.factorize(sales["sggCd"] + "|" + quarter_str)
    dq_code, dq_keys = pd.factorize(sales["dong"] + "|" + quarter_str)

    n_rows = len(sales)
    n_cell = cell_code.max() + 1
    n_gq, n_dq = len(gq_keys), len(dq_keys)
    n_col = n_cell + n_gq + n_dq

    design = sparse.csr_matrix(
        (np.ones(3 * n_rows),
         (np.tile(np.arange(n_rows), 3),
          np.concatenate([cell_code, n_cell + gq_code, n_cell + n_gq + dq_code]))),
        shape=(n_rows, n_col),
    )
    # ridge를 동×분기 편차 열에만 거는 방법: 해당 열에 sqrt(λ) 가짜 관측(목표 0)을 붙인다
    penalty = sparse.csr_matrix(
        (np.full(n_dq, np.sqrt(ridge_lambda)), (np.arange(n_dq), n_cell + n_gq + np.arange(n_dq))),
        shape=(n_dq, n_col),
    )
    y = sales["log_ppm2"].to_numpy()
    coef, istop, n_iter = _solve(sparse.vstack([design, penalty]).tocsr(), np.concatenate([y, np.zeros(n_dq)]))

    gq_effect = pd.Series(coef[n_cell:n_cell + n_gq], index=gq_keys)
    dq_effect = pd.Series(coef[n_cell + n_gq:], index=dq_keys)

    dongs = sales[["dong", "sggCd", "umdNm"]].drop_duplicates("dong")
    quarters = pd.period_range(sales["quarter"].min(), sales["quarter"].max(), freq="Q")
    grid = dongs.merge(pd.DataFrame({"quarter": quarters}), how="cross")
    grid_q = grid["quarter"].astype(str)
    # dq_effect(동 편차)는 SE 계산(_dong_index_se.py)이 따로 필요로 해서 컬럼으로 남긴다
    grid["dq_effect"] = (grid["dong"] + "|" + grid_q).map(dq_effect).fillna(0.0)
    grid["log_index"] = (grid["sggCd"] + "|" + grid_q).map(gq_effect) + grid["dq_effect"]
    counts = sales.groupby(["dong", "quarter"]).size().rename("n_sales").reset_index()
    grid = grid.merge(counts, on=["dong", "quarter"], how="left")
    grid["n_sales"] = grid["n_sales"].fillna(0).astype(int)

    residual = y - design @ coef
    diagnostics = {
        "lsqr_istop": int(istop), "lsqr_iterations": int(n_iter),
        "residual_sd": float(residual.std()), "n_sales": n_rows, "n_cells": int(n_cell),
    }
    grid = grid.sort_values(["dong", "quarter"]).reset_index(drop=True)
    if not with_components:
        return grid, diagnostics
    # nowcast(65)는 단지 고정효과만 재사용하고 분기 효과를 부분 표본으로 다시 계산한다
    components = {"cell_effect": pd.Series(coef[:n_cell], index=cell_keys),
                  "gq_effect": gq_effect, "dq_effect": dq_effect}
    return grid, diagnostics, components


def estimate_repeat_sales_index(sales):
    """동×분기 반복거래 log 지수를 'dong|quarter' 키 Series로 돌려준다. 동마다 상수는 임의다."""
    ordered = sales.sort_values(["cell", "quarter"])
    prev_quarter = ordered.groupby("cell")["quarter"].shift()
    prev_value = ordered.groupby("cell")["log_ppm2"].shift()
    is_pair = prev_quarter.notna() & (prev_quarter != ordered["quarter"])
    pairs = ordered[is_pair]

    sell_key = pairs["dong"] + "|" + pairs["quarter"].astype(str)
    buy_key = pairs["dong"] + "|" + prev_quarter[is_pair].astype(str)
    codes, keys = pd.factorize(pd.concat([sell_key, buy_key], ignore_index=True))
    n_pairs = len(pairs)
    design = sparse.csr_matrix(
        (np.concatenate([np.ones(n_pairs), -np.ones(n_pairs)]), (np.tile(np.arange(n_pairs), 2), codes)),
        shape=(n_pairs, len(keys)),
    )
    y = (pairs["log_ppm2"] - prev_value[is_pair]).to_numpy()
    # 동마다 상수가 식별되지 않고 거래 쌍으로 이어지지 않은 분기도 있어 아주 작은 damp로 해를 고정한다
    coef, _, _ = _solve(design, y, damp=1e-4)
    return pd.Series(coef, index=keys)
