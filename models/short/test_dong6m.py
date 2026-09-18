# ============================================================================
# test_dong6m.py
# ============================================================================
# Author:      yjkim
# Purpose:     6개월 target 기간·purge·bootstrap helper의 합성 검증
# ============================================================================

import numpy as np
import pandas as pd

from _dong6m import HORIZON, block_bootstrap, label_periods_6m, spearman_brown, volume_bin


def test_period_labels():
    origin = 100
    frame = pd.DataFrame({"mi": [98, 100, 101, 103, 104, 106]})
    assert label_periods_6m(frame, origin).tolist() == [0, 0, -1, -1, -2, -2]


def test_purge_and_reliability():
    train_origins = np.arange(80, 101)
    assert np.array_equal(train_origins[train_origins + HORIZON <= 100], np.arange(80, 95))
    assert np.isclose(spearman_brown(.5), 2 / 3)
    assert volume_bin(pd.Series([0, 9, 10, 20, 50])).astype(str).tolist() == ["0-9", "0-9", "10-19", "20-29", "50+"]


def test_bootstrap_is_deterministic():
    values = pd.Series(np.arange(20, dtype=float))
    first = block_bootstrap(values, reps=20)
    second = block_bootstrap(values, reps=20)
    assert first == second


if __name__ == "__main__":
    test_period_labels()
    test_purge_and_reliability()
    test_bootstrap_is_deterministic()
    print("test_dong6m: 통과")
