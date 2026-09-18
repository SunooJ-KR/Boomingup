# ============================================================================
# 71.collect_land_permit_zone.py
# ============================================================================
# Author:      yjkim
# Purpose:     서울 토지거래허가구역의 시점별 지정·해제 이력을 보존한다
# Description: 공식 원문을 우선 cache하고, 원문에서 확인한 사건만 TSV로 만든다.
#              법정동 전체가 아닌 단지·정비구역은 subarea로 남겨 과대 매핑을 막는다.
# ============================================================================

import csv
import hashlib
import http.cookiejar
import json
import shutil
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path


work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"
result_dir = output_dir / "raw" / "ldpz"
source_dir = result_dir / "src"
boundary_path = output_dir / "52.1.seoul_bjd_boundary.geojson"
history_path = result_dir / "71.1.land_permit_zone_history.tsv"
readme_path = result_dir / "71_README.md"

FIELDS = [
    "event_type", "effective_start_date", "effective_end_date", "announcing_body",
    "gu", "area_name", "area_level", "dong_key", "area_description",
    "target_use_types", "announcement_date", "source_url", "verbatim_quote",
    "confidence", "source_cache",
]

SOURCES = {
    "seoul_2013_release": "https://news.seoul.go.kr/citybuild/archives/23251",
    "seoul_2021_designation": "https://news.seoul.go.kr/citybuild/archives/512421",
    "seoul_2025_release": "https://mediahub.seoul.go.kr/news/article/newsArticlePrintPopup.do?articleNo=2013415",
    "molit_2025_guidance": "https://files-scs.pstatic.net/2025/10/17/UbF51gv8sV/250421%28%EC%B0%B8%EA%B3%A0%29%20%EA%B0%95%EB%82%A8%C2%B7%EC%84%9C%EC%B4%88%C2%B7%EC%86%A1%ED%8C%8C%C2%B7%EC%9A%A9%EC%82%B0%EA%B5%AC%20%EC%9D%BC%EC%9B%90%ED%86%A0%EC%A7%80%EA%B1%B0%EB%9E%98%ED%97%88%EA%B0%80%EA%B5%AC%EC%97%AD%20%EC%A7%80%EC%A0%95%20%EA%B4%80%EB%A0%A8%20%EC%97%85%EB%AC%B4%EC%B2%98%EB%A6%AC%EA%B8%B0%EC%A4%80%28%ED%86%A0%EC%A7%80%EC%A0%95%EC%B1%85%EA%B3%BC%29.pdf",
    "seoul_2026_extension": "https://www.seoul.go.kr/news/news_report.do?nttNo=457529&srchCtgry=465",
    "yna_2020_designation": "https://www.yna.co.kr/view/AKR20200623085500003",
}


def download(url, destination):
    """원문을 cache하며, 기존 cache가 있으면 network 없이 재사용한다."""
    if destination.exists() and destination.stat().st_size:
        return "cache"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"},
    )
    try:
        if "molit.go.kr" in url:
            cookies = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
            opener.open("https://www.molit.go.kr/", timeout=45).read(1)
        else:
            opener = urllib.request.build_opener()
        with opener.open(request, timeout=45) as response:
            content = response.read()
        if not content:
            raise ValueError("빈 응답")
        destination.write_bytes(content)
        return "download"
    except (OSError, ValueError, urllib.error.URLError) as error:
        return f"실패: {type(error).__name__}: {error}"


def load_dong_keys():
    """법정동 boundary의 sgg_cd와 umd_nm으로 요청된 dong_key를 만든다."""
    payload = json.loads(boundary_path.read_text(encoding="utf-8"))
    keys = {}
    for feature in payload["features"]:
        properties = feature["properties"]
        key = f"{properties['sgg_cd']}_{properties['umd_nm']}"
        keys[(properties["sgg_cd"], properties["umd_nm"])] = key
    return keys


def record(event_type, start, end, body, gu, area, level, description, uses,
           public_date, source_key, quote, confidence, sgg_cd=""):
    dong_key = ""
    if level == "dong":
        dong_key = DONG_KEYS.get((sgg_cd, area), "")
        if not dong_key:
            raise ValueError(f"boundary에서 법정동을 찾지 못함: {sgg_cd}_{area}")
    return {
        "event_type": event_type,
        "effective_start_date": start,
        "effective_end_date": end,
        "announcing_body": body,
        "gu": gu,
        "area_name": area,
        "area_level": level,
        "dong_key": dong_key,
        "area_description": description,
        "target_use_types": uses,
        "announcement_date": public_date,
        "source_url": SOURCES[source_key],
        "verbatim_quote": quote,
        "confidence": confidence,
        "source_cache": f"src/{source_key}{'.pdf' if SOURCES[source_key].lower().endswith('.pdf') else '.html'}",
    }


result_dir.mkdir(parents=True, exist_ok=True)
source_dir.mkdir(parents=True, exist_ok=True)

# 기존 수집기의 현재 현황도 provenance와 교차검증을 위해 복사한다.
current_cache = output_dir / "raw" / "regulation" / "land_permit_zones.json"
if current_cache.exists():
    shutil.copy2(current_cache, source_dir / "seoul_current_status.json")

