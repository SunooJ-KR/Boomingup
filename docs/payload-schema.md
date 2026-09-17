# 프론트 payload 스키마 v2

> 확정: 2026-09-17. 예측 중심의 v1을 대체하는 현행 계약이다. 필드 이름은 `feature-spec.md` §5의 컬럼명을 그대로 쓴다.
> 원칙: 예측 필드를 지우고, 그 자리에 판단 표현이 들어오지 않도록 응답 구조에서부터 막는다. 목록에는 변화율을 싣지 않는다.

## 1. 전달 경로

프론트는 아래 API 세 개를 사용한다. API가 DB의 active snapshot을 읽고, 접속이 없거나 조회가 실패하면 `front/public/data/`의 샘플 JSON으로 폴백한다. 응답의 `source`가 `db`인지 `sample`인지로 구분하며, 샘플일 때는 실제 수치가 아님을 화면에 표시한다.

| 경로 | 내용 | 응답 형태 |
|---|---|---|
| `GET /api/meta` | 기준 분기, 데이터 기간, 판단 보조 기준일과 문턱 | `{ source, meta }` |
| `GET /api/dongs` | 동 목록, 태그, 대표 좌표 | `{ source, meta, dongs, centers }` |
| `GET /api/dong/{dong_id}?asOf={분기}` | 동 상세 | `{ source, detail }` |

`dong_id`는 `{sggCd}_{umdNm}` 형식이다. 동 목록과 메타는 한 번 읽고, 상세는 동을 선택할 때 가져온다. `centers`는 최근 매매가 있는 단지 좌표의 평균이며 좌표가 없는 동은 키를 만들지 않는다.

새 데이터 출처는 `app.dong_support` 한 테이블이다(`feature-spec.md` §5). `app.dong_prediction`은 더 이상 읽지 않는다. 테이블은 지우지 않고 남긴다(결정 66).

## 2. `meta`

```json
{
  "as_of_quarter": "2026Q2",
  "data_period": { "sale": "2006-01 ~ 2026-08", "rent": "2011-01 ~ 2026-08" },
  "support_as_of": "2026Q2",
  "cluster_as_of": "2026Q2",
  "thresholds": { "few_sales": 20, "one_complex_share": 0.5, "high_index_se": 0.032, "delta_sigma": 2 },
  "regulation_as_of": "2026-06-30",
  "seoul_apartment_permit_zone": true
}
```

| 변경 | 내용 |
|---|---|
| 삭제 | `horizon_months`, `model_passed`, `interval_coverage_backtest`. 예측이 없으므로 뜻이 없다 |
| 추가 | `support_as_of` (`dong_support`의 `as_of`), `cluster_as_of` (`66.1` 최신 기점), `thresholds` (화면 각주용 상수) |
| 유지 | `as_of_quarter`, `data_period`, 규제 관련 필드 |

## 3. 동 목록 (`dongs`)

```json
{
  "dong_id": "11680_개포동",
  "sgg_cd": "11680",
  "gu_name": "강남구",
  "umd_name": "개포동",
  "n_sales_4q": 212,
  "ppm2_med_4q_manwon": 2480,
  "sample_flags": [],
  "index_se_band": "LOW",
  "structure_type": 0,
  "structure_desc": "평당가 높음 · 강남 6km대",
  "tags": ["정비사업 정보 있음", "거래 많은 동"]
}
```

| 필드 | 설명 |
|---|---|
| `status`, `change_pct_est`, `lower_pct`, `upper_pct`, `status_reason` | **삭제** |
| `n_sales_4q` | 유지 |
| `ppm2_med_4q_manwon` | 최근 4분기 ㎡당 매매 중앙가(만원). `dong_feature.sale_ppm2_med_4q`. 가격대 필터·정렬용 |
| `sample_flags` | `FEW_SALES` / `ONE_COMPLEX_DOMINATES` / `HIGH_INDEX_ERROR` 배열. 없으면 `[]` |
| `index_se_band` | `LOW` / `MID` / `HIGH` |
| `structure_type`, `structure_desc` | 구조 유형 번호와 자동 설명. 없으면 `null` |
| `tags` | 유지. 구조 유형은 태그가 아니라 별도 필드다 |

