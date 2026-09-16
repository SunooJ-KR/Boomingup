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
    return docs[0]["address"]["b_code"]


def build_bcode_cache():
    if os.path.exists(BCODE_CACHE_PATH):
        print("b_code 캐시 재사용:", BCODE_CACHE_PATH)
        return pd.read_csv(BCODE_CACHE_PATH, dtype=str)

    dong = query_df("select dong, sgg_cd, umd_nm, gu_name from app.dong order by dong;")
    rows = []
    for i, r in dong.iterrows():
        try:
            bcode = kakao_bcode(r["gu_name"], r["umd_nm"])
        except urllib.error.HTTPError as e:
            print("kakao 오류", r["dong"], e)
            bcode = None
        rows.append({"dong": r["dong"], "sgg_cd": r["sgg_cd"], "umd_nm": r["umd_nm"],
                      "gu_name": r["gu_name"], "b_code": bcode})
        if (i + 1) % 50 == 0:
            print(f"  kakao b_code {i + 1}/{len(dong)}")
    out = pd.DataFrame(rows)
    out.to_csv(BCODE_CACHE_PATH, index=False)
    print(f"b_code 캐시 저장: {BCODE_CACHE_PATH} (미매칭 {out['b_code'].isna().sum()}건)")
    return out


def mois_population(b_code, ym_from, ym_to):
    params = {
        "serviceKey": MOIS_KEY, "type": "json", "numOfRows": "999", "pageNo": "1",
        "srchFrYm": ym_from, "srchToYm": ym_to, "stdgCd": b_code,
    }
    url = "https://apis.data.go.kr/1741000/stdgPpltnHhStus/selectStdgPpltnHhStus?" + urllib.parse.urlencode(params, safe="%")
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    head = data["Response"]["head"]
    if head["resultMsg"] != "NORMAL_SERVICE":
        return []
    items = data["Response"]["items"]
    if items == "" or items is None:
        return []
    item = items["item"]
    return item if isinstance(item, list) else [item]


def build_population_data(bcode_df):
    valid = bcode_df.dropna(subset=["b_code"])
    all_rows = []
    for i, r in valid.iterrows():
        items = []
        for ym_from, ym_to in QUARTER_RANGES:
            try:
                items += mois_population(r["b_code"], ym_from, ym_to)
            except Exception as e:
                print("mois 오류", r["dong"], ym_from, e)
        for it in items:
            all_rows.append({
                "dong": r["dong"], "gu_name": r["gu_name"], "umd_nm": r["umd_nm"],
                "b_code": r["b_code"], "stats_ym": it["statsYm"],
                "hh_cnt": int(it["hhCnt"] or 0), "tot_nmpr_cnt": int(it["totNmprCnt"] or 0),
                "male_nmpr_cnt": int(it["maleNmprCnt"] or 0), "feml_nmpr_cnt": int(it["femlNmprCnt"] or 0),
            })
        if (i + 1) % 50 == 0:
            print(f"  mois {i + 1}/{len(valid)}")
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
