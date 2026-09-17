# ============================================================================
# 69.build_dong_support.py
# ============================================================================
# Author:      yjkim
# Purpose:     판단 보조 화면의 1차 산출물 네 가지를 한 파일로 만든다
# Description: docs/feature-spec.md의 F-1~F-4를 구현한다.
#                F-1 표본 주의 flag
#                F-2 오차를 동반한 12개월 변화
#                F-3 구조 유형과 자동 설명
#                F-4 같은 구조 유형 안에서 함께 볼 동 5개
#              모든 자체 검증을 통과한 뒤에만 output/69.1을 쓴다.
# ============================================================================

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import psycopg
from sklearn.preprocessing import StandardScaler

from _dong_cluster import STRUCTURE_COLUMNS, feature_matrix
from _dong_index import load_sales_any
from _dong_weight import dong_households


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"

CONCENTRATION_PATH = output_dir / "62.1.dong_complex_concentration.txt"
CLUSTER_PATH = output_dir / "66.1.dong_cluster.txt"
INDEX_PATH = output_dir / "60.1.dong_index_se.txt"
OUTPUT_PATH = output_dir / "69.1.dong_support.txt"

FEW_SALES_THRESHOLD = 20
DOMINANT_SHARE_THRESHOLD = 0.5
INDEX_SE_LOW_THRESHOLD = 0.016
INDEX_SE_HIGH_THRESHOLD = 0.032
DELTA_SIGMA = 2.0
PEER_COUNT = 5
MIN_CLUSTER_ELIGIBLE = 10

DESCRIPTION_COLUMNS = [
    "log_ppm2",
    "jeonse_ratio",
    "log_stock",
    "new_share",
    "dist_cbd",
    "dist_gangnam",
]

DESCRIPTION_WORDS = {
    "log_ppm2": ("평당가 낮음", "평당가 높음"),
    "jeonse_ratio": ("전세가율 낮음", "전세가율 높음"),
    "log_stock": ("아파트 세대수 적음", "아파트 세대수 많음"),
    "new_share": ("신축 비중 낮음", "신축 비중 높음"),
}

REASON_WORDS = {
    "log_ppm2": "평당가",
    "jeonse_ratio": "전세가율",
    "log_stock": "세대수",
    "new_share": "신축 비중",
    "lat": "위치",
    "lng": "위치",
    "dist_cbd": "도심 거리",
    "dist_gangnam": "강남 거리",
}

INDEX_QUERY = """
    select i.dong, i.quarter, i.log_index, i.log_index_se,
           i.n_sales_4q, i.eligible
    from app.dong_index i
    join app.dataset_snapshot s on s.snapshot_id = i.snapshot_id
    where s.is_active
    order by i.dong, i.quarter
"""

FEATURE_QUERY = """
    select f.dong, f.as_of_quarter, f.sale_ppm2_med_4q, f.jeonse_ratio_4q,
           f.stock_hh, f.completed_hh_8q
    from app.dong_feature f
    join app.dataset_snapshot s on s.snapshot_id = f.snapshot_id
    where s.is_active and f.as_of_quarter = %s
    order by f.dong
"""

BOUNDARY_QUERY = """
    select b.dong, b.centroid_lat, b.centroid_lng
    from app.dong_boundary b
    join app.dataset_snapshot s on s.snapshot_id = b.snapshot_id
    where s.is_active and b.in_index
    order by b.dong
"""

INDEX_SE_COLUMN_QUERY = """
    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'app' and table_name = 'dong_index' and column_name = 'log_index_se'
    )
"""


def database_url(env_name: str = "DATABASE_READONLY_URL") -> str:
    """저장소의 공통 DB URL 로더를 사용한다."""
    loader_path = work_dir / "data" / "db" / "50.load_db.py"
    spec = importlib.util.spec_from_file_location("boomingup_load_db", loader_path)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    return loader.database_url(env_name)


