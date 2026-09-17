# ============================================================================
# test_69.py
# ============================================================================
# Author:      yjkim
# Purpose:     판단 보조 산출물의 문턱·경계 사례·비교 동 불변식을 고정한다
# Description: docs/feature-spec.md §1.6~§4.7의 2026Q2 사례를 검사한다.
#              먼저 69.build_dong_support.py를 실행해 output/69.1을 만든다.
# ============================================================================

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "output" / "69.1.dong_support.txt"


def support_module():
    path = Path(__file__).with_name("69.build_dong_support.py")
    spec = importlib.util.spec_from_file_location("dong_support_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_support() -> pd.DataFrame:
    if not OUTPUT_PATH.is_file():
        raise FileNotFoundError("먼저 models/index/69.build_dong_support.py를 실행하세요.")
    frame = pd.read_csv(OUTPUT_PATH, sep="\t", dtype={"dong": str})
    frame["sample_flags"] = frame["sample_flags"].fillna("")
    return frame.set_index("dong")


def test_threshold_boundaries(module) -> None:
    assert module.sample_flags(19, 0.5, 0.031) == ["FEW_SALES"]
    assert module.sample_flags(20, 0.5, 0.031) == []
    assert module.sample_flags(20, 0.500001, 0.031) == ["ONE_COMPLEX_DOMINATES"]
    assert module.sample_flags(20, None, 0.032) == ["HIGH_INDEX_ERROR"]
    assert module.index_se_band(0.015999) == "LOW"
    assert module.index_se_band(0.016) == "MID"
    assert module.index_se_band(0.031999) == "MID"
    assert module.index_se_band(0.032) == "HIGH"


def test_sample_boundary_dongs(frame: pd.DataFrame) -> None:
    expected = {
        "11140_묵정동": (20, "MID", {"ONE_COMPLEX_DOMINATES"}),
        "11710_삼전동": (19, "HIGH", {"FEW_SALES", "HIGH_INDEX_ERROR"}),
        "11200_금호동2가": (80, "MID", set()),
        "11200_송정동": (54, "MID", set()),
        "11140_충무로5가": (22, "HIGH", {"ONE_COMPLEX_DOMINATES", "HIGH_INDEX_ERROR"}),
        "11200_금호동1가": (170, "LOW", {"ONE_COMPLEX_DOMINATES"}),
        "11110_평동": (22, "HIGH", {"ONE_COMPLEX_DOMINATES", "HIGH_INDEX_ERROR"}),
        "11170_후암동": (24, "MID", {"ONE_COMPLEX_DOMINATES"}),
        "11170_서빙고동": (34, "HIGH", {"ONE_COMPLEX_DOMINATES", "HIGH_INDEX_ERROR"}),
    }
    for dong, (sales, band, flags) in expected.items():
        row = frame.loc[dong]
        actual_flags = set(filter(None, row["sample_flags"].split(";")))
        assert int(row["sale_n_all_4q"]) == sales, dong
        assert row["index_se_band"] == band, dong
        assert actual_flags == flags, dong

    few = frame["sample_flags"].str.contains("FEW_SALES")
    assert int(few.sum()) == 100
    assert int(frame.loc[few, "index_se_band"].ne("HIGH").sum()) == 3


def test_change_boundary_dongs(frame: pd.DataFrame) -> None:
    expected_delta = {
        "11290_하월곡동": "DISTINGUISHABLE",
        "11470_목동": "INDISTINGUISHABLE",
        "11305_번동": "INDISTINGUISHABLE",
        "11560_영등포동3가": "DISTINGUISHABLE",
        "11290_삼선동4가": "DISTINGUISHABLE",
    }
    for dong, state in expected_delta.items():
        assert frame.loc[dong, "delta_state"] == state, dong

    assert frame.loc["11140_황학동", "peak_5y_state"] == "DISTINGUISHABLE"
    for dong in ["11140_중림동", "11140_흥인동", "11110_효제동"]:
        assert pd.isna(frame.loc[dong, "peak_5y_state"]), dong
        assert pd.isna(frame.loc[dong, "peak_5y_gap"]), dong


def test_structure_and_peers(frame: pd.DataFrame) -> None:
    descriptions = frame.groupby("structure_type")["structure_desc"].first()
    assert len(descriptions) == descriptions.nunique() == 4
    assert "신축" in descriptions.loc[2]

    cluster_two = ["11230_신설동", "11290_동선동1가", "11500_공항동", "11560_영등포동2가"]
    assert frame.loc[cluster_two, "structure_type"].eq(2).all()
    assert frame.loc[cluster_two, "peer_dongs"].isna().all()
    assert pd.isna(frame.loc["11710_삼전동", "peer_dongs"])

    shown = frame["peer_dongs"].dropna()
    assert len(shown) == 245
    for dong, encoded in shown.items():
        peers = json.loads(encoded)
        assert len(peers) == 5, dong
        assert dong not in {peer["dong"] for peer in peers}, dong
        for peer in peers:
            assert frame.loc[peer["dong"], "sale_n_all_4q"] >= 20, (dong, peer)
            assert frame.loc[peer["dong"], "structure_type"] == frame.loc[dong, "structure_type"], (dong, peer)
            assert peer["reason"].endswith("가까워요"), (dong, peer)


def main() -> None:
    module = support_module()
    frame = load_support()
    assert len(frame) == 346
    test_threshold_boundaries(module)
    test_sample_boundary_dongs(frame)
    test_change_boundary_dongs(frame)
    test_structure_and_peers(frame)
    print("69 판단 보조 산출물 점검 통과: 문턱, 경계 사례, 구조 유형, 함께 볼 동")


if __name__ == "__main__":
    main()
