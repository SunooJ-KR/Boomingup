# ============================================================================
# 66.collect_ledger_by_dong.py
# ============================================================================
# Author:      yjkim
# Purpose:     서울 법정동별 건축물대장 표제부를 snapshot 단위로 수집한다
# Description: cache는 output/raw/ledger_dong/<snapshot>/에 저장한다.
#              467개 법정동 cache가 모두 완전할 때만 공식 결과를 쓴다.
# ============================================================================

import argparse
import json
import math
import re
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"
BOUNDARY_PATH = output_dir / "52.1.seoul_bjd_boundary.geojson"
CACHE_ROOT = output_dir / "raw" / "ledger_dong"
RESULT_PATH = output_dir / "66.1.building_ledger_by_dong.txt"
API_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
ROWS_PER_CALL = 100
MAX_CALLS_PER_RUN = 9000
MAX_RETRY = 3
OK_RESULT_CODES = {"00", "000", "NORMAL_SERVICE"}


def parse_args():
    parser = argparse.ArgumentParser(description="서울 법정동별 건축물대장 표제부 수집")
    parser.add_argument("--snapshot", default=date.today().strftime("%Y%m%d"),
                        help="cache snapshot 날짜(YYYYMMDD, 기본값: 오늘)")
    parser.add_argument("--cache-only", action="store_true",
                        help="network를 사용하지 않고 기존 cache만 검증·집계")
    parsed = parser.parse_args()
    try:
        datetime.strptime(parsed.snapshot, "%Y%m%d")
    except ValueError as error:
        parser.error(f"--snapshot은 유효한 YYYYMMDD여야 합니다: {error}")
    return parsed


args = parse_args()
CACHE_DIR = CACHE_ROOT / args.snapshot
MANIFEST_PATH = CACHE_DIR / "manifest.tsv"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_env(key):
    for line in (work_dir / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f".env에 {key} 없음")


# cache-only에서는 API key를 읽지도 않는다.
SERVICE_KEY = None if args.cache_only else load_env("DATA_GO_KR_KEY")


def mask_key(text):
    value = str(text)
    return re.sub(re.escape(SERVICE_KEY), "<SERVICE_KEY>", value) if SERVICE_KEY else value


# ============================================================================
# 1. 법정동 목록
# ============================================================================

boundary = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
dongs = pd.DataFrame([feature["properties"] for feature in boundary["features"]])
dongs["sigungu_cd"] = dongs["emd_cd"].str[:5]
dongs["bjdong_cd"] = dongs["emd_cd"].str[5:8] + "00"
dongs["dong_key"] = dongs["sigungu_cd"] + dongs["bjdong_cd"]
assert len(dongs) == 467, f"법정동 수가 467개가 아니다: {len(dongs)}"
assert (dongs["sigungu_cd"] == dongs["sgg_cd"]).all(), "emd_cd 앞 5자리가 sgg_cd와 다르다"
assert dongs["dong_key"].is_unique, "법정동 코드가 중복된다"
old = pd.read_csv(output_dir / "19.1.building_ledger.txt", sep="\t", dtype=str,
                  usecols=["sigungu_cd", "bjdong_cd"])
missing = set(old["sigungu_cd"] + old["bjdong_cd"]) - set(dongs["dong_key"])
assert not missing, f"19.1 코드가 법정동 목록에 없다: {sorted(missing)[:5]}"


# ============================================================================
# 2. API 호출 또는 cache 읽기
# ============================================================================

n_calls = 0


class QuotaExceeded(Exception):
    pass


def cache_path(dong_key, page_no):
    return CACHE_DIR / f"{dong_key}_p{page_no:04d}.json"


def read_cache(path):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result.get("items"), list):
            raise ValueError("items가 list가 아니다")
        int(result["total_count"])
        return result
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cache 손상: {path.name}: {error}") from error