def load_database_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.Period]:
    """active snapshot에서 지수와 최신 구조 변수를 읽는다."""
    with psycopg.connect(database_url()) as connection:
        has_index_se = bool(connection.execute(INDEX_SE_COLUMN_QUERY).fetchone()[0])
        if has_index_se:
            index = pd.DataFrame(
                connection.execute(INDEX_QUERY).fetchall(),
                columns=["dong", "quarter", "log_index", "log_index_se", "n_sales_4q", "eligible"],
            )
        else:
            if not INDEX_PATH.is_file():
                raise FileNotFoundError("DB에 log_index_se가 없고 output/60.1도 없습니다.")
            index = pd.read_csv(
                INDEX_PATH,
                sep="\t",
                usecols=["dong", "quarter", "log_index", "log_index_se", "n_sales_4q", "eligible"],
            )
            print("  DB에 log_index_se가 없어 output/60.1을 사용합니다.")
        if index.empty:
            raise RuntimeError("active snapshot의 dong_index가 비어 있습니다.")
        index["quarter"] = pd.PeriodIndex(index["quarter"], freq="Q")
        as_of = index["quarter"].max()

        features = pd.DataFrame(
            connection.execute(FEATURE_QUERY, (str(as_of),)).fetchall(),
            columns=["dong", "as_of", "ppm2", "jeonse_ratio", "stock_hh", "completed_hh_8q"],
        )
        boundary = pd.DataFrame(
            connection.execute(BOUNDARY_QUERY).fetchall(),
            columns=["dong", "lat", "lng"],
        )

    for column in ["log_index", "log_index_se", "n_sales_4q"]:
        index[column] = pd.to_numeric(index[column], errors="coerce")
    index["eligible"] = index["eligible"].fillna(False).astype(bool)

    for column in ["ppm2", "jeonse_ratio", "stock_hh", "completed_hh_8q"]:
        features[column] = pd.to_numeric(features[column], errors="coerce")
    for column in ["lat", "lng"]:
        boundary[column] = pd.to_numeric(boundary[column], errors="coerce")
    features["as_of"] = pd.PeriodIndex(features["as_of"], freq="Q")
    features["sggCd"] = features["dong"].str.split("_").str[0]
    features = features.merge(boundary, on="dong", how="left", validate="one_to_one")
    return index, features, as_of


def load_file_inputs(as_of: pd.Period) -> tuple[pd.DataFrame, pd.DataFrame]:
    """62번 집중도와 66번 K-S 소속에서 기준 분기 행만 읽는다."""
    if not CONCENTRATION_PATH.is_file() or not CLUSTER_PATH.is_file():
        raise FileNotFoundError("output/62.1과 output/66.1이 먼저 있어야 합니다.")

    concentration = pd.read_csv(CONCENTRATION_PATH, sep="\t")
    concentration["as_of_quarter"] = pd.PeriodIndex(concentration["as_of_quarter"], freq="Q")
    concentration = concentration[concentration["as_of_quarter"] == as_of].copy()
    for column in ["n_complexes_4q", "sale_n_all_4q", "dominant_complex_share_4q"]:
        concentration[column] = pd.to_numeric(concentration[column], errors="coerce")

    membership = pd.read_csv(CLUSTER_PATH, sep="\t")
    membership["as_of"] = pd.PeriodIndex(membership["as_of"], freq="Q")
    membership = membership[membership["as_of"] == as_of].copy()
    membership["cluster"] = pd.to_numeric(membership["cluster"], errors="coerce").astype("Int64")
    return concentration, membership


def sample_flags(sale_n_all_4q: int, dominant_share: float | None, index_se: float) -> list[str]:
    """F-1 세 flag를 문서에 정한 순서로 돌려준다."""
    flags = []
    if sale_n_all_4q < FEW_SALES_THRESHOLD:
        flags.append("FEW_SALES")
    if sale_n_all_4q >= 1 and pd.notna(dominant_share) and dominant_share > DOMINANT_SHARE_THRESHOLD:
        flags.append("ONE_COMPLEX_DOMINATES")
    if index_se >= INDEX_SE_HIGH_THRESHOLD:
        flags.append("HIGH_INDEX_ERROR")
    return flags


def index_se_band(index_se: float) -> str:
    """고정 문턱 0.016·0.032로 지수 추정오차 구간을 만든다."""
    if index_se < INDEX_SE_LOW_THRESHOLD:
        return "LOW"
    if index_se < INDEX_SE_HIGH_THRESHOLD:
        return "MID"
    return "HIGH"


def has_final_consonant(word: str) -> bool:
    """마지막 한글 음절에 받침이 있는지 확인한다."""
    code = ord(word[-1])
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


def with_particle(word: str, consonant: str, vowel: str) -> str:
    return f"{word}{consonant if has_final_consonant(word) else vowel}"


