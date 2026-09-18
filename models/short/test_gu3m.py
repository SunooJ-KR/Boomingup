import unittest
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gu3m import aggregate_gu, center_by_origin, ridge_fit, spearman_brown


class Gu3mTest(unittest.TestCase):
    def test_aggregate_uses_equal_dong_weights_and_drops_small_gu(self):
        frame = pd.DataFrame({"origin": [1] * 5, "sggCd": ["a"] * 3 + ["b"] * 2,
                              "eligible": [True] * 5, "y": [1., 2., 6., 10., 20.]})
        result = aggregate_gu(frame, ["y"])
        self.assertEqual(result["sggCd"].tolist(), ["a"])
        self.assertAlmostEqual(result.loc[0, "y"], 3.)
        self.assertEqual(result.loc[0, "n_dongs"], 3)

    def test_center_and_ridge(self):
        frame = pd.DataFrame({"origin": [1, 1, 2, 2], "x": [1., 3., 2., 6.]})
        self.assertTrue(np.allclose(center_by_origin(frame, ["x"])["x"], [-1, 1, -2, 2]))
        beta = ridge_fit(np.array([[1.], [2.]]), np.array([2., 4.]), 0.)
        self.assertAlmostEqual(beta[0], 2.)

    def test_spearman_brown(self):
        self.assertAlmostEqual(spearman_brown(.5), 2 / 3)


if __name__ == "__main__":
    unittest.main()
