# ============================================================================
# 60.check_data_end.py
# ============================================================================
# Author:      yjkim
# Purpose:     파일럿 P0(데이터 끝 월·최근 월 완성도·holdout 확정)과 P1(신고 지연 근사)
# Description: 가격 열은 읽지 않고 거래 건수만 센다. 그래서 2025-05 이후 달도 셀 수 있다.
#              - 수집 시점: output/raw/sale 캐시 파일 수정 시각 (캐시당 스냅샷은 1개뿐)
#              - 수집 회차 비교: 11.run.log, 11.run2.log는 같은 캐시를 다시 합친 기록이라
#                최근 월 건수의 증가를 비교할 수 없다(다른 점은 201102 한 조합의 재시도뿐)
#              - 신고 지연 근사: 2026-08 계약일별 건수를 완결된 2026-07과 비교한다.
#                수집일 − 계약일(경과일)이 짧을수록 아직 신고되지 않은 거래가 많다
# ============================================================================

import datetime as dt

import pandas as pd

from _short_index import OUTPUT_DIR

HOLDOUT_FIRST, HOLDOUT_LAST = "2025-05", "2026-04"

# ============================================================================
# 1. 건수 적재 (가격 열 없음)
# ============================================================================

trades = pd.read_csv(OUTPUT_DIR / "11.1.trades_sale.txt", sep="\t", dtype=str,
                     usecols=["deal_ym", "dealDay", "is_cancelled", "sggCd", "umdNm"])
assert "deal_amount_manwon" not in trades.columns
trades = trades[trades["deal_ym"].str.fullmatch(r"\d{6}", na=False)]
trades["cancelled"] = trades["is_cancelled"].eq("True")

# ============================================================================
# 2. P0: 데이터 끝 월과 수집 시점
# ============================================================================

cache_times = {}
for path in (OUTPUT_DIR / "raw" / "sale").glob("*.json"):
    ym = path.stem.split("_")[1]
    cache_times.setdefault(ym, []).append(path.stat().st_mtime)
last_ym = max(cache_times)
collected = dt.datetime.fromtimestamp(min(cache_times[last_ym]))
snapshot_dates = sorted({dt.datetime.fromtimestamp(t).date() for times in cache_times.values() for t in times})

monthly = (trades.groupby("deal_ym")
           .agg(n_all=("cancelled", "size"), n_cancelled=("cancelled", "sum"))
           .reset_index())
monthly["n_valid"] = monthly["n_all"] - monthly["n_cancelled"]
monthly["cancel_share"] = monthly["n_cancelled"] / monthly["n_all"]
# 직전 12개월 중앙값 대비 비율: 끝 달이 덜 들어왔는지 거칠게 본다
monthly["ratio_to_prev12_median"] = monthly["n_valid"] / monthly["n_valid"].shift(1).rolling(12).median()
recent = monthly[monthly["deal_ym"] >= "202401"].copy()
recent["collected_at"] = recent["deal_ym"].map(
    lambda ym: dt.datetime.fromtimestamp(min(cache_times[ym])).strftime("%Y-%m-%d %H:%M"))

# 30일 신고 기한: 수집일 기준 계약일이 30일보다 앞선 달까지 완결로 본다
complete_cutoff = collected.date() - dt.timedelta(days=30)
last_complete = pd.Period(complete_cutoff + dt.timedelta(days=1), freq="M") - 1   # 말일이 cutoff 이하인 마지막 달
last_target_origin = last_complete - 3
holdout_first = last_target_origin - 11
assert str(holdout_first) == HOLDOUT_FIRST and str(last_target_origin) == HOLDOUT_LAST, (holdout_first, last_target_origin)

# ============================================================================
# 3. P1: 신고 지연 근사 (2026-08 계약일별 건수 / 2026-07 같은 날짜 건수)
# ============================================================================

day = pd.to_numeric(trades["dealDay"], errors="coerce")
valid = trades[~trades["cancelled"] & day.notna()].assign(day=day)
jul = valid[valid["deal_ym"] == "202607"].groupby("day").size()
aug = valid[valid["deal_ym"] == "202608"].groupby("day").size()
lag = pd.DataFrame({"day": range(1, 32)})
lag["n_202607"] = lag["day"].map(jul).fillna(0).astype(int)
lag["n_202608"] = lag["day"].map(aug).fillna(0).astype(int)
lag["days_elapsed_at_collection"] = [(collected.date() - dt.date(2026, 8, d)).days for d in lag["day"]]
bins = [0, 14, 19, 24, 29, 45]
labels = ["10-14", "15-19", "20-24", "25-29", "30-40"]
lag["elapsed_bin"] = pd.cut(lag["days_elapsed_at_collection"], bins=bins, labels=labels)
lag_summary = lag.groupby("elapsed_bin", observed=True)[["n_202607", "n_202608"]].sum().reset_index()
lag_summary["ratio_aug_to_jul"] = lag_summary["n_202608"] / lag_summary["n_202607"]
# 30일이 지난 날(계약 8/1~8/11)은 신고가 끝났다고 보고 그 비율로 시장 수준 차이를 나눈다
level = lag_summary.loc[lag_summary["elapsed_bin"] == "30-40", "ratio_aug_to_jul"].iloc[0]
lag_summary["availability_vs_complete"] = lag_summary["ratio_aug_to_jul"] / level

summary = pd.DataFrame([
    ("data_last_month", last_ym),
    ("last_month_collected_at", collected.strftime("%Y-%m-%d %H:%M")),
    ("cache_snapshot_dates", ",".join(map(str, snapshot_dates))),
    ("snapshots_per_month_cache", "1 (월×구 캐시마다 파일 1개, 재수집 이력 없음)"),
    ("run_log_comparison", "11.run.log vs 11.run2.log: 같은 캐시 재집계, 차이는 201102 관악구 재시도 1건 → 회차 간 증가 측정 불가"),
    ("last_complete_month_30d_rule", str(last_complete)),
    ("last_origin_with_complete_target", str(last_target_origin)),
    ("holdout_origins", f"{holdout_first}~{last_target_origin}"),
    ("pilot_last_origin", str(holdout_first - 4)),
    ("pilot_price_last_month", str(holdout_first - 1)),
    ("n_202608_vs_prev12_median", f"{monthly.iloc[-1]['ratio_to_prev12_median']:.3f}"),
    ("n_202607_vs_prev12_median", f"{monthly.iloc[-2]['ratio_to_prev12_median']:.3f}"),
], columns=["item", "value"])

# ============================================================================
# 4. 저장
# ============================================================================

paths = {
    "summary": OUTPUT_DIR / "60.1.data_end_summary.txt",
    "recent": OUTPUT_DIR / "60.2.recent_month_counts.txt",
    "lag": OUTPUT_DIR / "60.3.report_lag_proxy.txt",
}
summary.to_csv(paths["summary"], sep="\t", index=False, lineterminator="\n")
recent.to_csv(paths["recent"], sep="\t", index=False, lineterminator="\n", float_format="%.4f")
lag_summary.to_csv(paths["lag"], sep="\t", index=False, lineterminator="\n", float_format="%.4f")

print(summary.to_string(index=False))
print(lag_summary.to_string(index=False, float_format="%.3f"))
print("===== 60 완료 =====")
for path in paths.values():
    print(path)