def structure_description(cluster: int, matrix: pd.DataFrame, membership: pd.Series) -> str:
    """클러스터 중앙값의 서울 대비 표준화 편차가 큰 변수 두 개를 설명한다."""
    indexed = matrix.set_index("dong")
    members = membership[membership == cluster].index.intersection(indexed.index)
    overall_median = indexed[DESCRIPTION_COLUMNS].median()
    overall_sd = indexed[DESCRIPTION_COLUMNS].std(ddof=0).replace(0, np.nan)
    z = ((indexed.loc[members, DESCRIPTION_COLUMNS].median() - overall_median) / overall_sd).fillna(0.0)
    order = sorted(DESCRIPTION_COLUMNS, key=lambda column: (-abs(z[column]), DESCRIPTION_COLUMNS.index(column)))[:2]

    phrases = []
    cluster_median = indexed.loc[members, DESCRIPTION_COLUMNS].median()
    for column in order:
        if column == "dist_cbd":
            phrases.append(f"도심 {int(round(cluster_median[column]))}km대")
        elif column == "dist_gangnam":
            phrases.append(f"강남 {int(round(cluster_median[column]))}km대")
        else:
            negative, positive = DESCRIPTION_WORDS[column]
            phrases.append(positive if z[column] > 0 else negative)
    return " · ".join(phrases)


def peer_reason(contributions: pd.Series) -> str:
    """거리 기여가 작은 서로 다른 개념 두 개를 골라 이유 문장을 만든다."""
    concepts = []
    for column in sorted(STRUCTURE_COLUMNS, key=lambda name: (contributions[name], STRUCTURE_COLUMNS.index(name))):
        concept = REASON_WORDS[column]
        if concept not in concepts:
            concepts.append(concept)
        if len(concepts) == 2:
            break
    first, second = concepts
    return f"{with_particle(first, '과', '와')} {with_particle(second, '이', '가')} 가까워요"


def build_structure_and_peers(
    support: pd.DataFrame,
    matrix: pd.DataFrame,
    membership_frame: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, pd.Series, dict[str, list[dict[str, str]]]]:
    """F-3 구조 설명과 F-4 최근접 동을 계산한다."""
    membership = membership_frame.set_index("dong")["cluster"].dropna().astype(int)
    indexed = matrix.set_index("dong")
    descriptions = {
        int(cluster): structure_description(int(cluster), matrix, membership)
        for cluster in sorted(membership.unique())
    }
    structure_type = support["dong"].map(membership).astype("Int64")
    structure_desc = structure_type.map(descriptions)

    scaler = StandardScaler()
    scaled = pd.DataFrame(
        scaler.fit_transform(indexed[STRUCTURE_COLUMNS]),
        index=indexed.index,
        columns=STRUCTURE_COLUMNS,
    )
    eligible = support.set_index("dong")["eligible"].astype(bool)
    eligible_by_cluster = membership[eligible.reindex(membership.index).fillna(False)].groupby(membership).size()

    peer_map: dict[str, list[dict[str, str]]] = {}
    peer_json = pd.Series(index=support.index, dtype="object")
    for row_index, row in support.iterrows():
        dong = row["dong"]
        cluster = membership.get(dong)
        if pd.isna(cluster) or dong not in scaled.index or not bool(row["eligible"]):
            continue
        if int(eligible_by_cluster.get(int(cluster), 0)) < MIN_CLUSTER_ELIGIBLE:
            continue

        candidates = membership[(membership == int(cluster)) & eligible.reindex(membership.index).fillna(False)].index
        candidates = candidates.intersection(scaled.index).difference(pd.Index([dong]))
        differences = scaled.loc[candidates] - scaled.loc[dong]
        distance = np.sqrt((differences ** 2).sum(axis=1))
        nearest = pd.DataFrame({"dong": candidates, "distance": distance.to_numpy()}).sort_values(
            ["distance", "dong"], kind="stable"
        ).head(PEER_COUNT)

        peers = []
        for peer in nearest["dong"]:
            contributions = (scaled.loc[dong] - scaled.loc[peer]) ** 2
            peers.append({"dong": peer, "reason": peer_reason(contributions)})
        peer_map[dong] = peers
        peer_json.loc[row_index] = json.dumps(peers, ensure_ascii=False, separators=(",", ":"))
    return structure_type, structure_desc, peer_json, peer_map


