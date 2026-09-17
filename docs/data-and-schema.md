# 활용 가능한 데이터와 DB 스키마 정리

> 작성: 2026-09-17. `docs/data-sources.md`, `docs/payload-schema.md`, `docs/decisions.md`,
> `docs/model-performance.md`, `data/db/*.sql`, `data/db/README.md`, `front/lib/queries.ts`를 읽고 정리했다.
> 지금 무엇을 가지고 있고, 그것이 DB 어디에 어떤 모양으로 들어 있는지 한 곳에서 보기 위한 문서다.
> 스키마나 데이터 범위가 바뀌면 이 문서도 같은 PR에서 갱신한다.

## 1. 한눈에 보는 데이터 흐름

```text
원천 수집                정제·모델                 DB(Railway Postgres)        프론트
─────────               ─────────                ──────────────────         ─────
국토부 실거래 API   →  output/11.1, 11.2      →  app.trade_sale / trade_rent  →  /api/*
한국은행 기준금리   →  43.1 (feature)          ─(모델 입력, DB 미적재)
규제 고시 원문      →  43.1 + regulation_summary → app.regulation_summary
정비사업 xlsx       →  42.1 (dong_feature)     →  app.dong_feature
건축물대장·지오코딩 →  19.1, 14.1              →  app.complex(기존 적재분)
법정동 경계 SHP     →  output/52.1.geojson     →  app.dong_boundary → front/public/data/*.geojson
매매 원장           →  60.1 (동 지수+추정오차) →  app.dong_index
모델(48·49)         →  49.1.latest_predictions →  app.dong_prediction (아직 비어 있음)
```

DB는 원천 전체가 아니라 **서비스와 모델이 공통으로 읽는 정제 테이블 + 거래 원장**만 담는다.
모든 조회는 `app.dataset_snapshot.is_active = true`인 snapshot만 join해서 읽는다
(`snapshot_id`를 숫자로 박지 않는다).

## 2. 지금 쓸 수 있는 데이터

### 2.1 확보한 것

| 데이터 | 범위 | 출처 | 지금 상태 |
|---|---|---|---|
| 아파트 매매 실거래 | 2006-01 ~ 2026-08, 서울 25개 구 | 국토부 `RTMSDataSvcAptTradeDev` | `app.trade_sale`에 원장 적재 |
| 아파트 전월세 실거래 | 2011-01 ~ 2026-08 | 국토부 `RTMSDataSvcAptRent` | `app.trade_rent`에 원장 적재 |
| 동별 가격 지수 | 2006Q1 ~ 2026Q2, 346개 동 | hedonic 지수 + 추정오차(`models/index/60`) | `app.dong_index` |
| 동별 feature | 기점 분기별 | `models/index/42` | `app.dong_feature` |
| 시장 이벤트·이벤트 스터디 | 거시·금리·정책 | `models/index/event_dates.tsv`, `46` | `app.market_event`, `event_summary`, `event_dong_path` |
| 단지 정보 | 9,160개 | 이전 프로젝트(임앤장) 적재분 + 건축물대장·지오코딩 | `app.complex` 등 기존 8개 테이블 |
| 법정동 경계 | 서울 467개 법정동(지수 매칭 340개) | GIS Developer 2023-07판, 원본 도로명주소 DB | `app.dong_boundary`, 프론트 정적 GeoJSON |
| 규제 요약 | 서울 아파트 토지거래허가구역 지정 여부 1행 | 국토부 고시 원문 | `app.regulation_summary` |
| 기준금리 | 1999-05 ~ 2026-08, 61행 | 한국은행 기준금리 추이 | 모델 feature(`43.1`)로만 존재, DB 미적재 |
| 투기과열지구 이력 | 서울 전환점 6개 시점 | 국토부 공고 원문 | 모델 feature(`43.1`)로만 존재, 동 단위 값 없음 |
| 정비사업 추진현황 | 2026-06 기준 496구역 | 서울 열린데이터광장 xlsx | `dong_feature`의 `rz_*` 컬럼으로 집계돼 들어감 |

### 2.2 없는 것 / 비어 있는 것

| 항목 | 상태 |
|---|---|
| `app.dong_prediction` | **테이블은 있으나 행이 없다.** 프론트는 `dong_index.eligible`로 상태를 파생한다(결정 22) |
| 동 단위 투기과열지구 값 | 없다. 화면은 `meta.seoul_apartment_permit_zone`을 대신 쓴다(결정 23) |
| 정비사업 단계 일자(`stage_date`) | DB에 없어 payload에서 빈 문자열이다 |
| 교통 호재(역 개통일) | 미수집. 1차 출처에 개통일 항목이 없다 |
| 입주 예정 물량 | 미수집. 건축물대장 사용승인일로 과거 준공만 만든다 |
| 주담대 금리 | 미수집. 한국은행 ECOS API 키가 필요하다 |
| `model_passed`, `interval_coverage_backtest` | DB에 자리가 없어 상수로 내려보낸다 |