def fetch_page(sigungu_cd, bjdong_cd, page_no):
    """cache가 없을 때만 호출하며 API 오류 body는 저장하지 않는다."""
    global n_calls
    path = cache_path(sigungu_cd + bjdong_cd, page_no)
    if path.exists():
        return read_cache(path)
    if args.cache_only:
        return None
    params = {"serviceKey": SERVICE_KEY, "sigunguCd": sigungu_cd, "bjdongCd": bjdong_cd,
              "numOfRows": ROWS_PER_CALL, "pageNo": page_no, "_type": "json"}
    label = f"{sigungu_cd}{bjdong_cd} p{page_no}"
    for attempt in range(1, MAX_RETRY + 1):
        if n_calls >= MAX_CALLS_PER_RUN:
            raise QuotaExceeded
        time.sleep(0.06 if attempt == 1 else 2 ** attempt)
        try:
            response = requests.get(API_URL, params=params, timeout=30)
            n_calls += 1
            payload = response.json()
            header = payload["response"]["header"]
            result_code = str(header.get("resultCode", ""))
            if response.status_code != 200 or result_code not in OK_RESULT_CODES:
                print(f"[경고] API 오류 {label} ({attempt}/{MAX_RETRY}): "
                      f"HTTP {response.status_code}, resultCode={result_code!r}")
                continue
            body = payload["response"]["body"]
            raw_items = (body.get("items") or {}).get("item") or []
            items = raw_items if isinstance(raw_items, list) else [raw_items]
            result = {"result_code": result_code,
                      "total_count": int(body.get("totalCount") or 0), "items": items}
        except (requests.RequestException, ValueError, TypeError, KeyError) as error:
            print(f"[경고] 요청 실패 {label} ({attempt}/{MAX_RETRY}): {mask_key(error)[:160]}")
            continue
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
    return None


def n_pages(total_count):
    return max(1, math.ceil(total_count / ROWS_PER_CALL))


first = {}
try:
    for row in dongs.itertuples():
        page = fetch_page(row.sigungu_cd, row.bjdong_cd, 1)
        if page is not None:
            first[row.dong_key] = int(page["total_count"])
    for row in dongs.itertuples():
        if row.dong_key not in first:
            continue
        for page_no in range(2, n_pages(first[row.dong_key]) + 1):
            if fetch_page(row.sigungu_cd, row.bjdong_cd, page_no) is None:
                break
except QuotaExceeded:
    print(f"[중단] 실행당 호출 상한 {MAX_CALLS_PER_RUN}건에 도달했습니다.")


# ============================================================================
# 3. 완전성 gate와 manifest
# ============================================================================

gate_errors = []
manifest_rows = []
all_items = []
for row in dongs.itertuples():
    page_one = cache_path(row.dong_key, 1)
    if not page_one.exists():
        gate_errors.append(f"{row.dong_key}: 1페이지 없음")
        continue
    first_page = read_cache(page_one)
    total_count = int(first_page["total_count"])
    expected_pages = n_pages(total_count)
    expected_paths = [cache_path(row.dong_key, page_no)
                      for page_no in range(1, expected_pages + 1)]
    actual_paths = sorted(CACHE_DIR.glob(f"{row.dong_key}_p*.json"))
    if any(not path.exists() for path in expected_paths) or len(actual_paths) != expected_pages:
        gate_errors.append(f"{row.dong_key}: page 불연속/개수 불일치")
        continue
    dong_items = []
    result_status = "ok"
    mtimes = []
    for path in expected_paths:
        page = read_cache(path)
        if int(page["total_count"]) != total_count:
            gate_errors.append(f"{row.dong_key}: page별 totalCount 불일치")
        result_code = page.get("result_code")
        if result_code is None:
            result_status = "legacy_cache"
        elif str(result_code) not in OK_RESULT_CODES:
            gate_errors.append(f"{path.name}: API resultCode={result_code!r}")
        dong_items.extend(page["items"])
        mtimes.append(path.stat().st_mtime)
    if len(dong_items) != total_count:
        gate_errors.append(f"{row.dong_key}: items {len(dong_items)} != totalCount {total_count}")
    all_items.extend((item, row.umd_nm) for item in dong_items)
    manifest_rows.append({"snapshot": args.snapshot, "dong_key": row.dong_key,
                          "total_count": total_count, "pages": expected_pages,
                          "fetched_at": datetime.fromtimestamp(max(mtimes)).astimezone().isoformat(),
                          "result_code_status": result_status})

if len(manifest_rows) != 467:
    gate_errors.append(f"완료 법정동 {len(manifest_rows)}/467")
if gate_errors:
    print("GATE FAIL")
    for error in gate_errors[:20]:
        print(f"  {error}")
    raise SystemExit(1)
pd.DataFrame(manifest_rows).to_csv(MANIFEST_PATH, sep="\t", index=False, lineterminator="\n")


# ============================================================================
# 4. 표 만들기
# ============================================================================