failures = []
for source_key, source_url in SOURCES.items():
    suffix = ".pdf" if source_url.lower().endswith(".pdf") else ".html"
    status = download(source_url, source_dir / f"{source_key}{suffix}")
    if status.startswith("실패:"):
        failures.append(f"{source_key}: {status}")

DONG_KEYS = load_dong_keys()
rows = []

# 2008 지정은 2013년 서울시 공식 해제자료가 소급 확인하는 범위까지만 싣는다.
industrial_quote = (
    "이번에 해제되는 지역은 2008년 7월 9일 준공업지역에도 공동주택 건립을 완화하는 방향으로 "
    "도시계획조례가 개정되면서 준공업지역 내 토지의 투기적인 거래와 지가가 급격히 상승할 우려가 "
    "있어 2008.07.29 자로 5년간 토지거래허가구역으로 지정된 곳이다."
)
for gu in ["강서구", "금천구", "도봉구", "구로구", "성동구", "영등포구"]:
    rows.append(record("designation", "2008-07-29", "2013-07-28", "서울특별시", gu,
                       f"{gu} 준공업지역", "subarea", "해당 자치구 안의 준공업지역; 필지 목록 미확보",
                       "준공업지역 내 토지", "", "seoul_2013_release",
                       industrial_quote, "primary"))
    rows.append(record("expiration", "2013-07-29", "", "서울특별시", gu,
                       f"{gu} 준공업지역", "subarea", "5년 지정기간 만료로 재지정하지 않음",
                       "준공업지역 내 토지", "2013-07-26", "seoul_2013_release",
                       "7월 28일(일)로 토지거래허가구역 지정 기간이 만료되는데, 투기 우려 등이 없어 재지정하지 않게 됐다.",
                       "primary"))

# 2020년 국제교류복합지구 인근은 당시 동 단위 전체 지정이었다.
for gu, dong, code in [("강남구", "삼성동", "11680"), ("강남구", "대치동", "11680"),
                       ("강남구", "청담동", "11680"), ("송파구", "잠실동", "11710")]:
    rows.append(record("designation", "2020-06-23", "2021-06-22", "서울특별시", gu,
                       dong, "dong", "국제교류복합지구 인근 법정동 전체", "토지",
                       "2020-06-17", "yna_2020_designation",
                       "서울 송파구 잠실동, 강남구 삼성·대치·청담동 등 총 4개동이 토지거래허가구역으로 지정돼",
                       "secondary", code))

# 2021년 지정은 법정동 전체가 아니라 단지·사업구역 경계이므로 subarea이다.
subareas = [
    ("강남구", "압구정아파트지구", "압구정동의 24개 단지"),
    ("영등포구", "여의도아파트지구 및 인근단지", "여의도동의 아파트지구 및 인근 16개 단지"),
    ("양천구", "목동택지개발사업지구", "목동·신정동의 14개 단지; 상업지역 제외"),
    ("성동구", "성수전략정비구역", "성수동1가 일대 전략정비구역"),
]
for gu, area, description in subareas:
    rows.append(record("designation", "2021-04-27", "2022-04-26", "서울특별시", gu,
                       area, "subarea", description, "주거지역 18㎡·상업지역 20㎡ 초과 토지 등",
                       "2021-04-22", "seoul_2021_designation",
                       "지정 대상 구역은 ▴압구정아파트지구(24개 단지) ▴여의도아파트지구 및 인근단지(16개 단지) ▴목동택지개발사업지구(14개 단지) ▴성수전략정비구역으로, 총 4.57㎢이다.",
                       "primary"))

# 2025년 조정은 4개 동 전체 중 291개 아파트만 해제되어 subarea 사건으로 기록한다.
for gu, dong in [("강남구", "삼성동"), ("강남구", "대치동"), ("강남구", "청담동"), ("송파구", "잠실동")]:
    rows.append(record("release", "2025-02-13", "", "서울특별시", gu,
                       f"{dong} 비재건축 아파트", "subarea",
                       "4개 법정동의 아파트 305곳 중 재건축 14곳을 제외한 291곳; 동별 목록 미확보",
                       "아파트", "2025-02-13", "seoul_2025_release",
                       "4개동(송파구 잠실동, 강남구 삼성·대치·청담동)에 위치한 아파트 305곳 중 291곳에 대한 토지거래허가구역 지정을 ‘즉시’ 해제한다.",
                       "primary"))

for gu in ["강남구", "서초구", "송파구", "용산구"]:
    rows.append(record("designation", "2025-03-24", "2025-09-30", "서울특별시", gu,
                       gu, "gu", "자치구 소재 아파트 전체", "아파트; 주거지역 6㎡·상업지역 15㎡ 초과 토지 등",
                       "2025-03-19", "molit_2025_guidance",
                       "(지정범위/기간) 강남·서초·송파·용산구 소재 아파트 전체 / ’25.3.24 ~ ’25.9.30",
                       "primary"))