### 2.3 알려진 품질 이슈

- 원장의 `sggCd`와 `umdNm`이 서로 다른 구를 가리키는 동 키 6개(`11200_신당동`, `11290_청량리동`,
  `11305_도봉동`, `11410_길동`, `11590_봉천동`, `11620_사당동`). 유효 매매 31건(0.0022%)이라 지수·모델
  영향은 없지만, 법정동 경계와도 매칭되지 않아 지수 동 346개 중 340개만 경계를 갖는다.
- `app.complex`의 `bjd_code`는 5자리 자체 코드라 법정동 코드가 아니고 `dong_boundary.emd_cd`와 일치가 0건이다(결정 44).
  단지는 매매 기록의 `(sgg_cd, umd_nm)`으로 묶는다.
  **매매가 한 번도 없던 단지는 동 상세 목록에 나오지 않는다.**
- 정비사업은 2026-06 한 시점 파일이라 해제·완료된 구역이 빠진 생존 편향이 있다.
- 해제 비율(`cancel_share_4q`)은 2020년부터만 표시가 있어 feature로 쓰지 않는다(결정 38).

## 3. DB 스키마

접속은 `DATABASE_READONLY_URL`(일반 팀원), `DATABASE_LOADER_URL`(적재), `DATABASE_PUBLIC_URL`(인프라)로
나뉜다. 상세는 `docs/railway-postgres-onboarding.md`.

### 3.1 snapshot 축과 batch 축

DB의 테이블은 두 종류의 버전 축 중 하나에 붙어 있다.

| 축 | 기준 테이블 | 붙는 테이블 | 교체 방식 |
|---|---|---|---|
| snapshot | `app.dataset_snapshot` (`snapshot_id`, `as_of`, `is_active`, `source`, `note`) | 정제 테이블 전부 + 기존 8개 테이블 + `dong_boundary` | `50.load_db.py --commit`이 새 snapshot을 만들고 검증 뒤 active 전환 |
| batch | `app.trade_batch` (`batch_id`, `kind`, `period_start/end`, `source_sha256`, `row_count`, `is_active`) | `trade_sale`, `trade_rent` | `51.load_trades.py --kind sale|rent --commit`. kind별 active 1개만 남기고 이전 batch는 cascade 삭제 |

`app.share`는 `snapshot_id`가 없어 어느 축에도 붙지 않는다(서비스에서 링크 생성 시 채워진다).

현재 active snapshot은 `snapshot_id = 3`, `as_of = 2026-08-31`이다.

### 3.2 신규 정제 테이블 (`data/db/001_boomingup_tables.sql`)

동 키 규칙: `dong = sgg_cd || '_' || umd_nm` (예: `11680_개포동`). CHECK 제약으로 강제한다(결정 4).

| 테이블 | PK | 주요 컬럼 | 내용 |
|---|---|---|---|
| `dong` | `snapshot_id, dong` | `sgg_cd`, `umd_nm`, `gu_name` | 동 마스터. 다른 동 테이블이 여기로 FK를 건다 |
| `dong_index` | `snapshot_id, dong, quarter` | `log_index`, `log_index_se`, `n_sales`, `n_sales_4q`, `eligible` | 분기별 hedonic 지수. `eligible`은 직전 4분기 매매 20건 기준(결정 7). `log_index_se`는 지수 추정오차로, 표본 잡음과 구 지수 수축 편향을 합친 값이다(`models/index/60`) |
| `dong_feature` | `snapshot_id, dong, as_of_quarter` | 아래 §3.3 | 기점 분기별 feature. 시점 누수를 막으려고 `as_of_quarter`를 키에 둔다(결정 13) |
| `dong_prediction` | `snapshot_id, dong, horizon_q` | `origin`, `status`, `market_hat`, `relative_hat`, `gamma`, `y_hat`, `change_pct_est`, `lower_pct`, `upper_pct`, `model_version` | 예측 결과. `status`는 `PREDICTED`/`INSUFFICIENT_SALES`만 허용. **현재 비어 있다** |
| `market_event` | `snapshot_id, event_id` | `effective_date`, `category`, `direction`, `label`, `verified`, `source` | 이벤트 기준일 목록. 예측 feature가 아니라 사실 표시용 |
| `event_summary` | `snapshot_id, event_id` | `event_quarter`, `base_quarter`, `n_dongs`, `pre/post_change_4q`, `post_median/p10/p90`, `share_up`, `overlapping_events` | 이벤트 전후 동별 지수 분포 요약 |
| `event_dong_path` | `snapshot_id, event_id, dong, k` | `quarter`, `rel_log_change` | 이벤트 기준 분기 대비 k분기 상대 변화 경로 |
| `dong_boundary` | `snapshot_id, dong` | `emd_cd`, `eng_nm`, `in_index`, `geometry`(jsonb), bbox 4개, centroid 2개, `source` | 법정동 경계. `geometry`는 GeoJSON Polygon/MultiPolygon만 CHECK로 허용 |

