# ============================================================================
# 63.evaluate_baselines.py
# ============================================================================
# Author:      yjkim
# Purpose:     파일럿 P3: baseline 4종의 3개월 예측 성능을 기점별로 잰다
# Description: B0 0, B1 동 모멘텀(최근 3개월 변화), B2 구 모멘텀, B3 서울 모멘텀(거래량 가중).
#              평가 대상: 기점에서 최근 3개월 거래 N건 이상인 동 (N=10 주 결과, 20·30 보조).
#              기점 2012-01~2025-01, 2012~2019와 2020~2025-01을 따로도 본다.
#              지표: MAE, 상대 MAE, Spearman, 방향 정확도(부호·±0.5% 보합), 80% 구간 coverage.
#              B3와의 차이는 기점 block bootstrap(6개월, 2000회, seed 42)으로 구간을 낸다.
#              구조(A/B)는 62.1의 권고를 읽는다.
# ============================================================================

import time

import numpy as np
import pandas as pd

from _short_eval import (EVAL_FIRST, EVAL_LAST, PERIODS, add_features, block_bootstrap, in_period,
                         interval_coverage, load_panel, origin_metrics, read_structure)
from _short_index import OUTPUT_DIR

BASELINES = {"B0_zero": None, "B1_dong": "mom_0_3", "B2_gu": "gu_mom_0_3",
             "B3_seoul": "seoul_mom_0_3", "B1_prime_dong_t3": "main_mom_0_3",
             "B2_prime_gu_t3": "main_gu_mom_0_3"}
THRESHOLDS = [10, 20, 30]
METRICS = ["n_dongs", "mae", "rel_mae", "spearman", "dir_acc", "dir_acc_band", "coverage", "width"]

# ============================================================================
# 1. 입력
# ============================================================================

started = time.time()
structure = read_structure()
target = load_panel(structure).dropna(subset=["y"])
panel = add_features(target, "SENS_LAG")
main = add_features(target, "MAIN")
panel["main_mom_0_3"] = main["mom_0_3"]
panel["main_gu_mom_0_3"] = main["gu_mom_0_3"]
panel["B0_zero"] = 0.0
for name, col in BASELINES.items():
    if col:
        # 동 모멘텀이 없으면(창 앞부분 거래 공백) 같은 시점의 구·서울 값으로 채운다
        if name == "B1_prime_dong_t3":
            panel[name] = panel[col].fillna(panel["main_gu_mom_0_3"]).fillna(main["local_seoul_mom_0_3"])
        elif name == "B2_prime_gu_t3":
            panel[name] = panel[col].fillna(main["local_seoul_mom_0_3"])
        else:
            panel[name] = panel[col].fillna(panel["gu_mom_0_3"]).fillna(panel["seoul_mom_0_3"])
print(f"구조 {structure}, panel {len(panel):,}행")

# ============================================================================
# 2. 기점별 지표
# ============================================================================

summary_rows, boot_rows, per_origin_all = [], [], []
for n_min in THRESHOLDS:
    rows = panel[panel["n_3m"] >= n_min]
    per_method = {}
    for name in BASELINES:
        metrics = origin_metrics(rows, name).join(interval_coverage(rows, name))
        per_method[name] = metrics[(metrics.index >= EVAL_FIRST) & (metrics.index <= EVAL_LAST)]
        per_origin_all.append(per_method[name].assign(method=name, n_min=n_min).reset_index())
    for period in PERIODS:
        for name, metrics in per_method.items():
            part = metrics[in_period(metrics.index, period)]
            summary_rows.append({"n_min": n_min, "period": period, "method": name, "n_origins": len(part),
                                 **part[METRICS].mean().to_dict()})
            if n_min != 10:
                continue
            ref = per_method["B3_seoul"][in_period(per_method["B3_seoul"].index, period)]
            for metric in ("mae", "rel_mae", "dir_acc_band", "coverage"):
                if name == "B3_seoul":
                    continue
                est, lo, hi = block_bootstrap(part[metric] - ref[metric])
                boot_rows.append({"period": period, "method": name, "metric": f"{metric}_minus_B3",
                                  "estimate": est, "ci_lo": lo, "ci_hi": hi})
            if part["spearman"].notna().all():
                est, lo, hi = block_bootstrap(part["spearman"])
                boot_rows.append({"period": period, "method": name, "metric": "spearman",
                                  "estimate": est, "ci_lo": lo, "ci_hi": hi})

summary = pd.DataFrame(summary_rows)
boot = pd.DataFrame(boot_rows)

# ============================================================================
# 3. 저장
# ============================================================================

paths = {
    "summary": OUTPUT_DIR / "63.1.baseline_summary.txt",
    "boot": OUTPUT_DIR / "63.2.baseline_bootstrap.txt",
    "origin": OUTPUT_DIR / "63.3.baseline_by_origin.txt",
}
summary.to_csv(paths["summary"], sep="\t", index=False, lineterminator="\n", float_format="%.5f")
boot.to_csv(paths["boot"], sep="\t", index=False, lineterminator="\n", float_format="%.5f")
pd.concat(per_origin_all).to_csv(paths["origin"], sep="\t", index=False, lineterminator="\n", float_format="%.5f")

show = summary[(summary["n_min"] == 10) & (summary["period"] == "all")]
print(show.drop(columns=["n_min", "period"]).to_string(index=False, float_format="%.4f"))
print(f"===== 63 완료 ({time.time() - started:.0f}초) =====")
for path in paths.values():
    print(path)