def build_support(
    index: pd.DataFrame,
    concentration: pd.DataFrame,
    membership: pd.DataFrame,
    matrix: pd.DataFrame,
    weights: pd.Series,
    as_of: pd.Period,
) -> tuple[pd.DataFrame, dict[str, list[dict[str, str]]]]:
    """F-1~F-4를 합쳐 최종 346행을 만든다."""
    current = index[index["quarter"] == as_of].copy()
    previous = index[index["quarter"] == as_of - 4].set_index("dong")
    current = current.merge(
        concentration[["dong", "n_complexes_4q", "sale_n_all_4q", "dominant_complex_share_4q"]],
        on="dong",
        how="left",
        validate="one_to_one",
    ).sort_values("dong").reset_index(drop=True)

    current["n_complexes_4q"] = current["n_complexes_4q"].astype("Int64")
    current["sale_n_all_4q"] = current["sale_n_all_4q"].astype("Int64")
    current["sample_flag_list"] = current.apply(
        lambda row: sample_flags(
            int(row["sale_n_all_4q"]), row["dominant_complex_share_4q"], float(row["log_index_se"])
        ),
        axis=1,
    )
    current["sample_flags"] = current["sample_flag_list"].map(lambda values: ";".join(values))
    current["index_se_band"] = current["log_index_se"].map(index_se_band)

    current["previous_index"] = current["dong"].map(previous["log_index"])
    current["previous_se"] = current["dong"].map(previous["log_index_se"])
    current["change_12m"] = current["log_index"] - current["previous_index"]
    current["delta_se"] = np.sqrt(current["log_index_se"] ** 2 + current["previous_se"] ** 2)

    weight = current["dong"].map(weights)
    mu_rows = current["change_12m"].notna() & weight.notna() & weight.gt(0)
    if not mu_rows.any():
        raise RuntimeError("세대수 가중 μ를 계산할 동이 없습니다.")
    mu_12m = float(np.average(current.loc[mu_rows, "change_12m"], weights=weight[mu_rows]))
    current["mu_12m"] = mu_12m
    current["delta_12m"] = current["change_12m"] - mu_12m
    current["delta_state"] = np.where(
        current["change_12m"].notna() & current["delta_12m"].abs().gt(DELTA_SIGMA * current["delta_se"]),
        "DISTINGUISHABLE",
        "INDISTINGUISHABLE",
    )
    current.loc[current["change_12m"].isna(), "delta_state"] = None

    peak_rows = []
    window = index[(index["quarter"] >= as_of - 19) & (index["quarter"] <= as_of)]
    for dong, history in window.groupby("dong", sort=False):
        if history["quarter"].nunique() < 20:
            peak_rows.append({"dong": dong})
            continue
        peak = history.sort_values(["log_index", "quarter"], ascending=[False, False]).iloc[0]
        now = history[history["quarter"] == as_of].iloc[0]
        gap = float(now["log_index"] - peak["log_index"])
        gap_se = float(np.sqrt(now["log_index_se"] ** 2 + peak["log_index_se"] ** 2))
        state = "AT_PEAK" if peak["quarter"] == as_of else (
            "DISTINGUISHABLE" if abs(gap) > DELTA_SIGMA * gap_se else "INDISTINGUISHABLE"
        )
        peak_rows.append({
            "dong": dong,
            "peak_quarter": peak["quarter"],
            "peak_5y_gap": gap,
            "peak_5y_gap_se": gap_se,
            "peak_5y_state": state,
        })
    current = current.merge(pd.DataFrame(peak_rows), on="dong", how="left", validate="one_to_one")
    hide_peak = current["sample_flag_list"].map(
        lambda values: "FEW_SALES" in values or "HIGH_INDEX_ERROR" in values
    )
    current.loc[hide_peak, ["peak_5y_gap", "peak_5y_gap_se", "peak_5y_state"]] = None

    structure_type, structure_desc, peer_json, peer_map = build_structure_and_peers(
        current, matrix, membership
    )
    current["structure_type"] = structure_type
    current["structure_desc"] = structure_desc
    current["peer_dongs"] = peer_json
    current["as_of"] = str(as_of)
    current["index_se"] = current["log_index_se"]

    columns = [
        "dong", "as_of", "sale_n_all_4q", "n_complexes_4q", "dominant_complex_share_4q",
        "index_se", "index_se_band", "sample_flags", "change_12m", "mu_12m",
        "delta_12m", "delta_se", "delta_state", "peak_5y_gap", "peak_5y_gap_se",
        "peak_5y_state", "structure_type", "structure_desc", "peer_dongs",
    ]
    return current[columns], peer_map