`dong_prediction`의 값 구조는 2단계 모델을 따른다: `y_hat = market_hat + gamma × relative_hat`.
현재 채택 모델은 M0(서울 모멘텀) + R0(0 예측), γ=0이라 **모든 동의 예측값이 같다**(결정 39).

### 3.3 `dong_feature` 컬럼 묶음

| 묶음 | 컬럼 | 모델 사용 |
|---|---|---|
| 거래 | `sale_n_all_4q`, `cancel_share_4q`, `sale_n_log_change_4q`, `rent_n_4q`, `rent_n_log_change_4q` | 유지 (단 `cancel_share_4q`는 결정 38로 제외) |
| 가격 | `sale_ppm2_med_4q`, `jeonse_ppm2_med_4q`, `median_age_4q`, `old30_share_4q` | 유지 |
| 전세 | `jeonse_share_4q`, `jeonse_ratio_4q` | 유지 (선별에서 가장 기여가 컸다) |
| 공급 | `completed_hh_4q`, `completed_hh_8q`, `completed_share_8q`, `stock_hh` | 유지 |
| 정비사업 | `rz_designated_n`, `rz_committee_n`, `rz_association_n`, `rz_implementation_n`, `rz_management_n`, `rz_construction_n`, `rz_active_households`, `rz_events_4q` | **feature에서 제외**(결정 14). 화면 사실정보로는 계속 쓴다 |

입지·용적률 feature와 거시·규제 feature도 결정 14 선별에서 제외됐다. 즉 이 테이블의 컬럼 중
정비사업 묶음은 "화면용", 나머지는 "모델 입력 + 화면용"으로 쓰인다.

### 3.4 거래 원장 (`trade_sale`, `trade_rent`)

API 응답 컬럼을 거의 그대로 두고, 파싱한 컬럼을 뒤에 덧붙인 모양이다.

| 테이블 | API 원본 컬럼 | 파생 컬럼 | 인덱스 |
|---|---|---|---|
| `trade_sale` | `apt_seq`, `apt_nm`, `apt_dong`, `umd_nm`, `jibun`, `bonbun`, `bubun`, 도로명 3개, `build_year`, `exclu_use_ar`, `floor`, `deal_year/month/day`, `sgg_cd`, `deal_amount`, `cdeal_type` | `deal_ym`, `gu`, `is_cancelled`, `deal_amount_manwon` | `(batch_id, apt_seq, deal_ym)`, `(batch_id, sgg_cd, umd_nm, deal_ym)` |
| `trade_rent` | 위와 유사 + `deposit`, `monthly_rent` | `deal_ym`, `gu`, `deposit_manwon`, `monthly_rent_manwon`, `is_jeonse` | 같은 두 조합 |

PK는 `(batch_id, row_no)`다. 취소 거래는 지우지 않고 `is_cancelled`로 남기며, 집계할 때
`not is_cancelled` 조건을 붙인다.

### 3.5 기존 테이블 (이전 프로젝트 적재분, DDL은 이 저장소에 없음)

active snapshot 기준 행 수다. `50.load_db.py --commit`이 새 snapshot으로 그대로 복사한다.

| 테이블 | 행 수 | 프론트 사용 |
|---|---|---|
| `complex` | 9,160 | 단지명, `built_year`, `total_households`, `far`, `redevelop_type`, `redevelop_stage`, `lat`, `lng` — 단지 목록과 동 대표 좌표에 쓴다 |
| `complex_metrics` | 9,160 | 미사용 |
| `horizon_profile` | 19,349 | 미사용 |
| `price_cell` | 40,848 | 미사용 |
| `price_series` | 137,405 | 미사용 |
| `estimate` | 5,207 | 미사용 |
| `comparable` | 120,271 | 미사용 |
| `regulation_summary` | 1 | `as_of`, `seoul_apartment_permit_zone` — meta에 쓴다 |
| `share` | 0 | snapshot 대상 아님 |

