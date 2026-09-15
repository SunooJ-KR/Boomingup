# ============================================================================
# test_event_study.py
# ============================================================================
# Author:      yjkim
# Purpose:     이벤트별 동 가격 지수 변화 계산을 합성 데이터로 점검한다
# ============================================================================

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

script_path = Path(__file__).with_name("46.event_study.py")
spec = importlib.util.spec_from_file_location("event_study", script_path)
event_study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(event_study)


def make_index():
    quarters = pd.period_range("1999Q1", "2002Q4", freq="Q")
    rows = []
    for dong, slope in [("11110_A동", 0.01), ("11110_B동", 0.02), ("11110_C동", -0.005), ("11110_D동", 0.03)]:
        for position, quarter in enumerate(quarters):
            # E1의 기준 분기(2001Q3)에서만 B는 제외하고 C는 포함한다.
            eligible = (
                False if dong == "11110_D동"
                else False if dong == "11110_B동" and quarter == pd.Period("2001Q3", freq="Q")
                else True if dong == "11110_C동" and quarter == pd.Period("2001Q3", freq="Q")
                else dong != "11110_C동"
            )
            rows.append({
                "dong": dong,
                "sggCd": "11110",
                "umdNm": dong[-2:],
                "quarter": str(quarter),
                "log_index": 5.0 + slope * position,
                "n_sales": 10,
                "n_sales_4q": 40,
                "eligible": eligible,
            })
    return pd.DataFrame(rows)


def make_events():
    return pd.DataFrame([
        {"event_id": "E1", "effective_date": "2001-10-15", "category": "test", "label": "첫 이벤트", "verified": "True", "source": "합성"},
        {"event_id": "E2", "effective_date": "2002-10-15", "category": "test", "label": "끝 이벤트", "verified": "True", "source": "합성"},
        {"event_id": "E3", "effective_date": "1998-10-15", "category": "test", "label": "범위 밖 이벤트", "verified": "True", "source": "합성"},
    ])


def main():
    paths, summary = event_study.calculate_event_study(make_index(), make_events())
    e1_paths = paths[paths["event_id"] == "E1"]
    e1_a_k0 = e1_paths.loc[(e1_paths["dong"] == "11110_A동") & (e1_paths["k"] == 0), "rel_log_change"].iloc[0]
    e1 = summary.loc[summary["event_id"] == "E1"].iloc[0]
    e2 = summary.loc[summary["event_id"] == "E2"].iloc[0]
    e3 = summary.loc[summary["event_id"] == "E3"].iloc[0]

    assert np.isclose(e1_a_k0, 0.01)
    # E1 포함 동은 A(+0.04, +0.04)와 C(-0.02, -0.02)이다.
    # 괄호 안은 각각 post_change_4q, pre_change_4q의 동별 값이다.
    assert np.isclose(e1["pre_change_4q"], 0.01)
    assert np.isclose(e1["post_change_4q"], 0.01)
    assert np.isclose(e1["share_same_direction"], 0.5)
    assert np.isclose(e1["share_up"], 0.5)
    assert e1["n_dongs"] == 2
    assert "11110_B동" not in set(e1_paths["dong"])
    assert "11110_C동" in set(e1_paths["dong"])
    assert "11110_D동" not in set(e1_paths["dong"])
    assert bool(e2["post_observable"]) is False
    for column in [
        "post_change_4q", "post_median", "post_p10", "post_p90", "share_same_direction", "share_up",
    ]:
        assert np.isnan(e2[column])
    assert e1["overlapping_events"] == "E2"
    assert e2["overlapping_events"] == "E1"
    assert e3["n_dongs"] == 0
    assert np.isnan(e3["post_change_4q"])
    assert "지수 범위 밖" in e3["note"]

    index_with_nan_post = make_index()
    index_with_nan_post.loc[
        (index_with_nan_post["dong"] == "11110_C동")
        & (index_with_nan_post["quarter"] == "2002Q3"),
        "log_index",
    ] = np.nan
    _, nan_summary = event_study.calculate_event_study(index_with_nan_post, make_events())
    nan_e1 = nan_summary.loc[nan_summary["event_id"] == "E1"].iloc[0]
    # C의 post 값은 결측이므로 A(+0.04)만 두 비율의 분자와 분모에 남는다.
    assert np.isclose(nan_e1["share_same_direction"], 1.0)
    assert np.isclose(nan_e1["share_up"], 1.0)
    assert nan_e1["n_dongs_post"] == 1
    print("모든 점검 통과")


if __name__ == "__main__":
    main()
