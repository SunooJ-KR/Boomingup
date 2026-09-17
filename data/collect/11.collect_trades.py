# ============================================================================
# 11.collect_trades.py
# ============================================================================
# Author:      yjkim
# Purpose:     서울 25개 구 아파트 실거래(매매 + 전월세) 전체 제공 기간을 수집한다
# Description: 동별 상승률 예측에 여러 시장 사이클이 필요해 기간을 API 제공 시작점까지 늘렸다.
#              - 매매는 2006-01, 전월세는 2011-01부터 제공된다 (2026-09-15 실측:
#                전월세 2006-01은 0건, 2011-01부터 존재. 과거 매매도 aptSeq 100% 채워짐)
#              - 임앤장에서 받은 2021-09 이후 캐시(output/raw/)는 그대로 재사용한다
#              - 매매는 aptSeq가 있는 '상세' 엔드포인트만 쓴다 (일반은 aptSeq 없음)
#              - 응답 키를 전부 소문자로 정규화한 뒤 표준 이름으로 되돌린다.
#                매매는 roadNm, 전월세는 roadnm 이라 공통 처리하면 조용히 결측이 된다
#              - (구, 연월, 종류) 단위로 JSON 캐시를 남겨 중단 후 재개할 수 있다.
#                공공데이터포털 일 호출 한도에 걸려도 다음 날 이어받으면 된다
#
#              통과 기준:
#                (1) 미수집 (구, 연월, 종류) 조합 0건
#                (2) 매매·전월세 모두 aptSeq 결측률 < 1%
#                (3) 25개 구 전부 거래 1건 이상
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import importlib.util
import json
import time
from pathlib import Path

import pandas as pd

# 점 파일명이라 일반 import가 안 되는 형제 모듈을 경로로 읽는다
_spec = importlib.util.spec_from_file_location(
    "boomingup_trades_api", Path(__file__).with_name("_trades_api.py"))
_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api)

ENDPOINTS = _api.ENDPOINTS
SEOUL_LAWD = _api.SEOUL_LAWD
SLEEP_SEC = _api.SLEEP_SEC
fetch_month = _api.fetch_month
mask_key = _api.mask_key

work_dir = Path(__file__).resolve().parents[2]   # 저장소 루트
output_dir = work_dir / "output"
cache_dir = output_dir / "raw"

END_YM = "202608"        # 2026-09는 아직 진행 중인 달이라 제외한다
START_YM = {"sale": "200601", "rent": "201101"}   # 종류별 API 제공 시작월


def month_list(kind):
    periods = pd.period_range(START_YM[kind], END_YM, freq="M")
    return [period.strftime("%Y%m") for period in periods]


# ============================================================================
# 2. 수집 (캐시가 있으면 건너뛴다)
# ============================================================================

months_by_kind = {kind: month_list(kind) for kind in ENDPOINTS}
print(f"===== 1. 수집 대상 =====")
for kind, months in months_by_kind.items():
    print(f"  [{kind}] {len(SEOUL_LAWD)}개 구 x {len(months)}개월 ({months[0]} ~ {months[-1]})")
print(f"  총 {len(SEOUL_LAWD) * sum(len(m) for m in months_by_kind.values())}회 호출 예정 (캐시분 제외)")

failures = []
for kind in ENDPOINTS:
    (cache_dir / kind).mkdir(parents=True, exist_ok=True)
    months = months_by_kind[kind]
    done = 0
    for lawd_cd, gu_name in SEOUL_LAWD.items():
        for deal_ymd in months:
            cache_path = cache_dir / kind / f"{lawd_cd}_{deal_ymd}.json"
            if cache_path.exists():
                done += 1
                continue

            records, error = fetch_month(kind, lawd_cd, deal_ymd)
            if error:
                failures.append({"kind": kind, "lawd_cd": lawd_cd, "gu": gu_name,
                                 "deal_ymd": deal_ymd, "error": mask_key(error)[:200]})
                print(f"  [실패] {kind} {gu_name} {deal_ymd}: {mask_key(error)[:200]}")
                continue

            cache_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
            done += 1
            time.sleep(SLEEP_SEC)

        print(f"진행 [{kind}] {gu_name}: 누적 {done}/{len(SEOUL_LAWD) * len(months)}")