현재 화면이 실제로 읽는 기존 테이블은 `complex`와 `regulation_summary` 둘뿐이다.
나머지 6개는 적재돼 있지만 이 제품의 어느 경로에서도 조회하지 않는다.

### 3.6 권한

신규 테이블은 `boomingup_readonly`에 `select`, `boomingup_loader`에 `select/insert/update/delete`,
그리고 `app.trade_batch_batch_id_seq`에 `usage, select`를 준다. 적재 role에는 DDL 권한이 없다.
스키마 적용 후 `data/db/check_schema.sql`로 컬럼·PK·FK·CHECK 기대값을 대조한다.

## 4. 프론트가 실제로 읽는 경로

`front/lib/queries.ts` 기준이다. 상세 payload 형태는 `docs/payload-schema.md`.

| API | 읽는 테이블 |
|---|---|
| `GET /api/meta` | `dong_index`(마지막 분기), `trade_batch`(데이터 기간), `regulation_summary` |
| `GET /api/dongs` | `dong` + `dong_index` + `dong_feature` + `dong_prediction`, 대표 좌표는 `trade_sale` × `complex` |
| `GET /api/dong/{dong_id}` | 위 + `trade_sale`(면적대 통계·최근 매매), `complex`(단지 정보) |

DB 접속이 없거나 조회가 실패하면 `front/public/data/`의 샘플 JSON으로 폴백하고, 응답의 `source`가
`db`인지 `sample`인지로 구분한다(결정 19). 경계 GeoJSON은 DB가 아니라 정적 파일로 나간다(결정 42).

## 5. 중간 산출물 파일

`output/`은 git 비추적이다(`52.1`과 프론트 정적 GeoJSON만 예외적으로 저장소에 둔다).
아래 파일은 스크립트를 다시 돌려 만들 수 있다.

| 파일 | 만든 스크립트 | 쓰임 |
|---|---|---|
| `11.1.trades_sale.txt`, `11.2.trades_rent.txt` | `data/collect/11.collect_trades.py` | `51.load_trades.py` 입력 |
| `14.1.geocoded_master.txt` | `data/master/14.geocode_all.py` | 19의 입력 |
| `19.1.building_ledger.txt` | `data/collect/19.collect_building_ledger.py` | 준공·입주 feature |
| `40.1.dong_index.txt` | `models/index/40.build_dong_index.py` | `app.dong_index` |
| `42.1.dong_features.txt` | `models/index/42.build_dong_features.py` | `app.dong_feature` |
| `43.1.gu_macro_regulation.txt` | `models/index/43.build_macro_regulation.py` | 모델 feature(DB 미적재) |
| `46.1.event_dong_paths.txt`, `46.2.event_summary.txt` | `models/index/46.event_study.py` | `app.event_dong_path`, `app.event_summary` |
| `47.1~47.4` | `models/index/47.build_realtime_panel.py` | 48의 입력 |
| `48.1~48.5` | `models/index/48.evaluate_realtime_two_stage.py` | 성능 지표(`docs/model-performance.md`) |
| `49.model/model.json`, `49.1.latest_predictions.txt` | `models/index/49.build_final_model.py` | `app.dong_prediction` 적재 대기 |
| `52.1.seoul_bjd_boundary.geojson`, `52.2.dong_boundary_match.txt` | `models/index/52.build_dong_boundary.py` | `app.dong_boundary` |
| `front/public/data/dong-boundary.geojson`, `gu-boundary.geojson` | `models/index/53.export_front_boundary.py` | 지도 |

원천 SHP가 없어도 `52.1`은 `app.dong_boundary`에서 복원할 수 있다(결정 45, 복원 SQL은
`docs/data-sources.md` §6).

## 6. 이 데이터로 할 수 있는 것과 없는 것

**할 수 있는 것**

- 동·단지 단위 과거 사실 조회: 매매 건수, 면적대별 가격 분포, 최근 매매, 전세가율, 준공·정비사업 현황
- 서울·자치구·동의 지난 12개월 실제 변화율 비교
- 이벤트 기준일 전후의 동별 지수 흐름 표시
- 법정동·자치구 경계 기반 지도 선택

**할 수 없는 것**

- **동별로 다른 예측.** 채택 모델이 M0+R0라 246개 PREDICTED 동의 값이 모두 같다(+13.6%). 예측은
  "서울 시장 전망"으로 표기해야 한다(결정 39, `docs/model-performance.md` §8).
- 신뢰할 수 있는 구간 제시. 실측 coverage는 h=4에서 65.5%로 목표 80%에 미달하고, 국면 전환기에 더
  낮다. 실측값을 그대로 공개한다(결정 37).
- 동 단위 규제 상태 표시, 교통 호재·입주 예정 물량 반영 — 데이터가 없다.