def validate_concentration_against_sales(support: pd.DataFrame, as_of: pd.Period) -> None:
    """62번과 같은 방식으로 표본 3개 동의 원장 집계를 다시 확인한다."""
    sales, _ = load_sales_any(work_dir)
    sales = sales[sales["quarter"] <= as_of]
    sample = support[support["sale_n_all_4q"] > 0].sample(3, random_state=20260917)
    for _, row in sample.iterrows():
        raw = sales[
            (sales["dong"] == row["dong"])
            & (sales["quarter"] > as_of - 4)
            & (sales["quarter"] <= as_of)
        ]
        assert raw["aptSeq"].nunique() == row["n_complexes_4q"], f"{row['dong']}: 단지 수 불일치"
        expected_share = raw["aptSeq"].value_counts().iloc[0] / len(raw)
        assert abs(expected_share - row["dominant_complex_share_4q"]) < 1e-12, (
            f"{row['dong']}: 집중도 불일치"
        )


def validate_support(
    support: pd.DataFrame,
    index: pd.DataFrame,
    membership_frame: pd.DataFrame,
    weights: pd.Series,
    peer_map: dict[str, list[dict[str, str]]],
    as_of: pd.Period,
) -> dict[str, object]:
    """feature-spec §1.7~§4.7의 불변식을 검사한다."""
    assert len(support) == 346, f"동 행 수가 346이 아닙니다: {len(support)}"
    assert support["dong"].is_unique, "동이 중복됐습니다."
    assert support["index_se"].notna().all(), "index_se 결측 동이 있습니다."

    latest = index[index["quarter"] == as_of].set_index("dong")
    counted = support.set_index("dong")
    assert counted["sale_n_all_4q"].astype(float).equals(
        latest.loc[counted.index, "n_sales_4q"].astype(float)
    ), "62번 거래 수와 dong_index.n_sales_4q가 다릅니다."
    zero_sales = support["sale_n_all_4q"] == 0
    assert not support.loc[zero_sales, "sample_flags"].str.contains("ONE_COMPLEX_DOMINATES").any()
    few_sales = support["sample_flags"].str.contains("FEW_SALES")
    few_not_high = support.loc[few_sales, "index_se_band"].ne("HIGH")
    assert int(few_sales.sum()) == 100, f"FEW_SALES 동이 100개가 아닙니다: {int(few_sales.sum())}"
    assert int(few_not_high.sum()) == 3, (
        f"FEW_SALES 중 HIGH가 아닌 동이 3개가 아닙니다: {int(few_not_high.sum())}"
    )

    boundary_flags = {
        "11140_묵정동": (set(), "MID"),
        "11710_삼전동": ({"FEW_SALES", "HIGH_INDEX_ERROR"}, "HIGH"),
        "11170_후암동": (set(), "MID"),
        "11170_서빙고동": ({"HIGH_INDEX_ERROR"}, "HIGH"),
    }
    for dong, (required_flags, band) in boundary_flags.items():
        row = counted.loc[dong]
        actual_flags = set(filter(None, row["sample_flags"].split(";")))
        assert required_flags.issubset(actual_flags), f"{dong}: 필수 flag가 없습니다."
        assert not ({"FEW_SALES", "HIGH_INDEX_ERROR"} - required_flags) & actual_flags, (
            f"{dong}: 경계와 맞지 않는 flag가 있습니다."
        )
        assert row["index_se_band"] == band, f"{dong}: SE band가 다릅니다."
    for dong in ["11200_금호동2가", "11200_송정동"]:
        assert "ONE_COMPLEX_DOMINATES" not in counted.loc[dong, "sample_flags"]
    for dong in ["11140_충무로5가", "11200_금호동1가", "11110_평동"]:
        assert "ONE_COMPLEX_DOMINATES" in counted.loc[dong, "sample_flags"]

    current = index[index["quarter"] == as_of].set_index("dong")
    previous = index[index["quarter"] == as_of - 4].set_index("dong")
    expected_delta_se = np.sqrt(
        current.loc[counted.index, "log_index_se"] ** 2 + previous.loc[counted.index, "log_index_se"] ** 2
    )
    assert np.allclose(counted["delta_se"], expected_delta_se)
    assert (counted["delta_se"] >= np.maximum(
        current.loc[counted.index, "log_index_se"], previous.loc[counted.index, "log_index_se"]
    )).all()
    valid_weight = weights.reindex(counted.index).notna() & weights.reindex(counted.index).gt(0)
    weighted_delta = np.average(counted.loc[valid_weight, "delta_12m"], weights=weights.reindex(counted.index)[valid_weight])
    assert abs(weighted_delta) < 1e-12, f"δ 세대수 가중 평균이 0이 아닙니다: {weighted_delta}"
    assert counted["peak_5y_gap"].dropna().le(1e-12).all()
    hidden_peak = counted["sample_flags"].str.contains("FEW_SALES|HIGH_INDEX_ERROR", regex=True)
    assert counted.loc[hidden_peak, ["peak_5y_gap", "peak_5y_gap_se", "peak_5y_state"]].isna().all().all()

    eligible = latest.loc[counted.index, "eligible"].astype(bool)
    distinguishable = counted["delta_state"].eq("DISTINGUISHABLE")
    assert distinguishable[eligible].mean() > distinguishable[~eligible].mean()

    expected_membership = membership_frame.set_index("dong")["cluster"].astype("Int64")
    assert counted["structure_type"].equals(expected_membership.reindex(counted.index))
    descriptions = counted.dropna(subset=["structure_type"]).groupby("structure_type")["structure_desc"].first()
    assert descriptions.nunique() == len(descriptions) == 4
    assert "신축" in descriptions.loc[2]

    for dong, peers in peer_map.items():
        assert len(peers) == PEER_COUNT, f"{dong}: peer가 5개가 아닙니다."
        cluster = int(counted.loc[dong, "structure_type"])
        for peer in peers:
            assert peer["dong"] != dong
            assert bool(latest.loc[peer["dong"], "eligible"])
            assert int(counted.loc[peer["dong"], "structure_type"]) == cluster
    cluster_two = counted[counted["structure_type"] == 2]
    assert cluster_two["peer_dongs"].isna().all()
    assert counted.loc[~eligible, "peer_dongs"].isna().all()

    same_gu = []
    for dong, peers in peer_map.items():
        gu = dong.split("_", 1)[0]
        same_count = sum(peer["dong"].split("_", 1)[0] == gu for peer in peers)
        if same_count >= 4:
            same_gu.append((dong, same_count, [peer["dong"] for peer in peers]))
    return {
        "zero_sales": int(zero_sales.sum()),
        "few_sales": int(few_sales.sum()),
        "few_not_high": int(few_not_high.sum()),
        "distinguishable": int(distinguishable.sum()),
        "eligible_distinguishable": int(distinguishable[eligible].sum()),
        "ineligible_distinguishable": int(distinguishable[~eligible].sum()),
        "peer_rows": len(peer_map),
        "same_gu": same_gu,
    }


