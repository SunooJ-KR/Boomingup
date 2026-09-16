"""10번 축(추가): 법정동별 주민등록 인구·세대수 수집.

절차:
1. app.dong(346개 법정동)을 Kakao 주소검색 API로 10자리 법정동코드(b_code)로 변환
   (KAKAO_REST_KEY 재사용, output/11_dong_bcode.csv에 캐시)
2. 행정안전부 "법정동별(행정동 통반단위) 주민등록 인구 및 세대현황" API
   (data.go.kr 15108071, MOIS_POPULATION_KEY)로 2022-10~2026-08 매월 조회
3. 동일 법정동 안의 통/반별 응답을 합산해 법정동×월 단위로 저장

주의: 이 통계는 2022-10부터만 존재한다(행정안전부 집계 시작월). 그 이전은 원천적으로 없다.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from _db import query_df

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")


def load_env():
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
KAKAO_KEY = ENV["KAKAO_REST_KEY"]
MOIS_KEY = ENV["MOIS_POPULATION_KEY"]

BCODE_CACHE_PATH = "../output/11_dong_bcode.csv"
POP_OUT_PATH = "../output/11_population_dong_monthly.csv"

# API가 한 번에 최대 3개월까지만 허용한다(QUERY_PERIOD_LIMIT_EXCEEDED_ERROR 확인함).
# 2번 축의 "2025Q2->2026Q2" 동별 상승률 비교와 바로 연결하기 위해 두 분기만 받는다.
QUARTER_RANGES = [("202504", "202506"), ("202604", "202606")]


def kakao_bcode(gu_name, umd_nm):
    q = urllib.parse.quote(f"서울특별시 {gu_name} {umd_nm}")
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={q}"
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KAKAO_KEY}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    docs = data.get("documents", [])
    if not docs:
        return None
    addr = docs[0]["address"]
    return {"b_code": addr["b_code"], "region_2depth_name": addr["region_2depth_name"],
            "region_3depth_name": addr["region_3depth_name"]}


def build_bcode_cache():
    if os.path.exists(BCODE_CACHE_PATH):
        print("b_code 캐시 재사용:", BCODE_CACHE_PATH)
        return pd.read_csv(BCODE_CACHE_PATH, dtype=str)

    dong = query_df("select dong, sgg_cd, umd_nm, gu_name from app.dong order by dong;")
    rows = []
    for i, r in dong.iterrows():
        bcode, ret_gu, ret_dong, matched = None, None, None, False
        try:
            result = kakao_bcode(r["gu_name"], r["umd_nm"])
            if result is not None:
                ret_gu, ret_dong = result["region_2depth_name"], result["region_3depth_name"]
                # Kakao 응답의 구·동명이 요청한 것과 일치할 때만 채택한다(첫 결과를 무검증으로
                # 쓰면 동명이인 법정동에서 엉뚱한 코드가 섞일 수 있음 — 2026-09-16 검증에서 지적됨)
                matched = (ret_gu == r["gu_name"]) and (ret_dong == r["umd_nm"])
                bcode = result["b_code"] if matched else None
        except urllib.error.HTTPError as e:
            print("kakao 오류", r["dong"], e)
        rows.append({"dong": r["dong"], "sgg_cd": r["sgg_cd"], "umd_nm": r["umd_nm"],
                      "gu_name": r["gu_name"], "b_code": bcode,
                      "kakao_region_2depth": ret_gu, "kakao_region_3depth": ret_dong, "matched": matched})
        if (i + 1) % 50 == 0:
            print(f"  kakao b_code {i + 1}/{len(dong)}")
    out = pd.DataFrame(rows)
    out.to_csv(BCODE_CACHE_PATH, index=False)
    print(f"b_code 캐시 저장: {BCODE_CACHE_PATH} (미매칭 {out['b_code'].isna().sum()}건)")
    return out


def _mois_request(b_code, ym_from, ym_to, page_no, num_rows=999):
    params = {
        "serviceKey": MOIS_KEY, "type": "json", "numOfRows": str(num_rows), "pageNo": str(page_no),
        "srchFrYm": ym_from, "srchToYm": ym_to, "stdgCd": b_code,
    }
    url = "https://apis.data.go.kr/1741000/stdgPpltnHhStus/selectStdgPpltnHhStus?" + urllib.parse.urlencode(params, safe="%")
    max_attempts = 6
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_attempts - 1:
                time.sleep(3 * (attempt + 1))  # 429(요청 과다)는 더 길게 backoff
                continue
            if attempt == max_attempts - 1:
                raise
            time.sleep(2)
        except (urllib.error.URLError, TimeoutError):
            if attempt == max_attempts - 1:
                raise
            time.sleep(2)


def mois_population(b_code, ym_from, ym_to):
    """totalCount를 끝까지 순회한다 — numOfRows(999) 한 페이지만 받으면 통/반이 많은
    동(예: 대치동 2,170건)에서 뒷부분이 잘린다(2026-09-16 검증 후 발견한 버그)."""
    data = _mois_request(b_code, ym_from, ym_to, page_no=1)
    head = data["Response"]["head"]
    if head["resultMsg"] != "NORMAL_SERVICE":
        return []
    total_count = int(head["totalCount"])
    num_rows = int(head["numOfRows"])
    items = data["Response"]["items"]
    all_items = []
    if items not in ("", None):
        item = items["item"]
        all_items = item if isinstance(item, list) else [item]

    n_pages = -(-total_count // num_rows) if num_rows else 1
    for page in range(2, n_pages + 1):
        data = _mois_request(b_code, ym_from, ym_to, page_no=page)
        items = data["Response"]["items"]
        if items in ("", None):
            continue
        item = items["item"]
        all_items += item if isinstance(item, list) else [item]

    if len(all_items) != total_count:
        print(f"  경고: {b_code} {ym_from}-{ym_to} totalCount={total_count}인데 {len(all_items)}건만 받음")
    return all_items


def _fetch_dong(row):
    dong, b_code, gu_name, umd_nm = row["dong"], row["b_code"], row["gu_name"], row["umd_nm"]
    rows = []
    for ym_from, ym_to in QUARTER_RANGES:
        try:
            items = mois_population(b_code, ym_from, ym_to)
        except Exception as e:
            print("mois 오류", dong, ym_from, e)
            continue
        for it in items:
            rows.append({
                "dong": dong, "gu_name": gu_name, "umd_nm": umd_nm,
                "b_code": b_code, "stats_ym": it["statsYm"],
                "hh_cnt": int(it["hhCnt"] or 0), "tot_nmpr_cnt": int(it["totNmprCnt"] or 0),
                "male_nmpr_cnt": int(it["maleNmprCnt"] or 0), "feml_nmpr_cnt": int(it["femlNmprCnt"] or 0),
            })
    return rows


def build_population_data(bcode_df):
    # API 응답이 느릴 때(2026-09-16 확인: 건당 약 14초) 순차 호출이면 전체 수집에 몇 시간이
    # 걸린다. I/O 대기가 대부분이라 스레드로 동시에 여러 동을 요청한다.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    valid = bcode_df.dropna(subset=["b_code"])
    records = valid.to_dict("records")
    all_rows = []
    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_dong, r): r["dong"] for r in records}
        for fut in as_completed(futures):
            all_rows += fut.result()
            done += 1
            if done % 20 == 0:
                print(f"  mois {done}/{len(records)}")
    raw = pd.DataFrame(all_rows)
    # 통/반 단위 응답을 법정동x월로 합산
    agg = raw.groupby(["dong", "gu_name", "umd_nm", "stats_ym"], as_index=False).agg(
        hh_cnt=("hh_cnt", "sum"), tot_nmpr_cnt=("tot_nmpr_cnt", "sum"),
        male_nmpr_cnt=("male_nmpr_cnt", "sum"), feml_nmpr_cnt=("feml_nmpr_cnt", "sum"),
    )
    agg.to_csv(POP_OUT_PATH, index=False)
    print(f"저장 완료: {POP_OUT_PATH} ({len(agg)}행, 동 {agg['dong'].nunique()}개, 월 {agg['stats_ym'].nunique()}개)")
    return agg


if __name__ == "__main__":
    bcode_df = build_bcode_cache()
    build_population_data(bcode_df)
