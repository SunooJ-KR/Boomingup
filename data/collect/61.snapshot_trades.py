# ============================================================================
# 61.snapshot_trades.py
# ============================================================================
# Author:      yjkim
# Purpose:     최근 몇 달 실거래를 "오늘 본 그대로" 날짜별로 남긴다 (vintage 적재)
# Description: 계획 docs/model-develope-plan.md §2.2, 진행 docs/model-build-process.md P0-2.
#              실거래는 계약 후 신고까지 시차가 있어 최근 분기 지수가 아래로 치우친다.
#              이걸 고치려면 "분기 종료 후 d일에는 최종 건수의 몇 %가 보였는가"라는
#              도착 곡선이 필요한데, 그건 과거 시점에 무엇이 보였는지를 기록해 둬야만
#              알 수 있다. 지금은 그 기록이 없어 N-1을 학습할 수 없다.
#
#              **오늘 시작하지 않으면 영구히 잃는 데이터다.** 이 스크립트는 매일(또는
#              주 1회) 돌려서 쌓기만 한다. 쓰는 쪽은 4분기 이상 쌓인 뒤의 N-1이다.
#
#              저장: output/raw/snapshot/{조회일}/{종류}/{구코드}_{연월}.json.gz
#              같은 날 다시 돌리면 이미 받은 조합은 건너뛴다. 덮어쓰지 않는다.
#              조회일 기준으로 파일이 나뉘므로 vintage가 섞이지 않는다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

import argparse
import gzip
import importlib.util
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "boomingup_trades_api", Path(__file__).with_name("_trades_api.py"))
_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_api)

work_dir = Path(__file__).resolve().parents[2]
snapshot_root = work_dir / "output" / "raw" / "snapshot"

# 신고 기한이 계약일로부터 30일이고 지연·정정이 뒤따르므로, 최근 6개월이면
# 도착 곡선의 가파른 구간을 모두 담는다. 더 늘리면 호출만 늘고 얻는 게 없다
RECENT_MONTHS = 6


def recent_months(months, today):
    """조회 시점 기준 최근 N개월의 연월 문자열. 이번 달도 진행 중인 채로 담는다."""
    end = pd.Period(today, freq="M")
    return [(end - offset).strftime("%Y%m") for offset in range(months)][::-1]


# ============================================================================
# 1. 대상
# ============================================================================

parser = argparse.ArgumentParser(description="최근 실거래를 조회일별로 적재한다")
parser.add_argument("--months", type=int, default=RECENT_MONTHS, help="거슬러 담을 개월 수")
parser.add_argument("--kinds", default="sale,rent", help="쉼표로 구분한 종류")
args = parser.parse_args()

as_of = date.today().isoformat()
kinds = [kind.strip() for kind in args.kinds.split(",") if kind.strip()]
months = recent_months(args.months, date.today())
snapshot_dir = snapshot_root / as_of

print("===== 1. 적재 대상 =====")
print(f"  조회일 {as_of}")
print(f"  {', '.join(kinds)} × {len(_api.SEOUL_LAWD)}개 구 × {len(months)}개월 ({months[0]} ~ {months[-1]})")
print(f"  저장 위치 {snapshot_dir}")


# ============================================================================
# 2. 수집 (같은 날 이미 받은 조합은 건너뛴다)
# ============================================================================

manifest, failures, skipped, fetched = [], [], 0, 0

for kind in kinds:
    if kind not in _api.ENDPOINTS:
        raise SystemExit(f"모르는 종류: {kind}")
    (snapshot_dir / kind).mkdir(parents=True, exist_ok=True)

    for lawd_cd, gu_name in _api.SEOUL_LAWD.items():
        for deal_ymd in months:
            path = snapshot_dir / kind / f"{lawd_cd}_{deal_ymd}.json.gz"
            if path.exists():
                skipped += 1
                continue

            pages, records, error = _api.fetch_month_pages(kind, lawd_cd, deal_ymd)
            if error:
                failures.append({"kind": kind, "lawd_cd": lawd_cd, "gu": gu_name,
                                 "deal_ymd": deal_ymd, "error": _api.mask_key(error)[:200]})
                print(f"  [실패] {kind} {gu_name} {deal_ymd}: {_api.mask_key(error)[:200]}")
                continue

            payload = {"as_of": as_of, "kind": kind, "lawd_cd": lawd_cd,
                       "deal_ymd": deal_ymd, "n_pages": len(pages), "records": records}
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False)

            manifest.append({"as_of": as_of, "kind": kind, "lawd_cd": lawd_cd, "gu": gu_name,
                             "deal_ymd": deal_ymd, "n_records": len(records)})
            fetched += 1
            time.sleep(_api.SLEEP_SEC)

        print(f"진행 [{kind}] {gu_name}: 새로 {fetched}건, 건너뜀 {skipped}건")


# ============================================================================
# 3. 조회일 요약
# ============================================================================

print("\n===== 2. 적재 완료 =====")
print(f"  새로 받음 {fetched}건, 이미 있어 건너뜀 {skipped}건, 실패 {len(failures)}건")

if manifest:
    # 도착 곡선은 이 요약만으로도 그릴 수 있다. 원문은 지수를 다시 추정할 때 쓴다
    manifest_path = snapshot_dir / "manifest.txt"
    frame = pd.DataFrame(manifest)
    if manifest_path.exists():
        frame = pd.concat([pd.read_csv(manifest_path, sep="\t", dtype=str), frame], ignore_index=True)
    frame.to_csv(manifest_path, sep="\t", index=False, lineterminator="\n")
    print(f"  목록: {manifest_path}")

    # 이번 실행분만 세면 건너뛴 조합이 빠져 조회일 전체 그림이 어긋난다. 목록 전체를 읽는다
    frame["n_records"] = pd.to_numeric(frame["n_records"])
    counts = frame.groupby(["kind", "deal_ymd"])["n_records"].sum().reset_index()
    print("\n  연월별 관측 건수 (조회일 전체):")
    print(counts.to_string(index=False))

fail_path = snapshot_dir / "failures.txt"
if not failures:
    # 앞선 실행에서 실패했다가 이번에 받아졌으면 목록을 남겨 두지 않는다
    fail_path.unlink(missing_ok=True)
if failures:
    pd.DataFrame(failures).to_csv(fail_path, sep="\t", index=False, lineterminator="\n")
    print(f"\n  실패 목록: {fail_path}")
    print("  ※ 일 호출 한도라면 같은 날 다시 실행하면 빠진 것만 이어받는다")

if not fetched and not skipped:
    raise SystemExit("받은 것도 건너뛴 것도 없다. 대상 설정을 확인할 것")
