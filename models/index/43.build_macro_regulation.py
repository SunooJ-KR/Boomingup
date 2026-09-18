# ============================================================================
# 43.build_macro_regulation.py
# ============================================================================
# Author:      yjkim
# Purpose:     기준금리와 투기과열지구 지정 여부를 자치구×기점(as_of_quarter) feature로 만든다
# Description: 사전 등록 결정 13. 값은 분기 말 시점 상태다. 출처와 확인 방법은 docs/data-sources.md.
#              - 기준금리: 한국은행 기준금리 추이 목록 HTML을 raw/macro에 캐시하고 표를 직접 파싱한다
#                (캐시를 지우면 다시 받는다. lxml 없이 정규식으로 읽는다)
#              - 투기과열지구: 원문으로 확인한 서울 전환점만 상수로 둔다
#              - 조정대상지역은 서울에서 확인된 전환점이 투기과열지구와 같아 따로 두지 않는다
#              - 서울 전역에 같은 값인 기간이 길어 동끼리 구분하는 힘은 약하다 (handoff §6.3)
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import html
import re
from pathlib import Path

import pandas as pd
import requests

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"
BASE_RATE_URL = "https://www.bok.or.kr/portal/singl/baseRate/list.do?dataSeCd=01&menuNo=200643"
BASE_RATE_HTML = output_dir / "raw" / "macro" / "bok_base_rate.html"

SEOUL_GU_CODES = [
    "11110", "11140", "11170", "11200", "11215", "11230", "11260", "11290", "11305", "11320",
    "11350", "11380", "11410", "11440", "11470", "11500", "11530", "11545", "11560", "11590",
    "11620", "11650", "11680", "11710", "11740",
]
GANGNAM3 = ["11650", "11680", "11710"]                    # 서초·강남·송파
GANGNAM3_YONGSAN = GANGNAM3 + ["11170"]                    # + 용산

# (효력 발생일, 지정 자치구) — 서울 전환점만. 이 날부터 다음 전환점 전날까지 유지된다.
# 지수 시작(2006Q1) 전부터 서울 전역이 지정 상태였다. 2008-11-07 해제가 22개 구를 풀고 강남3구만
# 남겼기 때문이다(해제 22 + 유지 3 = 25). 최초 지정일은 지수 범위 밖이라 확인하지 않았다.
OVERHEATED_CHANGES = [
    ("2006-01-01", SEOUL_GU_CODES),      # 지수 시작 시점 상태 (위 설명)
    ("2008-11-07", GANGNAM3),            # 국토부 정책Q&A: "강남 3구를 제외한 수도권 투기과열지구 전역을 모두 해제 … 11월 7일부터"
    ("2011-12-22", []),                  # 국토해양부고시 제2011-795호: 해제지역 강남구·서초구·송파구, 해제일 2011-12-22
    ("2017-08-03", SEOUL_GU_CODES),      # 정부 공감 2017-08-07: "서울 25개 구 전 지역", "8월 3일부터 즉시"
    ("2023-01-05", GANGNAM3_YONGSAN),    # 국토교통부공고 2023-1호: 전역 → 서초·강남·송파·용산, 공고일 효력
    ("2025-10-16", SEOUL_GU_CODES),      # 국토부 2025-10-15 대책 원문: 4개구 유지 + 21개구 신규, 10.16 효력
]
FIRST_QUARTER = pd.Period("2006Q1", freq="Q")
LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")


def parse_base_rate_table(page):
    """표에서 (연도, 'MM월 DD일', 금리) 3칸짜리 행만 꺼낸다."""
    rows = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, flags=re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cell))).strip()
                 for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S)]
        if len(cells) == 3 and re.fullmatch(r"\d{4}", cells[0]):
            rows.append(cells)
    return rows


# ============================================================================
# 1. 기준금리 (분기 말 값)
# ============================================================================

if not BASE_RATE_HTML.exists():
    BASE_RATE_HTML.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(BASE_RATE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    BASE_RATE_HTML.write_text(response.text, encoding="utf-8")

rate = pd.DataFrame(parse_base_rate_table(BASE_RATE_HTML.read_text(encoding="utf-8", errors="replace")),
                    columns=["year", "month_day", "rate_pct"])
if rate.empty:
    raise SystemExit(f"기준금리 표를 찾지 못함: {BASE_RATE_HTML} (페이지 구조가 바뀌었는지 확인)")
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
for label in ["2006Q1", "2008Q3", "2008Q4", "2011Q3", "2011Q4", "2017Q2", "2017Q3", "2022Q4", "2023Q1", "2025Q3", "2025Q4", "2026Q2"]:
    print(f"  {label}: 투기과열지구 자치구 {check[pd.Period(label, freq='Q')]}개, "
          f"기준금리 {macro.set_index('as_of_quarter').loc[pd.Period(label, freq='Q'), 'base_rate_pct']}%")
print(f"\n금리·규제: {features_path} ({len(features):,}행)")