print("\n===== 2. 수집 완료 =====")
print(f"  실패 {len(failures)}건")
if failures:
    fail_path = output_dir / "11.0.collect_failures.txt"
    pd.DataFrame(failures).to_csv(fail_path, sep="\t", index=False, lineterminator="\n")
    print(f"  실패 목록: {fail_path}")
    print("  ※ 일 호출 한도라면 내일 이 스크립트를 다시 실행하면 이어받는다")


# ============================================================================
# 3. 적재 및 저장
# ============================================================================

def load_kind(kind):
    frames = []
    for cache_path in sorted((cache_dir / kind).glob("*.json")):
        records = json.loads(cache_path.read_text(encoding="utf-8"))
        if records:
            frames.append(pd.DataFrame(records))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


print("\n===== 3. 적재 =====")
sale = load_kind("sale")
rent = load_kind("rent")

for name, frame in [("매매", sale), ("전월세", rent)]:
    if frame.empty:
        raise SystemExit(f"{name} 수집 결과가 비어 있다. 캐시를 확인할 것")
    frame["deal_ym"] = frame["dealYear"] + frame["dealMonth"].str.zfill(2)
    frame["gu"] = frame["sggCd"].map(SEOUL_LAWD)
    print(f"  {name} {len(frame):,}행 / 단지 {frame['aptSeq'].nunique():,}개")

def to_manwon(frame, column):
    """금액은 '145,000' 형태의 문자열이다. 결측·빈칸은 NaN으로 남긴다."""
    if column not in frame.columns:
        raise SystemExit(f"기대한 금액 필드 {column}가 없다. FIELD_MAP을 확인할 것")
    return pd.to_numeric(
        frame[column].str.replace(",", "", regex=False).replace("", pd.NA), errors="coerce"
    )


# 취소 거래는 실제 체결이 아니다. 지우지 않고 표시만 해 downstream이 고르게 한다
sale["is_cancelled"] = sale.get("cdealType", pd.Series("", index=sale.index)).fillna("").eq("O")
sale["deal_amount_manwon"] = to_manwon(sale, "dealAmount")
rent["deposit_manwon"] = to_manwon(rent, "deposit")
rent["monthly_rent_manwon"] = to_manwon(rent, "monthlyRent")
rent["is_jeonse"] = rent["monthly_rent_manwon"].eq(0)

sale_path = output_dir / "11.1.trades_sale.txt"
rent_path = output_dir / "11.2.trades_rent.txt"
sale.to_csv(sale_path, sep="\t", index=False, lineterminator="\n")
rent.to_csv(rent_path, sep="\t", index=False, lineterminator="\n")


# ============================================================================
# 4. 자체 검증
# ============================================================================

print("\n===== 4. 판정 =====")

missing = {
    kind: sum(
        not (cache_dir / kind / f"{lawd_cd}_{deal_ymd}.json").exists()
        for lawd_cd in SEOUL_LAWD
        for deal_ymd in months_by_kind[kind]
    )
    for kind in ENDPOINTS
}
sale_null = sale["aptSeq"].isna().mean() * 100 if "aptSeq" in sale else 100.0
rent_null = rent["aptSeq"].isna().mean() * 100 if "aptSeq" in rent else 100.0
gu_covered = sale["gu"].nunique()

checks = [
    ("미수집 조합 0건", sum(missing.values()) == 0, f"매매 {missing['sale']} / 전월세 {missing['rent']}"),
    ("매매 aptSeq 결측 < 1%", sale_null < 1, f"{sale_null:.2f}%"),
    ("전월세 aptSeq 결측 < 1%", rent_null < 1, f"{rent_null:.2f}%"),
    ("25개 구 전부 거래 존재", gu_covered == len(SEOUL_LAWD), f"{gu_covered}개 구"),
]
for label, passed, observed in checks:
    print(f"  [{'PASS' if passed else 'FAIL'}] {label:<28} 실측 {observed}")

print(f"\n  전세 비율 {rent['is_jeonse'].mean() * 100:.1f}% / 전월세 거래량은 매매의 {len(rent) / len(sale):.1f}배")
print(f"\n매매: {sale_path}")
print(f"전월세: {rent_path}")
