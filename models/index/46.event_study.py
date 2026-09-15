# ============================================================================
# 46.event_study.py
# ============================================================================
# Author:      yjkim
# Purpose:     검증된 이벤트별 서울 법정동 가격 지수 변화 경로와 요약 지표를 계산한다
# Description: 기준 분기는 이벤트 분기의 직전 분기이며, eligible 동을 같은 가중치로 요약한다.
#              log_index는 같은 동 안의 시점 간 변화량으로만 사용한다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"

RELATIVE_QUARTERS = range(-4, 5)


# ============================================================================
# 1. 계산 함수
# ============================================================================

def as_quarter(value):
    """YYYYQn 형식 또는 날짜를 분기 Period로 변환한다."""
    if isinstance(value, pd.Period):
        return value.asfreq("Q")
    return pd.Period(value, freq="Q")


def empty_summary_row(event, event_quarter, base_quarter, pre_observable, post_observable, note):
    """지수 범위 밖 이벤트의 요약 행을 만든다."""
    return {
        "event_id": event["event_id"],
        "effective_date": event["effective_date"],
        "category": event["category"],
        "label": event["label"],
        "event_quarter": event_quarter,
        "base_quarter": base_quarter,
        "n_dongs": 0,
        "n_dongs_post": 0,
        "pre_change_4q": np.nan,
        "post_change_4q": np.nan,
        "post_median": np.nan,
        "post_p10": np.nan,
        "post_p90": np.nan,
        "share_same_direction": np.nan,
        "share_up": np.nan,
        "pre_observable": pre_observable,
        "post_observable": post_observable,
        "overlapping_events": event["overlapping_events"],
        "note": note,
    }


