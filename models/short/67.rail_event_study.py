# ============================================================================
# 67.rail_event_study.py
# ============================================================================
# Author:      yjkim
# Purpose:     역 사건 공개 전후의 forecastable 동 상대 3개월 변화율을 기술한다
# Description: 같은 구·같은 origin의 비노출 동 평균을 빼고 사건 단위 bootstrap을 한다.
# ============================================================================
import argparse
import time

import numpy as np
import pandas as pd

from _short_eval import load_panel, read_structure
from _short_events import RAIL_LINE_PATH, load_rail, rail_exposure
from _short_index import OUTPUT_DIR, ym_to_mi


def clustered_ci(frame, reps=2000, seed=42):
    """project milestone을 복원추출하고 exposure 가중 평균의 percentile CI를 계산한다."""
    rng = np.random.default_rng(seed)
    frame = frame.assign(weighted=frame.difference * frame.exposure_1000)
    cluster = frame.groupby("milestone_id").agg(num=("weighted", "sum"), den=("exposure_1000", "sum"))
    estimate = cluster.num.sum() / cluster.den.sum()
    if len(cluster) < 2:
        return estimate, np.nan, np.nan
    index = rng.integers(0, len(cluster), size=(reps, len(cluster)))
    num = cluster.num.to_numpy()[index].sum(axis=1)
    den = cluster.den.to_numpy()[index].sum(axis=1)
    draws = num / den
    return estimate, *np.quantile(draws, [.025, .975])


def summarize(frame, group_cols):
    rows = []
    for key, part in frame.groupby(group_cols):
        key = (key,) if not isinstance(key, tuple) else key
        mean, lo, hi = clustered_ci(part)
        rows.append(dict(zip(group_cols, key), mean_difference=mean, ci_lo=lo, ci_hi=hi,
                         ci_note="NA (사건 1건)" if part.milestone_id.nunique() < 2 else "",
                         n_events=part.milestone_id.nunique(), n_station_rows=part.event_id.nunique(),
                         n_dongs=part.dong.nunique(), n_rows=len(part)))
    return pd.DataFrame(rows)


parser = argparse.ArgumentParser()
parser.add_argument("--smoke", action="store_true")
args = parser.parse_args(); started = time.time()
panel = load_panel(read_structure())
panel = panel[(panel.origin >= 201201) & panel.y.notna() & (panel.n_3m >= 10)].copy()
panel["r"] = panel.y - panel.groupby("origin").y.transform("mean")
events = load_rail()
if args.smoke:
    events = events[events.public_month >= pd.Period("2011-01", freq="M")].head(8).reset_index(drop=True)
exposure = rail_exposure(events)
event_meta = events[["event_id", "milestone_id", "kind", "public_month"]].copy()
event_meta["event_mi"] = event_meta.public_month.map(lambda x: x.year * 12 + x.month - 1)
exposure_meta = exposure.merge(event_meta, on="event_id")
rows = []
for sensitivity in (False, True):
  analysis = "other_event_controls_dropped" if sensitivity else "main"
  for event in events.itertuples():
    event_mi = event.public_month.year * 12 + event.public_month.month - 1
    exposed = exposure[exposure.event_id == event.event_id]
    if exposed.empty:
        continue
    for origin, current in panel.groupby("origin"):
        origin_mi = int(ym_to_mi(origin)); k = origin_mi - event_mi
        if not -12 <= k <= 12:
            continue
        treatment = current.merge(exposed, on="dong")
        if treatment.empty:
            continue
        exposed_dongs = set(exposed.dong)
        control_excluded = exposed_dongs
        if sensitivity:
            other = exposure_meta[(exposure_meta.event_id != event.event_id)
                                  & ((origin_mi - exposure_meta.event_mi).abs() <= 12)]
            control_excluded = control_excluded | set(other.dong)
        # 역의 좌표 구가 아니라 각 처리 동의 구별 control을 사용한다.
        control_mean = current[~current.dong.isin(control_excluded)].groupby("sggCd").r.mean()
        treatment["difference"] = treatment.r - treatment.sggCd.map(control_mean)
        treatment = treatment.dropna(subset=["difference"])
        treatment["event_id"] = event.event_id; treatment["milestone_id"] = event.milestone_id
        treatment["kind"] = event.kind; treatment["k"] = k; treatment["analysis"] = analysis
        rows.append(treatment[["analysis", "event_id", "milestone_id", "kind", "k", "origin", "dong",
                               "exposure_1000", "difference"]])
detail = pd.concat(rows, ignore_index=True)
by_k = summarize(detail, ["analysis", "kind", "k"])
detail["window"] = pd.cut(detail.k, [-13, -1, 5, 12], labels=["-12~-1", "0~+5", "+6~+12"])
pooled = summarize(detail, ["analysis", "kind", "window"])
line_excluded = sum(1 for _ in open(RAIL_LINE_PATH, encoding="utf-8")) - 1
contributed = detail.groupby(["analysis", "kind"]).agg(
    contributing_milestones=("milestone_id", "nunique"), contributing_station_rows=("event_id", "nunique")).reset_index()
candidate_counts = events.groupby("kind").milestone_id.nunique().to_dict()
qc = pd.DataFrame([{"candidate_station_rows": events.event_id.nunique(),
                    "candidate_plan_milestones": candidate_counts.get("plan", 0),
                    "candidate_construction_milestones": candidate_counts.get("construction", 0),
                    "candidate_open_milestones": candidate_counts.get("open", 0),
                    **{f"{r.analysis}_{r.kind}_contributing_milestones": r.contributing_milestones
                       for r in contributed.itertuples()},
                    "line_events_excluded": line_excluded,
                    "scheduled_open_rows_excluded": 34, "runtime_seconds": time.time() - started}])
suffix = ".smoke" if args.smoke else ""
paths = [OUTPUT_DIR / f"67.1{suffix}.event_time.txt", OUTPUT_DIR / f"67.2{suffix}.pooled.txt",
         OUTPUT_DIR / f"67.3{suffix}.qc.txt"]
by_k.to_csv(paths[0], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
pooled.to_csv(paths[1], sep="\t", index=False, lineterminator="\n", float_format="%.6f")
qc.to_csv(paths[2], sep="\t", index=False, lineterminator="\n", float_format="%.3f")
print(pooled.to_string(index=False)); print(f"===== 67 완료 ({time.time() - started:.1f}초) =====")
for path in paths: print(path)