def main() -> None:
    print("===== 1. 판단 보조 입력 적재 =====")
    index, raw_features, as_of = load_database_inputs()
    concentration, membership = load_file_inputs(as_of)
    weights, coverage = dong_households(work_dir)
    matrix = feature_matrix(raw_features)
    print(f"  기준 분기 {as_of}, 지수 동 {index[index['quarter'] == as_of]['dong'].nunique()}개")
    print(f"  구조 행렬 {len(matrix)}개 동, 세대수 매핑 커버리지 {coverage:.1%}")

    print("\n===== 2. F-1~F-4 산출 =====")
    support, peer_map = build_support(index, concentration, membership, matrix, weights, as_of)
    print(f"  산출 {len(support)}행")

    print("\n===== 3. 자체 검증 =====")
    validate_concentration_against_sales(support, as_of)
    report = validate_support(support, index, membership, weights, peer_map, as_of)
    print(
        f"  매매 0건 {report['zero_sales']}개, FEW_SALES {report['few_sales']}개 "
        f"(HIGH 아닌 동 {report['few_not_high']}개)"
    )
    print(
        f"  DISTINGUISHABLE {report['distinguishable']}개 "
        f"(eligible {report['eligible_distinguishable']}, 비eligible {report['ineligible_distinguishable']})"
    )
    print(f"  peer 표시 {report['peer_rows']}개 동")

    same_gu = report["same_gu"]
    rate = len(same_gu) / report["peer_rows"] if report["peer_rows"] else 0.0
    print(f"  peer 5개 중 같은 자치구 4개 이상: {len(same_gu)}개 동 ({rate:.1%})")
    for dong, same_count, peers in same_gu[:3]:
        print(f"    {dong}: 같은 구 {same_count}개 — {', '.join(peers)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    support.to_csv(OUTPUT_PATH, sep="\t", index=False, lineterminator="\n", na_rep="")
    print(f"\n산출물: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
