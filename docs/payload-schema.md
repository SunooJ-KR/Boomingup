# 프론트 payload 스키마 (초안, 정선우 님 합의 필요)

> 상태: 초안 (2026-09-15). 모델 공식 판정(docs/decisions.md 결정 10·11) 전이라 서비스할 예측 기간은 비워 둔다.
> 합의 후 이 문서를 정본으로 삼고, 바뀌면 같은 PR에서 갱신한다.

## 1. 파일 구성

| 경로 | 내용 | 크기 추정 |
|---|---|---|
| `front/public/data/dongs.json` | 서울 법정동 목록 + 동 예측 카드 요약 (지도·목록용) | 동 약 340개 |
| `front/public/data/dong/{dong_id}.json` | 동 상세: 예측 카드 + 소속 단지 사실정보 | 동당 1개 |
| `front/public/data/meta.json` | 기준 분기, 데이터 기간, 예측 기간, 모델 판정 요약, 규제 기준일 | 1개 |

`dong_id` = `{sggCd}_{umdNm}` (예: `11680_개포동`). 결정 4의 동 키와 같다.

## 2. `dongs.json`

```json
[
  {
    "dong_id": "11680_개포동",
    "sgg_cd": "11680",
    "gu_name": "강남구",
    "umd_name": "개포동",
    "status": "PREDICTED",
    "change_pct_est": 3.2,
    "lower_pct": -4.1,
    "upper_pct": 10.9,
    "n_sales_4q": 212
  }
]
```

| 필드 | 설명 |
|---|---|
| `status` | `PREDICTED` 예측 제공 / `INSUFFICIENT_SALES` 직전 4분기 매매 20건 미만(결정 7) / `NOT_SERVED` 모델이 채택 기준을 통과하지 못해 예측 미제공(결정 11) |
| `change_pct_est` | 추정 변화율(%). 모델 출력 log 변화 `y`를 `(exp(y) − 1) × 100`으로 바꾼 값, 소수 1자리. `status`가 `PREDICTED`가 아니면 `null` |
| `lower_pct`, `upper_pct` | conformal 추정 구간(%), 같은 변환. 구간이 없으면 `null` |
| `n_sales_4q` | 기준 분기 포함 직전 4분기 매매 건수 (취소 제외) |

## 3. `dong/{dong_id}.json`

```json
{
  "dong_id": "11680_개포동",
  "prediction": { "status": "PREDICTED", "change_pct_est": 3.2, "lower_pct": -4.1, "upper_pct": 10.9 },
  "facts": {
    "n_sales_4q": 212,
    "jeonse_ratio_4q": 0.48,
    "redevelop_zones": { "designated": 3, "association": 2, "management": 1, "construction": 0 },
    "completed_households_8q": 1200,
    "reg_overheated": true
  },
  "complexes": [
    {
      "apt_seq": "11680-1234",
      "name": "○○아파트",
      "built_year": 1983,
      "households": 1500,
      "far_pct": 180.5,
      "redevelop": { "zone_name": "○○재건축", "stage": "관리처분", "stage_date": "2024-05-10" },
      "last_sale": { "date": "2026-08", "floor": 7, "area_m2": 84.9, "price_manwon": 245000 }
    }
  ]
}
```

- `complexes[].redevelop`은 정비사업 매칭이 된 단지만 채운다(재건축 81.9%, 재개발 1.7% 매칭). 매칭이 없으면 `null`이며 "구역 아님"을 뜻하지 않는다
- `last_sale`은 취소 제외 가장 최근 매매

## 4. `meta.json`

| 필드 | 예 |
|---|---|
| `as_of_quarter` | `"2026Q2"` (예측 기점) |
| `data_period` | 매매 `"2006-01 ~ 2026-08"`, 전월세 `"2011-01 ~ 2026-08"` |
| `horizon_months` | 공식 판정 후 확정 (결정 11). 미정이면 `null` |
| `model_passed` | 결정 10 판정 결과 |
| `regulation_as_of` | 투기과열지구 기준일 |

## 5. 화면 문구 규칙 (AGENTS §6 계승, 표기 검사 스크립트로 강제 예정)

- 예측: "향후 {horizon_months}개월 추정 변화율 +3.2% (추정 구간 −4.1% ~ +10.9%, 기준 2026년 2분기)"
- `INSUFFICIENT_SALES`: "최근 1년 매매가 적어 예측하지 않음"
- `NOT_SERVED`: 예측 카드 없이 사실정보만 표시
- 금지: 저평가/고평가/적정가/싸다/비싸다/유망/추천/투자 적격, "80% 보장", "재건축으로 N% 오릅니다"

## 6. 미정·확인 필요

| 항목 | 담당 |
|---|---|
| 법정동 경계 GeoJSON 출처 (지도 색칠용) — 현재 보유 데이터에 없음 | 김용진·정선우 |
| 단지 좌표를 동 상세에 넣을지 (`14.1` 보유) | 정선우 |
| payload를 git으로 추적할지 (새 `.gitignore`의 `output/*`, `build/` 규칙 영향) | 정선우 |
