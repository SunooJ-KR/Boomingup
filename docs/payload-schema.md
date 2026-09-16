# 프론트 payload 스키마

> 상태: 구현 반영 (2026-09-16). 결정 19~23으로 데이터 경로가 정해져 초안 딱지를 뗐다.
> 모델 공식 판정(결정 16·17)에 따라 12개월 예측과 구간 실측 coverage를 함께 공개한다.
> 스키마가 바뀌면 이 문서를 같은 PR에서 갱신한다.

## 1. 전달 경로

프론트는 API로 받는다. API가 DB(active snapshot)를 읽고, 접속이 없거나 조회가 실패하면
저장소의 샘플 JSON으로 폴백한다(결정 19). 응답의 `source`가 `db`인지 `sample`인지로 구분한다.

| 경로 | 내용 | 응답 형태 |
|---|---|---|
| `GET /api/meta` | 기준 분기, 데이터 기간, 예측 기간, 구간 coverage, 규제 기준일 | `{ source, meta }` |
| `GET /api/dongs` | 동 목록, 지역 태그, 동 대표 좌표 | `{ source, meta, dongs, centers }` |
| `GET /api/dong/{dong_id}?asOf={분기}` | 동 상세 | `{ source, detail }` |

폴백용 샘플은 `front/public/data/`에 있다(`meta.json`, `dongs.json`, `dong-details.json`).
실제 수치가 아니므로 화면에도 폴백 중임을 표시한다.

`dong_id` = `{sggCd}_{umdNm}` (예: `11680_개포동`). 결정 4의 동 키와 같다.
동 목록과 메타는 서버에서 한 번 읽어 화면에 내려보내고, 상세는 동을 선택할 때 가져온다(결정 20).

## 2. 동 목록 (`dongs`)

```json
{
  "dong_id": "11680_개포동",
  "sgg_cd": "11680",
  "gu_name": "강남구",
  "umd_name": "개포동",
  "status": "PREDICTED",
  "change_pct_est": 3.2,
  "lower_pct": -4.1,
  "upper_pct": 10.9,
  "n_sales_4q": 212,
  "tags": ["정비사업 정보 있음", "거래 많은 동"]
}
```

| 필드 | 설명 |
|---|---|
| `status` | `PREDICTED` 예측 제공 / `INSUFFICIENT_SALES` 직전 4분기 매매 20건 미만(결정 7) / `NOT_SERVED` 예측 미제공(결정 11). `app.dong_prediction`이 비어 있는 동안에는 `dong_index.eligible`로 뒤 두 값을 파생한다(결정 22) |
| `change_pct_est` | 추정 변화율(%). 모델 출력 log 변화 `y`를 `(exp(y) − 1) × 100`으로 바꾼 값, 소수 1자리. `status`가 `PREDICTED`가 아니면 `null` |
| `lower_pct`, `upper_pct` | conformal 추정 구간(%), 같은 변환. 구간이 없으면 `null` |
| `n_sales_4q` | 기준 분기 포함 직전 4분기 매매 건수 (취소 제외) |
| `tags` | 규칙 기반 지역 태그. 아래 §5 |

`centers`는 지도 마커용 동 대표 좌표다. 법정동 경계 GeoJSON이 없어 최근 매매가 있는 단지
좌표의 평균을 쓴다(결정 21). 좌표가 없는 동은 키 자체가 없다.

```json
{ "11680_개포동": { "lat": 37.4783, "lng": 127.0558 } }
```

## 3. 동 상세 (`detail`)

```json
{
  "dong_id": "11680_개포동",
  "prediction": { "status": "PREDICTED", "change_pct_est": 3.2, "lower_pct": -4.1, "upper_pct": 10.9 },
  "facts": {
    "n_sales_4q": 212,
    "jeonse_ratio_4q": 0.48,
    "redevelop_zones": { "designated": 3, "association": 2, "management": 1, "construction": 0 },
    "completed_households_8q": 1200,
    "reg_overheated": null
  },
  "comparison": { "seoul_change_pct": 13.6, "gu_change_pct": 10.3, "dong_change_pct": 10.7 },
  "area_stats": [
    { "band": "60㎡ 미만", "n_sales": 3483, "median_price_manwon": 50000, "min_price_manwon": 9700, "max_price_manwon": 108000 }
  ],
  "area_stats_period": "2024-09 ~ 2026-08",
  "complexes": [
    {
      "apt_seq": "11680-1234",
      "name": "○○아파트",
      "built_year": 1983,
      "households": 1500,
      "far_pct": 180.5,
      "redevelop": { "zone_name": "재건축", "stage": "관리처분", "stage_date": "" },
      "last_sale": { "date": "2026-08", "floor": 7, "area_m2": 84.9, "price_manwon": 245000 }
    }
  ]
}
```

