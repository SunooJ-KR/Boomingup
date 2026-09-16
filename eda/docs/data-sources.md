# EDA에서 추가로 쓴 외부 데이터 출처

리포 루트 `docs/data-sources.md`(모델 파이프라인 팀 관리)와는 별개로, `eda/` 브랜치에서
매매가 영향 요인 분석을 위해 새로 가져온 외부 데이터만 정리한다. AGENTS.md의
"데이터 출처와 수집 기준은 docs/data-sources.md에 정리한다" 원칙을 이 폴더 범위에서 따른다.

## 1. 법정동별 주민등록 인구·세대현황 (10번 축)

| 항목 | 내용 |
|---|---|
| 출처 | 행정안전부, 공공데이터포털(data.go.kr) — "법정동별(행정동 통반단위) 주민등록 인구 및 세대현황" |
| 데이터셋 ID | 15108071 |
| Endpoint | `https://apis.data.go.kr/1741000/stdgPpltnHhStus/selectStdgPpltnHhStus` |
| 인증키 | `.env`의 `MOIS_POPULATION_KEY` (data.go.kr 활용신청, 자동승인, 개발계정 일일 10,000건) |
| 수집 스크립트 | `eda/scripts/11_population_data.py` |
| 산출물 | `eda/output/11_population_dong_monthly.csv` (git 비추적, `*.csv` 규칙) |
| 수집 범위 | 2025Q2, 2026Q2 (2번 축의 "구 평균 vs 동별 하락" 비교와 맞추기 위해 두 분기만) |

주의:
- 통계는 **2022-10부터만** 공식 집계된다(그 이전은 이 API로 조회 불가).
- 한 번의 요청에 **최대 3개월(분기 하나)까지만** 조회 가능하다(`QUERY_PERIOD_LIMIT_EXCEEDED_ERROR`로 확인).
- 응답은 **법정동 하나에 통/반(統/班) 단위로 여러 행**이 나온다. `numOfRows`를 넉넉히 잡아도
  대치동(분기당 2,170여 행)처럼 큰 동은 한 페이지로 안 끝나서, **totalCount까지 페이지를
  끝까지 순회해야 한다**(2026-09-16, codex 검증에서 첫 페이지만 받고 뒷부분이 잘리는 버그를
  발견함 — `mois_population()` 함수에서 수정).
- 이 API는 **429(Too Many Requests)를 자주 반환**한다. 동시 요청 수를 4개 이하로 유지하고,
  429에는 더 길게(3초×시도횟수) backoff한다.

## 2. Kakao 주소검색 API (법정동코드 변환용)

| 항목 | 내용 |
|---|---|
| 출처 | Kakao 로컬 API, 주소 검색(`/v2/local/search/address.json`) |
| 인증키 | `.env`의 `KAKAO_REST_KEY` (이미 이 프로젝트에서 단지 좌표 지오코딩에 쓰던 키 재사용) |
| 용도 | `app.dong`의 (자치구명, 법정동명) 346개를 10자리 법정동코드(b_code)로 변환해 위 인구 API에 넘김 |

주의:
- 첫 번째 검색 결과를 무검증으로 쓰면 동명이인 법정동에서 엉뚱한 코드가 섞일 수 있다
  (2026-09-16, codex 검증에서 지적). **Kakao 응답의 `region_2depth_name`(구)·
  `region_3depth_name`(동)이 요청한 것과 정확히 일치할 때만** 채택하도록 고쳤다
  (`eda/scripts/11_population_data.py`의 `build_bcode_cache()`).
- 이 검증을 통과 못 한 동은 `b_code`가 비어 있고, 이후 인구 데이터 집계에서 자동으로 빠진다.
- `eda/output/11_dong_bcode.csv`에 Kakao가 실제로 반환한 구·동명(`kakao_region_2depth`,
  `kakao_region_3depth`)과 일치 여부(`matched`)를 같이 저장해 사후 감사가 가능하게 했다.