def calculate_event_study(index, events):
    """동×분기 지수와 이벤트 표에서 경로 및 이벤트 요약을 계산한다."""
    required_index = {"dong", "sggCd", "umdNm", "quarter", "log_index", "eligible"}
    required_events = {"event_id", "effective_date", "category", "label", "verified", "source"}
    missing_index = required_index - set(index.columns)
    missing_events = required_events - set(events.columns)
    if missing_index:
        raise ValueError(f"지수 입력 필수 컬럼 없음: {sorted(missing_index)}")
    if missing_events:
        raise ValueError(f"이벤트 입력 필수 컬럼 없음: {sorted(missing_events)}")

    panel = index.copy()
    panel["quarter"] = pd.PeriodIndex(panel["quarter"].astype(str), freq="Q")
    panel["eligible"] = panel["eligible"].astype(str).eq("True")
    panel = panel.sort_values(["dong", "quarter"]).reset_index(drop=True)

    verified = events.loc[events["verified"].astype(str).eq("True")].copy().reset_index(drop=True)
    verified["effective_date"] = pd.to_datetime(verified["effective_date"]).dt.strftime("%Y-%m-%d")
    verified["event_quarter"] = pd.PeriodIndex(pd.to_datetime(verified["effective_date"]), freq="Q")
    verified["event_quarter_ordinal"] = verified["event_quarter"].astype("int64")
    verified["overlapping_events"] = ""
    for position, event in verified.iterrows():
        nearby = verified.loc[
            (verified["event_id"] != event["event_id"])
            & ((verified["event_quarter_ordinal"] - event["event_quarter_ordinal"]).abs() <= 4),
            "event_id",
        ]
        verified.loc[position, "overlapping_events"] = ",".join(nearby)

    first_quarter = panel["quarter"].min()
    last_quarter = panel["quarter"].max()
    lookup = panel.set_index(["dong", "quarter"])
    path_rows = []
    summary_rows = []

    for _, event in verified.iterrows():
        event_quarter = event["event_quarter"]
        base_quarter = event_quarter - 1
        pre_observable = base_quarter - 4 >= first_quarter
        post_observable = event_quarter + 3 <= last_quarter
        outside_event = not first_quarter <= event_quarter <= last_quarter
        outside_base = not first_quarter <= base_quarter <= last_quarter

        if outside_event or outside_base:
            reasons = []
            if outside_event:
                reasons.append("이벤트 분기가 지수 범위 밖")
            if outside_base:
                reasons.append("기준 분기가 지수 범위 밖")
            summary_rows.append(empty_summary_row(
                event, event_quarter, base_quarter, pre_observable, post_observable, "; ".join(reasons)
            ))
            continue

        base = panel.loc[(panel["quarter"] == base_quarter) & panel["eligible"]].copy()
        included = base[["dong", "sggCd", "umdNm", "log_index"]].rename(columns={"log_index": "base_log_index"})

        for k in RELATIVE_QUARTERS:
            quarter = event_quarter + k
            if not first_quarter <= quarter <= last_quarter:
                continue
            at_quarter = panel.loc[panel["quarter"] == quarter, ["dong", "log_index"]]
            paths = included.merge(at_quarter, on="dong", how="left")
            for row in paths.itertuples(index=False):
                path_rows.append({
                    "event_id": event["event_id"],
                    "dong": row.dong,
                    "sggCd": row.sggCd,
                    "umdNm": row.umdNm,
                    "k": k,
                    "quarter": quarter,
                    "rel_log_change": row.log_index - row.base_log_index,
                })

        pre_change = np.nan
        if pre_observable:
            before = panel.loc[panel["quarter"] == base_quarter - 4, ["dong", "log_index"]]
            pre_values = included.merge(before, on="dong", how="left")
            pre_change = (pre_values["base_log_index"] - pre_values["log_index"]).mean()

        post_values = pd.Series(dtype=float)
        if post_observable:
            post = panel.loc[panel["quarter"] == event_quarter + 3, ["dong", "log_index"]]
            post_values = included.merge(post, on="dong", how="left")
            post_values = post_values["log_index"] - post_values["base_log_index"]
            valid_post = post_values.dropna()
            post_change = valid_post.mean()
            post_median = valid_post.median()
            post_p10, post_p90 = np.percentile(valid_post, [10, 90]) if not valid_post.empty else (np.nan, np.nan)
            share_same_direction = np.nan if post_change == 0 or pd.isna(post_change) else (
                np.sign(valid_post) == np.sign(post_change)
            ).mean()
            share_up = (valid_post > 0).mean() if not valid_post.empty else np.nan
        else:
            post_change = np.nan
            post_median = np.nan
            post_p10 = np.nan
            post_p90 = np.nan
            share_same_direction = np.nan
            share_up = np.nan

        summary_rows.append({
            "event_id": event["event_id"],
            "effective_date": event["effective_date"],
            "category": event["category"],
            "label": event["label"],
            "event_quarter": event_quarter,
            "base_quarter": base_quarter,
            "n_dongs": len(included),
            "n_dongs_post": len(valid_post) if post_observable else 0,
            "pre_change_4q": pre_change,
            "post_change_4q": post_change,
            "post_median": post_median,
            "post_p10": post_p10,
            "post_p90": post_p90,
            "share_same_direction": share_same_direction,
            "share_up": share_up,
            "pre_observable": pre_observable,
            "post_observable": post_observable,
            "overlapping_events": event["overlapping_events"],
            "note": "",
        })

    path_columns = ["event_id", "dong", "sggCd", "umdNm", "k", "quarter", "rel_log_change"]
    summary_columns = [
        "event_id", "effective_date", "category", "label", "event_quarter", "base_quarter", "n_dongs",
        "n_dongs_post", "pre_change_4q", "post_change_4q", "post_median", "post_p10", "post_p90", "share_same_direction",
        "share_up", "pre_observable", "post_observable", "overlapping_events", "note",
    ]
    return pd.DataFrame(path_rows, columns=path_columns), pd.DataFrame(summary_rows, columns=summary_columns)


# ============================================================================
# 2. 파일 실행
# ============================================================================

def main():
    index_path = output_dir / "40.1.dong_index.txt"
    events_path = work_dir / "models" / "index" / "event_dates.tsv"
    paths_path = output_dir / "46.1.event_dong_paths.txt"
    summary_path = output_dir / "46.2.event_summary.txt"

    index = pd.read_csv(index_path, sep="\t", dtype={"dong": str, "sggCd": str, "umdNm": str})
    events = pd.read_csv(events_path, sep="\t", dtype=str)
    paths, summary = calculate_event_study(index, events)
    paths.to_csv(paths_path, sep="\t", index=False, lineterminator="\n")
    summary.to_csv(summary_path, sep="\t", index=False, lineterminator="\n")

    print("===== 이벤트별 요약 =====")
    for row in summary.itertuples(index=False):
        post_percent = np.nan if pd.isna(row.post_change_4q) else (np.exp(row.post_change_4q) - 1) * 100
        print(f"  {row.event_id} / {row.event_quarter} / 포함 동 {row.n_dongs:,} / "
              f"post_change_4q {post_percent:.2f}% / share_same_direction {row.share_same_direction:.3f}")
    print(f"\n경로: {paths_path}")
    print(f"요약: {summary_path}")


if __name__ == "__main__":
    main()