| 필드 | 설명 |
|---|---|
| `comparison` | 서울 전체·자치구·선택 동의 최근 4분기 변화율(%). `dong_index`의 log 지수 차이로 계산하고, 서울·자치구는 eligible 동의 평균이다 |
| `area_stats` | 면적대별 과거 실적 조회. 예측이 아니라 지나간 거래 집계다. 표본이 적은 면적대는 중위값이 흔들리므로 `n_sales`를 항상 같이 쓴다 |
| `complexes[].redevelop` | 정비사업 매칭이 된 단지만 채운다. 매칭이 없으면 `null`이며 "구역 아님"을 뜻하지 않는다. `stage_date`는 현재 DB에 없어 빈 문자열이다 |
| `complexes[].last_sale` | 취소 제외 가장 최근 매매 |
| `facts.reg_overheated` | 동 단위 투기과열지구 값이 없어 항상 `null`이다. 화면은 대신 `meta.seoul_apartment_permit_zone`을 쓴다(결정 23) |

단지는 `app.complex`에 법정동 코드가 없어서 매매 기록의 `(sgg_cd, umd_nm)`으로 묶는다.
매매가 한 번도 없던 단지는 목록에 나오지 않는다.

## 4. `meta`

| 필드 | 예 | 출처 |
|---|---|---|
| `as_of_quarter` | `"2026Q2"` | `dong_index`의 마지막 분기 |
| `data_period` | 매매 `"2006-01 ~ 2026-08"`, 전월세 `"2011-01 ~ 2026-08"` | `trade_batch` |
| `horizon_months` | `12` (결정 16·11) | 상수 |
| `model_passed` | `true` (결정 16) | 상수. DB에 자리가 생기면 옮긴다 |
| `interval_coverage_backtest` | `0.641` — 과거 검증에서 실제값이 추정 구간 안에 든 비율 (결정 17) | 상수. 같이 옮긴다 |
| `regulation_as_of` | 규제 기준일 | `regulation_summary` |
| `seoul_apartment_permit_zone` | 서울 전체 아파트 토지거래허가구역 지정 여부 | `regulation_summary` |

## 5. 지역 태그

규칙 기반이며, 서비스 대상 동 전체 분포의 상위 30%를 기준으로 붙인다
(`docs/front/product-plan.md` §4.3).

| 태그 | 기준 |
|---|---|
| `거래 많은 동` | 직전 4분기 매매 건수 상위 30% |
| `전세가율 높은 동` | 최근 1년 전세가율 상위 30% |
| `최근 준공 많은 동` | 최근 8분기 준공 비중 상위 30% |
| `30년 이상 단지 많은 동` | 준공 30년 이상 단지 비중 상위 30% |
| `정비사업 정보 있음` | 정비사업 구역 수가 1개 이상 |

태그 이름에 좋고 나쁨을 담지 않는다. "안정형", "성장형", "저평가형" 같은 이름은 쓰지 않는다.

## 6. 화면 문구 규칙 (AGENTS §6 계승)

- 예측: "향후 {horizon_months}개월 추정 변화율 +3.2% (추정 구간 −4.1% ~ +10.9%, 기준 2026년 2분기)"
- 구간 안내(예측 카드 하단 고정): "과거 검증에서 실제 변화율이 추정 구간 안에 든 비율은 약 64%이며, 시장 흐름이 바뀌는 시기에는 더 낮았습니다"
- `INSUFFICIENT_SALES`: "최근 1년 매매가 적어 예측하지 않음"
- `NOT_SERVED`: 예측 카드에 사유만 적고 수치를 만들지 않는다
- 금지 표현은 `front/scripts/check-wording.mjs`가 검사한다. `npm run check:wording`

## 7. 미정·확인 필요

| 항목 | 담당 |
|---|---|
| `app.dong_prediction` 적재 — 지금 비어 있어 모든 동이 표본 부족·예측 미제공으로 보인다 | 김용진 |
| 법정동 경계 GeoJSON — 지도 색칠용. 없어도 대표 좌표로 동작한다(결정 21) | 김용진·정선우 |
| `model_passed`, `interval_coverage_backtest`를 DB에 둘 자리 | 정선우 |
| 정비사업 단계 일자(`stage_date`) 적재 여부 | 김용진 |
