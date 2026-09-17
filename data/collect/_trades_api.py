# ============================================================================
# _trades_api.py
# ============================================================================
# Author:      yjkim
# Purpose:     국토부 실거래 API 호출을 11(전체 수집)과 61(snapshot)이 함께 쓴다
# Description: 두 스크립트가 같은 엔드포인트·같은 페이징·같은 키 처리를 쓰도록 한 곳에 둔다.
#              11은 정규화된 레코드를, 61은 원문 XML을 필요로 해서 두 갈래를 모두 낸다.
# ============================================================================

import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트

ROWS_PER_PAGE = 1000
SLEEP_SEC = 0.2          # 포털 권장 간격. 제거하면 간헐적 500이 늘어난다

ENDPOINTS = {
    "sale": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "rent": "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
}

SEOUL_LAWD = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}

# 소문자 정규화 후 되돌릴 표준 이름. 여기 없는 필드는 버린다
FIELD_MAP = {
    "aptseq": "aptSeq", "aptnm": "aptNm", "aptdong": "aptDong",
    "umdnm": "umdNm", "jibun": "jibun", "bonbun": "bonbun", "bubun": "bubun",
    "roadnm": "roadNm", "roadnmbonbun": "roadNmBonbun", "roadnmbubun": "roadNmBubun",
    "buildyear": "buildYear", "excluusear": "excluUseAr", "floor": "floor",
    "dealyear": "dealYear", "dealmonth": "dealMonth", "dealday": "dealDay",
    "sggcd": "sggCd",
    "dealamount": "dealAmount", "cdealtype": "cdealType",   # 매매 전용
    "deposit": "deposit", "monthlyrent": "monthlyRent",     # 전월세 전용
}


def load_key():
    env_path = work_dir / ".env"
    if not env_path.exists():
        raise SystemExit(".env 없음. DATA_GO_KR_KEY를 넣어주세요")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env에 DATA_GO_KR_KEY 없음")


SERVICE_KEY = load_key()


def mask_key(text):
    """requests의 예외 메시지에는 요청 URL이 통째로 들어간다. 키가 파일로 새지 않게 가린다."""
    return str(text).replace(SERVICE_KEY, "***")


def parse_response(text):
    """공공데이터포털은 성공/실패 모두 XML이다. resultCode를 먼저 본다."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None, f"XML 파싱 실패: {text[:200]}"

    code_node = root.find(".//resultCode")
    code = code_node.text.strip() if code_node is not None and code_node.text else None
    msg_node = root.find(".//resultMsg")
    message = msg_node.text.strip() if msg_node is not None and msg_node.text else ""

    # 성공 코드가 데이터셋마다 "00" / "0" / "000"으로 다르다. 숫자 0이면 성공으로 본다
    if code is not None and code.strip("0") != "":
        return None, f"API 오류 [{code}] {message}"

    total_node = root.find(".//totalCount")
    total = int(total_node.text) if total_node is not None and total_node.text else 0

    records = []
    for item in root.findall(".//item"):
        raw = {child.tag.lower(): (child.text or "").strip() for child in item}
        records.append({std: raw[low] for low, std in FIELD_MAP.items() if low in raw})
    return {"records": records, "total": total}, None


def fetch_month_pages(kind, lawd_cd, deal_ymd):
    """한 (구, 연월)의 전체 페이지를 받아 (페이지별 원문 XML, 레코드, 사유)를 돌려준다."""
    pages, collected = [], []
    page = 1
    while True:
        params = {
            "serviceKey": SERVICE_KEY,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": str(page),
            "numOfRows": str(ROWS_PER_PAGE),
        }
        try:
            response = requests.get(ENDPOINTS[kind], params=params, timeout=30)
        except requests.exceptions.RequestException as error:
            return None, None, f"요청 실패: {error}"
        if response.status_code != 200:
            return None, None, f"HTTP {response.status_code}: {response.text[:150]}"

        parsed, error = parse_response(response.text)
        if error:
            return None, None, error

        pages.append(response.text)
        collected.extend(parsed["records"])
        if len(collected) >= parsed["total"] or not parsed["records"]:
            return pages, collected, None
        page += 1
        time.sleep(SLEEP_SEC)


def fetch_month(kind, lawd_cd, deal_ymd):
    """한 (구, 연월)의 레코드만 받는다. 실패하면 (None, 사유)."""
    _, records, error = fetch_month_pages(kind, lawd_cd, deal_ymd)
    return records, error