FIELDS = {
    "sigunguCd": "sigungu_cd", "bjdongCd": "bjdong_cd", "bun": "bun", "ji": "ji",
    "platGbCd": "plat_gb_cd", "platPlc": "plat_plc", "newPlatPlc": "new_plat_plc",
    "bldNm": "bld_nm", "dongNm": "dong_nm", "mgmBldrgstPk": "mgm_bldrgst_pk",
    "regstrGbCdNm": "regstr_gb_cd_nm", "mainAtchGbCdNm": "main_atch_gb_cd_nm",
    "mainPurpsCd": "main_purps_cd", "mainPurpsCdNm": "main_purps_cd_nm", "etcPurps": "etc_purps",
    "hhldCnt": "hhld_cnt", "hoCnt": "ho_cnt", "fmlyCnt": "fmly_cnt",
    "grndFlrCnt": "grnd_flr_cnt", "heit": "heit", "totArea": "tot_area",
    "pmsDay": "pms_day", "stcnsDay": "stcns_day", "useAprDay": "use_apr_day", "crtnDay": "crtn_day",
}
records = []
for item, umd_nm in all_items:
    record = {column: item.get(field) for field, column in FIELDS.items()}
    record.update({"umd_nm": umd_nm, "snapshot": args.snapshot})
    records.append(record)
ledger = pd.DataFrame(records, columns=list(FIELDS.values()) + ["umd_nm", "snapshot"])
for column in ["hhld_cnt", "ho_cnt", "fmly_cnt", "grnd_flr_cnt", "heit", "tot_area"]:
    ledger[column] = pd.to_numeric(ledger[column], errors="coerce")

ledger["use_apr_day"] = ledger["use_apr_day"].fillna("").astype(str).str.strip()
is_empty = ledger["use_apr_day"].eq("")
is_eight_digits = ledger["use_apr_day"].str.fullmatch(r"\d{8}")
parsed_date = pd.to_datetime(ledger["use_apr_day"].where(is_eight_digits),
                             format="%Y%m%d", errors="coerce")
ledger["use_apr_qc"] = "ok"
ledger.loc[is_empty, "use_apr_qc"] = "empty"
ledger.loc[~is_empty & ~is_eight_digits, "use_apr_qc"] = "malformed"
ledger.loc[is_eight_digits & parsed_date.isna(), "use_apr_qc"] = "invalid_date"
valid_date = parsed_date.notna()
# strftime는 1000년 이전 연도를 4자리로 보존하지 않으므로 원문을 조합한다.
ledger["use_apr_date"] = pd.NA
ledger["use_apr_month"] = pd.NA
ledger.loc[valid_date, "use_apr_date"] = (
    ledger.loc[valid_date, "use_apr_day"].str[:4] + "-"
    + ledger.loc[valid_date, "use_apr_day"].str[4:6] + "-"
    + ledger.loc[valid_date, "use_apr_day"].str[6:8])
ledger.loc[valid_date, "use_apr_month"] = (
    ledger.loc[valid_date, "use_apr_day"].str[:4] + "-"
    + ledger.loc[valid_date, "use_apr_day"].str[4:6])

base = (ledger["main_purps_cd_nm"] == "공동주택") & (ledger["hhld_cnt"] > 0)
etc = ledger["etc_purps"].fillna("")
ledger["is_apartment"] = base & etc.str.contains("아파트")
non_apartment_words = "다세대|연립|기숙사|도시형|오피스텔"
floor_kind = etc.str.contains("아파트") | (
    ~etc.str.contains(non_apartment_words) & (ledger["grnd_flr_cnt"] >= 5))
ledger["is_apartment_floor_rule"] = base & floor_kind

duplicates = int(ledger.duplicated("mgm_bldrgst_pk").sum())
if duplicates:
    print(f"GATE FAIL: mgmBldrgstPk 중복 {duplicates}건")
    raise SystemExit(1)
temporary_path = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
ledger.to_csv(temporary_path, sep="\t", index=False, lineterminator="\n")
temporary_path.replace(RESULT_PATH)

strict = ledger["is_apartment"]
floor = ledger["is_apartment_floor_rule"]
print(f"전체 행: {len(ledger):,}")
print(f"strict 아파트: {int(strict.sum()):,}행 / {int(ledger.loc[strict, 'hhld_cnt'].sum()):,}세대")
print(f"floor rule 아파트: {int(floor.sum()):,}행 / {int(ledger.loc[floor, 'hhld_cnt'].sum()):,}세대")
for qc, count in ledger["use_apr_qc"].value_counts().reindex(
        ["ok", "empty", "malformed", "invalid_date"], fill_value=0).items():
    print(f"use_apr_qc {qc}: {count:,}")
print(f"최신 use_apr_date: {ledger['use_apr_date'].dropna().max()}")
legacy_pages = sum(row["result_code_status"] == "legacy_cache" for row in manifest_rows)
print("GATE PASS: 467개 동, page 연속, items=totalCount")
print(f"resultCode: 새 cache 정상 code만 허용; legacy 표시 동 {legacy_pages}개")
print(f"snapshot: {args.snapshot}, cache 신규 호출: {n_calls}건")