**목록에 변화율이 없다.** `change_12m`, `delta_12m`을 싣지 않는다. 목록 행에 변화율이 있으면 눈으로 정렬하게 된다. 변화율은 상세에서만 오차와 함께 본다.

`centers`는 `{ "dong_id": { "lat": number, "lng": number } }` 형태를 유지한다.

### 3.1 목록 필터·정렬 (프론트 `lib/filter.ts` 계약)

| 필터 | 필드 | 값 |
|---|---|---|
| 자치구 | `gu_name` | 유지 |
| 가격대 | `ppm2_med_4q_manwon` | 구간 `[min, max]`. 구간 경계는 프론트가 전체 분포의 4분위로 만든다 |
| 표본 상태 | `sample_flags` | "주의 없음" = 빈 배열, "주의 있음" = 하나 이상 |
| 구조 유형 | `structure_type` | 0~3 다중 선택 |
| 지역 태그 | `tags` | 유지 |

정렬: `umd_name`, `gu_name`, `n_sales_4q`, `ppm2_med_4q_manwon`. 그 외 없음.

## 4. 동 상세 (`detail`)

```json
{
  "dong_id": "11680_개포동",
  "sample": {
    "n_sales_4q": 212,
    "n_complexes_4q": 14,
    "dominant_complex_share_4q": 0.21,
    "index_se": 0.0091,
    "index_se_band": "LOW",
    "flags": []
  },
  "change": {
    "dong_12m_pct": 15.7,
    "seoul_12m_pct": 12.7,
    "delta_12m_pct": 2.7,
    "delta_se_pct": 1.3,
    "delta_state": "DISTINGUISHABLE",
    "peak_5y_gap_pct": 0.0,
    "peak_5y_gap_se_pct": 1.3,
    "peak_5y_state": "AT_PEAK"
  },
  "flows": [
    { "quarter": "2024Q3", "n_sales": 48, "n_jeonse": 61, "monthly_rent_share": 0.34 }
  ],
  "facts": {
    "n_sales_4q": 212,
    "jeonse_ratio_4q": 0.48,
    "redevelop_zones": { "designated": 3, "association": 2, "management": 1, "construction": 0 },
    "completed_households_8q": 1200,
    "reg_overheated": null
  },
  "structure": {
    "type": 0,
    "desc": "평당가 높음 · 강남 6km대",
    "as_of": "2026Q2"
  },
  "peers": [
    { "dong_id": "11680_대치동", "gu_name": "강남구", "umd_name": "대치동", "reason": "평당가와 전세가율이 가까워요" }
  ],
  "reference": { "seoul_12m_pct": 12.7 },
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

| 블록 | 설명 | 화면 블록 (`investment-support-plan.md` §4.1) |
|---|---|---|
| `prediction` | **삭제** | — |
| `comparison` | **삭제**. `change`가 대신한다. v1의 서울·자치구 변화율은 eligible 평균이었고 오차가 없었다 | — |
| `sample` | `dong_support`의 F-1 값 그대로 | 1 표본 상태 |
| `change` | F-2 값을 %로 바꾼 것. `delta_state`가 `INDISTINGUISHABLE`이면 **`delta_12m_pct`를 `null`로 보낸다.** 서버가 지운다. 프론트가 숨기는 게 아니다. `peak_5y_*`도 같은 규칙, 저거래 동은 `null` | 2 지난 12개월 변화와 5년 범위 |
| `flows` | 최근 8분기 분기별 매매 건수, 전세 건수, 월세 비중. API가 `trade_sale`·`trade_rent`에서 집계한다. `dong_support`에 없다 | 3 거래 흐름 |
| `facts` | 전세가율, 거래 수, 정비사업, 준공, 규제 같은 관측 정보. 예측 이유처럼 설명하지 않는다 | 4 사실 정보 |
| `structure` | F-3. 없으면 `null` | 목록·상세 구조 유형 |
| `peers` | F-4. 표시 조건을 못 채우면 **`null`**. 빈 배열 `[]`이 아니다. 프론트는 `null`이면 블록을 그리지 않는다 | 5 함께 볼 동 |
| `reference` | μ. 접힘 블록용. 지난 기간의 서울 평균이라는 안내 문구는 프론트 상수 | 6 참고치 |

`change`의 % 변환: `(exp(x) − 1) × 100`, 소수 1자리. 오차도 같은 변환을 log 값 ±se에 적용한 뒤 반폭으로 낸다. `delta_se_pct`는 근사값이다.

`area_stats`는 면적대별 매매 가격 분포다. 표본이 적으면 중앙값이 흔들리므로 `n_sales`를 항상 함께 보낸다. `complexes[].redevelop`은 매칭된 단지만 채우고, 매칭이 없으면 `null`이다. `complexes[].last_sale`은 취소되지 않은 가장 최근 매매다. 단지는 매매 원장의 `(sgg_cd, umd_nm)`과 `bjd_code`로 동에 연결한다.

## 5. 지역 태그

지역 태그는 서비스 대상 동 전체 분포의 상위 30%를 기준으로 붙인다. 구조 유형은 군집 소속이므로 태그에 넣지 않는다.

| 태그 | 기준 |
|---|---|
| `거래 많은 동` | 직전 4분기 매매 건수 상위 30% |
| `전세가율 높은 동` | 최근 1년 전세가율 상위 30% |
| `최근 준공 많은 동` | 최근 8분기 준공 비중 상위 30% |
| `30년 이상 단지 많은 동` | 준공 30년 이상 단지 비중 상위 30% |
| `정비사업 정보 있음` | 정비사업 구역 수가 1개 이상 |

## 6. 화면 문구 규칙

`wording-guide.md`가 정한다. payload는 문구를 싣지 않고 코드값(`sample_flags`, `delta_state`, `index_se_band`)만 보낸다. 예외는 `structure_desc`와 `peers[].reason`으로, 산출 스크립트가 사전을 적용한 문자열이다. 그 사전도 `wording-guide.md` §4·§5에 있다.

## 7. 프론트 변경 범위

| 파일 | 변경 |
|---|---|
| `lib/types.ts` | `PredictionStatus`, `Prediction`, `DongComparison` 삭제. `SampleFlag`, `DongSample`, `DongChange`, `DongFlow`, `DongStructure`, `DongPeer` 추가. `AreaStat` 주석의 "과거 실적" 수정 |
| `lib/derive.ts` | `deriveStatus` 삭제. 태그 파생은 유지 |
| `lib/filter.ts` | `statuses` → `flagged: boolean | null`, `priceBand`, `structureTypes` |
| `lib/format.ts` | `STATUS_LABEL`, `STATUS_REASON` 삭제. flag 문장, `delta_state` 문장은 `wording-guide.md`에서 |
| `lib/queries.ts` | `dong_prediction` join 제거. `dong_support` join 추가. `flows` 집계 쿼리 추가 |
| `components/dong/prediction-card.tsx` | 삭제. `sample-card.tsx`, `change-card.tsx`로 대체 |
| `components/dong/status-badge.tsx` | flag 배지로 교체 |
| `components/dong/comparison-card.tsx` | 삭제. `change-card`에 흡수 |
| `components/dong/facts-panel.tsx`, `area-stats-card.tsx`, `complex-list.tsx` | 유지. 문구만 검수 |
| `components/dong/map-panel.tsx` | 색상 기준을 flag 유무·구조 유형으로. 변화율 색칠 없음 |
| `public/data/*.json` | 샘플을 v2 형태로 갱신 |
| `scripts/check-wording.mjs` | `wording-guide.md` §2의 추가 금지어 반영 |

`front/lib/*.test.ts`는 위 변경에 맞춰 고친다. `deriveStatus` 테스트는 삭제한다.

## 8. DB

`app.dong_support` 신설. 컬럼은 `feature-spec.md` §5 + `snapshot_id`. 기본키 `(snapshot_id, dong)`. `data/db/001_boomingup_tables.sql`에 DDL을 추가하고 `50.load_db.py`에 `--kind support`를 더한다.

`app.dong_prediction`은 읽지 않지만 남긴다. 결정 22(비어 있을 때 `eligible`로 파생)는 폐기한다.

## 9. 미정

| 항목 | 담당 |
|---|---|
| `flows`의 월세 비중 정의(건수 기준인지 보증금 환산인지) | 프론트·데이터 |
| 가격대 필터 구간 경계를 4분위로 할지 고정 금액으로 할지 | 프론트 |
| `peers`의 `gu_name`, `umd_name`을 API가 붙일지 프론트가 목록에서 찾을지 | 프론트 |
