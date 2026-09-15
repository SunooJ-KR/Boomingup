# ============================================================================
# 43.build_macro_regulation.py
# ============================================================================
# Author:      yjkim
# Purpose:     기준금리와 투기과열지구 지정 여부를 자치구×기점(as_of_quarter) feature로 만든다
# Description: 사전 등록 결정 13. 값은 분기 말 시점 상태다. 출처와 확인 방법은 docs/data-sources.md.
#              - 기준금리: 한국은행 기준금리 추이 목록 HTML을 직접 파싱한 표(raw/macro)
#              - 투기과열지구: 원문으로 확인한 서울 전환점만 상수로 둔다
#              - 조정대상지역은 서울에서 확인된 전환점이 투기과열지구와 같아 따로 두지 않는다
#              - 서울 전역에 같은 값인 기간이 길어 동끼리 구분하는 힘은 약하다 (handoff §6.3)
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from pathlib import Path

import pandas as pd

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"
BASE_RATE_PATH = output_dir / "raw" / "macro" / "bok_base_rate_parsed.txt"

SEOUL_GU_CODES = [
    "11110", "11140", "11170", "11200", "11215", "11230", "11260", "11290", "11305", "11320",
    "11350", "11380", "11410", "11440", "11470", "11500", "11530", "11545", "11560", "11590",
    "11620", "11650", "11680", "11710", "11740",
]
GANGNAM3_YONGSAN = ["11650", "11680", "11710", "11170"]   # 서초·강남·송파·용산

# (효력 발생일, 지정 자치구) — 서울 전환점만. 이 날부터 다음 전환점 전날까지 유지된다
OVERHEATED_CHANGES = [
    ("2017-08-03", SEOUL_GU_CODES),      # 정부 공감 2017-08-07: "서울 25개 구 전 지역", "8월 3일부터 즉시"
    ("2023-01-05", GANGNAM3_YONGSAN),    # 국토교통부공고 2023-1호: 전역 → 서초·강남·송파·용산, 공고일 효력
    ("2025-10-16", SEOUL_GU_CODES),      # 국토부 2025-10-15 대책 원문: 4개구 유지 + 21개구 신규, 10.16 효력
]
FIRST_QUARTER = pd.Period("2006Q1", freq="Q")
LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")


# ============================================================================
# 1. 기준금리 (분기 말 값)
# ============================================================================

rate = pd.read_csv(BASE_RATE_PATH, sep="\t", dtype=str)
rate["date"] = pd.to_datetime(rate["year"] + " " + rate["month_day"], format="%Y %m월 %d일")
rate["rate_pct"] = pd.to_numeric(rate["rate_pct"])
rate = rate.sort_values("date")

quarters = pd.period_range(FIRST_QUARTER, LAST_COMPLETE_QUARTER, freq="Q")
quarter_end = pd.DataFrame({"as_of_quarter": quarters, "date": quarters.end_time.normalize()})
macro = pd.merge_asof(quarter_end, rate[["date", "rate_pct"]], on="date", direction="backward")
macro = macro.rename(columns={"rate_pct": "base_rate_pct"})
macro["base_rate_change_4q"] = macro["base_rate_pct"] - macro["base_rate_pct"].shift(4)
print(f"===== 1. 기준금리 완료: 변경 {len(rate)}건, 결측 분기 {int(macro['base_rate_pct'].isna().sum())}개 =====")


# ============================================================================
# 2. 투기과열지구 (분기 말 상태)
# ============================================================================

rows = []
for quarter, date in zip(macro["as_of_quarter"], macro["date"]):
    designated = set()
    for effective, gu_codes in OVERHEATED_CHANGES:
        if pd.Timestamp(effective) <= date:
            designated = set(gu_codes)
    for gu_code in SEOUL_GU_CODES:
        rows.append({"sggCd": gu_code, "as_of_quarter": quarter, "reg_overheated": int(gu_code in designated)})
regulation = pd.DataFrame(rows)
print("===== 2. 투기과열지구 완료 =====")


# ============================================================================
# 3. 병합 및 저장
# ============================================================================

features = regulation.merge(macro.drop(columns="date"), on="as_of_quarter", how="left")
features_path = output_dir / "43.1.gu_macro_regulation.txt"
features.to_csv(features_path, sep="\t", index=False, lineterminator="\n")

check = features.groupby("as_of_quarter")["reg_overheated"].sum()
for label in ["2017Q2", "2017Q3", "2022Q4", "2023Q1", "2025Q3", "2025Q4", "2026Q2"]:
    print(f"  {label}: 투기과열지구 자치구 {check[pd.Period(label, freq='Q')]}개, "
          f"기준금리 {macro.set_index('as_of_quarter').loc[pd.Period(label, freq='Q'), 'base_rate_pct']}%")
print(f"\n금리·규제: {features_path} ({len(features):,}행)")