for area, description, start, end in [
    ("강남·서초 자연녹지지역", "강남구·서초구 자연녹지지역 일대 26.69㎢", "2026-05-31", "2027-05-30"),
    ("강남·송파 주요 재건축 아파트 14개 단지", "강남구·송파구 재건축 아파트 14개 단지 1.43㎢", "2026-06-23", "2027-06-22"),
]:
    rows.append(record("extension", start, end, "서울특별시", "복수 자치구", area, "subarea",
                       description, "녹지지역 100㎡ 초과" if "자연녹지" in area else "주거지역 6㎡·상업·공업지역 15㎡ 초과",
                       "2026-05-07", "seoul_2026_extension",
                       f"{description} 지정기간 : {start.replace('-', '.')} ~ {end.replace('-', '.')}",
                       "primary"))

rows.sort(key=lambda row: (row["effective_start_date"], row["event_type"], row["gu"], row["area_name"]))
with history_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

years = Counter(row["effective_start_date"][:4] for row in rows)
levels = Counter(row["area_level"] for row in rows)
confidence = Counter(row["confidence"] for row in rows)
digest = hashlib.sha256(history_path.read_bytes()).hexdigest()

readme = f"""# 서울 토지거래허가구역 시점 이력

이 자료는 **완전한 전수 ledger가 아니라 원문으로 확인된 사건만 담은 부분 이력**입니다. 생성일 기준 TSV SHA-256은 `{digest}`입니다. 동일한 구역의 지정·연장·해제는 각각 별도 행이며, `effective_start_date`는 효력발생일, `announcement_date`는 공고·공개일입니다.

## 수록 범위

- 2006~2007: 확인된 행 없음
- 2008: 6개 자치구 준공업지역 지정(2013년 서울시 공식 해제자료의 소급 설명)
- 2009~2012: 신규 사건 미확인
- 2013: 위 준공업지역 지정 만료
- 2014~2019: 확인된 행 없음
- 2020: 삼성동·대치동·청담동·잠실동 지정(secondary source만 확보)
- 2021: 압구정·여의도·목동·성수의 단지·사업구역 지정
- 2022~2024: 연장 사실은 알려져 있으나 각 고시 원문과 정확한 공고일을 모두 확보하지 못해 행을 만들지 않음
- 2025: 4개 동의 비재건축 아파트 해제와 강남·서초·송파·용산구 아파트 전체 재지정
- 2026-01~09: 자연녹지지역과 주요 재건축 14개 단지의 연장

## 해석 및 point-in-time 규칙

`announcement_date` 이전에는 해당 사건을 알 수 없었던 것으로 처리합니다. 규제 적용 여부는 `effective_start_date`부터 판단하고, 종료일이 있으면 그 날짜까지 포함합니다. 공고일과 효력발생일 사이 거래에는 새 규제를 소급하지 않습니다. `expiration`·`release` 행의 시작일은 비규제 상태가 시작된 첫날입니다.

## 공간 매핑

`dong` 행만 `output/52.1.seoul_bjd_boundary.geojson`의 `sgg_cd`와 `umd_nm`을 결합한 `dong_key`에 직접 join할 수 있습니다. `subarea`는 단지, 아파트지구, 정비사업구역 또는 용도지역 경계이므로 법정동 전체에 부여하면 안 됩니다. polygon/필지 목록이 없을 때 법정동으로 근사하려면 주소 문구에서 동을 추출해 별도 crosswalk를 만들되, 그 동 전체가 규제된 것처럼 false positive가 생깁니다. 특히 2025년 2월 해제는 같은 동 안에서 14개 재건축 단지를 유지했으므로 동 단위 binary mapping이 부적절합니다.

## 남은 gap과 제한

2006~2007 및 2014~2019의 서울 전체 고시 색인을 확립하지 못했습니다. 2020 사건은 서울시 고시 PDF가 아니라 보도를 사용해 `secondary`입니다. 2021 이후 매년의 연장 고시, 공공재개발·신속통합기획·모아타운의 개별 후보지 전체, 용산정비창, 외국인 대상 및 2025-10·2026-08 국토교통부 지정은 이번 time box에서 사건별 원문·경계를 완전히 대조하지 못해 제외했습니다. 2008 준공업지역도 자치구 안의 정확한 필지/용도지역 polygon이 없어 `subarea`입니다.

## 재실행

`/home/yjkim/test/boomingup/.venv/bin/python data/collect/71.collect_land_permit_zone.py`를 실행합니다. `src/` 파일이 있으면 network 요청 없이 재사용합니다. 기존 `output/raw/regulation/land_permit_zones.json`은 현재 현황 교차검증용으로 복사합니다. download 실패는 기존 cache가 없는 경우 마지막에 출력되며, curated 행은 임의로 보완하지 않습니다.
"""
readme_path.write_text(readme, encoding="utf-8")

print(f"행 수(연도): {dict(sorted(years.items()))}")
print(f"행 수(area_level): {dict(sorted(levels.items()))}")
print(f"근거 등급: primary={confidence['primary']}, secondary={confidence['secondary']}")
print("가장 큰 gap: 2006~2007, 2014~2019, 2022~2024 연장 고시, 후보지별 전체 경계")
print(f"TSV: {history_path} ({len(rows)}행)")
for failure in failures:
    print(f"download {failure}")
