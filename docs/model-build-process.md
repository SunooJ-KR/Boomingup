# 모델 개발 진행 관리

`docs/model-develope-plan.md`의 계획을 실제 작업으로 옮긴 진행표다. **모델 작업은 이 문서를 읽고 시작하고, 끝나면 이 문서의 상태를 갱신한다.**
기존 `models/index/40~52` 스크립트는 참고용일 뿐, 이 계획의 산출물로 치지 않는다. 계획대로 처음부터 다시 만든다.

마지막 갱신: 2026-09-17

## 1. 운용 규칙

- 상태는 `Todo` / `Doing` / `Done` 세 가지만 쓴다.
- 작업을 시작하면 그 행의 상태를 `Doing`으로 바꾸고 §3 현황판에 담당·시작일을 적는다. `Doing`은 사람당 2개를 넘기지 않는다.
- 작업이 끝나면 상태를 `Done`으로 바꾸고 §6 완료 기록에 날짜·산출물·결정 번호를 한 줄로 남긴다. 완료 조건을 충족하지 못한 채 `Done`으로 바꾸지 않는다.
- 계획 자체가 바뀌면(작업 추가·삭제·완료 조건 변경) 이 문서를 고치고 이유를 `docs/decisions.md`에 기록한다.
- 새 스크립트 번호는 **60번부터** 쓴다. 기존 40~52번과 산출물 이름이 섞이지 않게 하기 위해서다.
- Phase 게이트(§5)를 통과하기 전에는 다음 Phase 작업을 `Doing`으로 올리지 않는다. 예외는 §4에 "병렬 가능"으로 표시한 것뿐이다.

## 2. 없는 데이터를 어떻게 덮을지

계획서가 요구하지만 지금 없는 데이터와, 각각의 대응이다. 대응은 "지금 당장 쓸 수 있는 근사"와 "정식 해결"을 나눠 적는다.

| 없는 것 | 어디에 필요한가 | 지금 당장 (근사) | 정식 해결 | 담당 작업 |
|---|---|---|---|---|
| 원천 API snapshot 이력 | Track N-1 도착률 곡선 | 계약일+30일 규칙으로 근사 vintage를 만들어 N-3에 사용 | **오늘부터** 원천 응답을 날짜별로 적재. 4분기 이상 쌓이면 N-1 학습 | P0-2, N-1 |
| 지수 표준오차 `log_index_se` | Track 0 shrinkage, gate, 구간 조정, 4.4 진단 | 없음. 만들기 전엔 아무것도 못 한다 | hedonic 재추정 시 시점효과의 SE를 같이 산출해 `dong_index`에 저장 | P0-1 |
| ~~세대수의 동 매핑 커버리지~~ 해결됨 | μ 재고가중 | — | 매매 기록 + `(구, bjd_code)` 사전으로 99.3%. 재고가중 확정(결정 43·47) | P0-4 Done |
| 거래 단지 수·상위 단지 집중도 | gate, 신뢰도 블록 | `trade_sale`에서 바로 집계 가능 | `dong_feature`에 `n_complexes_4q`, `dominant_complex_share_4q` 추가 | P0-5 |
| 전세 feature의 2021-06 break 표시 | Track C feature | break 더미 컬럼 추가 | 2021H2 이후 origin에서만 전세 feature 사용하는 정책을 C-3 설계에 명시 | C-3 |
| 정책 가격 문턱 이력 | Track C 추가 feature | 국토부 고시 원문에서 발표일·시행일·문턱을 수동 입력 | `policy_events` 테이블 신설 | C-3b |
| 주담대 금리 | Track C feature | v1 feature에서 제외. 기준금리(이미 있음)로 대체하지 않는다 (서울 전역 동일값은 feature 금지) | ECOS API 키 확보 후 `observed_at` 붙여 적재 | D-2 |
| 정비사업 시계열 (인가일) | Track C feature, 생존 편향 해소 | feature로 쓰지 않는다. 화면용 `rz_*`만 유지, "2026-06 시점, 해제·완료 미반영" 각주 | 인가일 이벤트 수집 | D-3 |
| 입주 예정 물량, 교통 호재 | Track C feature | v1에서 제외 | P2로 미룬다. 이 문서의 범위 밖 | — |
| 6개 동 키 불일치 (경계 미매칭) | 지도 | UI에 사유 노출 | `(구 코드, bjd_code)`가 맞는 쪽을 옳은 동으로 본다(결정 48) | D-4 |
| `dong_prediction` nowcast 행·확률·사유 코드 | 화면 ②③⑥ | 없음 | `status` CHECK 확장, `prob_above_seoul`, `delta_lower/upper`, `mu_ref`, `insufficient_reason` 추가 | P3-5 |

## 3. 현황판

| 상태 | 작업 ID | 담당 | 시작일 | 메모 |
|---|---|---|---|---|
| Doing | — | — | — | Phase 0·1 완료. 다음은 Phase 2 N-3 (nowcast) |

## 4. 작업 목록

### Phase 0 — 토대 (즉시)

| ID | 작업 | 상태 | 완료 조건 | 산출물 | 의존 |
|---|---|---|---|---|---|
| P0-1 | hedonic 지수를 재추정하며 동×분기 시점효과의 SE를 함께 산출하고 `dong_index.log_index_se` 컬럼을 추가 | Done | `dong_index` 전 행에 SE가 있고, 저거래 동일수록 SE가 큰지 산점도로 확인 | `models/index/60.build_dong_index_se.py`, 스키마 migration, `docs/data-and-schema.md` 갱신 | — |
| P0-2 | 원천 API 응답 snapshot 적재 시작 (실거래 매매·전월세, 날짜별 파일) | Done | 첫 snapshot이 `output/raw/snapshot/{YYYY-MM-DD}/`에 저장되고 재실행해도 덮어쓰지 않음 | `data/collect/61.snapshot_trades.py` | — (P0-1과 병렬 가능) |
| P0-3 | 평가 코드의 embargo 규칙(`s + horizon ≤ T`)을 새 평가 스크립트 설계에 명시하고 결정 기록 | Done | 결정 기록에 규칙과 근거가 있음 | `docs/decisions.md` | — |
| P0-4 | μ 가중 방식 확정: `complex.total_households`의 동 매핑 커버리지 측정 후 재고가중/거래가중 결정 | Done | 커버리지 수치와 결정이 `docs/decisions.md`에 있음 | 결정 기록, 측정 스크립트 | — |
| P0-5 | `dong_feature`에 `n_complexes_4q`, `dominant_complex_share_4q` 추가 | Done | 전 동×기점에 값이 있고 `trade_sale` 수동 집계와 표본 3개 일치 | `models/index/62.build_dong_features.py` (신규 feature 빌더의 첫 버전) | — |

### Phase 1 — Track 0 지수 개선

| ID | 작업 | 상태 | 완료 조건 | 산출물 | 의존 |
|---|---|---|---|---|---|
| T0-A | `n_sales` 기반 Empirical Bayes shrinkage로 동 시점효과를 구 평균 쪽으로 수축 | Done | 수축 전후 지수 안정성(분기 간 수정폭, 저거래 동 분산) 비교표 작성 | `models/index/63.shrink_dong_index.py`, `docs/model-performance.md` 비교표 | P0-1 |
| T0-B | (조건부) multilevel hedonic 재추정 | Todo | T0-A가 안정성 기준을 못 넘길 때만 시작. 그 전엔 `Doing`으로 올리지 않는다. **T0-A가 기준을 넘겼으므로 지금은 시작하지 않는다** | `models/index/70.*` | T0-A |
| T0-C | (조건부) 인접 동 가중 pooling 비교 | Todo | T0-A와 안정성 비교 | `dong_boundary`에서 인접 행렬 산출 | T0-A |

### Phase 2 — Track N nowcast

| ID | 작업 | 상태 | 완료 조건 | 산출물 | 의존 |
|---|---|---|---|---|---|
| N-3 | 수정폭 회귀: (확정치 − 잠정치)를 경과일수·관측 건수·취소율로 회귀. 계약일+30일 근사 vintage 사용 | Todo | 무보정 대비 잠정→확정 수정폭 MAE 개선폭에 block bootstrap 신뢰구간이 있고 0을 제외 | `models/index/65.build_nowcast.py`, `docs/model-performance.md` | P0-1 (T0-A와 병렬 가능) |
| N-1 | 도착률 보정: 실제 snapshot에서 도착 곡선 추정 | Todo | snapshot 4분기 이상 축적 후 시작. N-3와 성능 비교 | `models/index/66.*` | P0-2 축적 |
| N-2 | (조건부) 상태공간 필터 | Todo | N-3가 개선을 못 보일 때만 | — | N-3 |

### Phase 3 — Track C δ 사다리

| ID | 작업 | 상태 | 완료 조건 | 산출물 | 의존 |
|---|---|---|---|---|---|
| C-0/1 | 기준선 두 개 구현: δ̂=0, 구 평균 모멘텀 | Todo | rolling-origin(2015Q1~2025Q3) δ MAE, origin별 Spearman 분포 산출 | `models/index/67.evaluate_delta.py` (평가 프레임 자체) | P0-1, P0-3, P0-4 |
| C-2 | 수축 모멘텀: 동별 과거 4분기 상대 변화 × λ(SE) | Todo | C-0·C-1 대비 개선폭 신뢰구간이 0 제외 **그리고** HAC-DM p<0.05 **그리고** 4.4 진단 3종 통과 | 67의 후보 추가, `docs/model-performance.md` | C-0/1, T0-A |
| C-diag | 측정오차 진단 배터리: feature 기점 `t−1` 이동 시 성능 하락폭, SE 구간별 계수, 저SE 부분집합 성능 | Todo | 세 결과가 보고서에 있고 해석이 결정 기록에 있음 | 67 옵션, `docs/model-performance.md` | C-2와 동시 |
| C-3 | elastic net (전세 break 더미 포함) | Todo | C-2를 같은 기준으로 유의하게 이길 때만 채택 | 67 후보 추가 | C-2 통과 |
| C-3b | `policy_events` 테이블과 문턱 대비 거래가 feature, 거리 가중 인근 준공 물량 feature | Todo | feature가 `dong_feature`에 있고 as-of 원칙 검증 | 62 확장, migration | C-3 시작 시 |
| C-4 | LightGBM pooled, `1/se²` 가중 | Todo | C-3를 유의하게 이길 때만 | 67 후보 추가 | C-3 통과 |
| C-5 | 계층 베이지안 | Todo | C-2~C-4 중 하나라도 신호를 보일 때만 검토 | — | — |
| P3-5 | `dong_prediction` 스키마 확장 (nowcast 행, `prob_above_seoul`, δ 구간, `mu_ref`, `insufficient_reason`) 후 적재 | Todo | 프론트 payload 스키마 합의 후 migration 반영, 정선우 님 확인 | migration, `docs/payload-schema.md` | Phase 3 게이트 결과 |

### Phase 4 — Track I 구간과 gate

| ID | 작업 | 상태 | 완료 조건 | 산출물 | 의존 |
|---|---|---|---|---|---|
| I-1 | split conformal + SE 큰 동 구간 가산 확대. nominal 80% 선언 | Todo | empirical coverage를 전체/국면/표본수/SE/gate별로 분해한 표와 평균 구간 폭 | `models/index/68.build_intervals.py`, `docs/model-performance.md` | C 게이트, N-3 |
| G-1 | gate 임계값(τ_ci, n_min, τ_dom) 3차원 trade-off 곡선으로 결정 | Todo | 곡선 그림과 채택 값이 결정 기록에 있음. "4분기 20건" 단일 기준 대체 | 68 옵션, `docs/decisions.md` | I-1, P0-5 |
| I-2 | (조건부) adaptive conformal | Todo | I-1 coverage가 국면별로 크게 흔들릴 때만 | — | I-1 |

### Phase 5 — 지속 운영

| ID | 작업 | 상태 | 완료 조건 | 산출물 | 의존 |
|---|---|---|---|---|---|
| M-1 | 2025Q4 이후 origin의 current regime monitoring (nowcast·3/6개월만) | Todo | 분기마다 갱신되는 표 | `docs/model-performance.md` 별도 절 | Phase 2 |
| M-2 | 한국부동산원 지수와 정기 대사 | Todo | 분기 1회 비교 기록 | 같은 문서 | T0-A |

### 데이터 부채 (Phase와 별도, 우선순위 순)

| ID | 작업 | 상태 | 완료 조건 | 의존 |
|---|---|---|---|---|
| D-1 | = P0-2 snapshot 적재 | Done | (P0-2 참고) | — |
| D-2 | ECOS API 키 확보, 주담대 금리 `observed_at` 포함 적재 | Todo | `docs/data-sources.md`에 확인 방법 기록 | — |
| D-3 | 정비사업 인가일 이벤트 수집 (생존 편향 해소) | Todo | 시계열 테이블과 출처 기록 | — |
| D-4 | 6개 동 키 불일치 매핑 — `bjd_code`로 닫는다(결정 48) | Todo | 지수 동 346개 전부 경계 매칭 | — |

## 5. Phase 게이트

| 게이트 | 통과 조건 | 실패 시 |
|---|---|---|
| Phase 0 → 1 | P0-1, P0-3, P0-4 Done | 진행 불가. SE 없이는 아무것도 못 한다 |
| Phase 1 → 2·3 | T0-A 비교표 작성, 안정성이 수축 전보다 나쁘지 않음 | T0-B로 |
| Phase 2 판정 | N-3 수정폭 MAE 개선 신뢰구간이 0 제외 | N-2로. 헤드라인 ① 보류 |
| **Phase 3 판정** | C-2 이상 후보가 C-0·C-1 모두를 DM p<0.05로 이기고 C-diag 통과 | **δ 비공개.** 제품은 nowcast + 신뢰도 블록 + 구조 정보로 확정. 이것도 실패가 아니라 방향 결정이다 |
| Phase 4 판정 | 80% nominal에서 empirical coverage 75% 이상, 평균 구간 폭이 거래비용(±수%) 이내 | 구간 재설계. 화면에 "실험적" 라벨 |

## 6. 완료 기록

| 날짜 | 작업 ID | 산출물 | 결정 번호 | 메모 |
|---|---|---|---|---|
| 2026-09-17 | P0-3 | `docs/decisions.md` 결정 41 | 41 | 기존 44·48 코드에 누수 없음을 확인했다. 결정 39의 관찰은 실제 결과다 |
| 2026-09-17 | T0-A | `models/index/63.shrink_dong_index.py`, `output/63.1`·`63.2`, `docs/model-performance.md` R2 | 45, 46 | 현행 λ=5가 반쪽 나누기 최적(6.5) 대비 0.27%만 나빠 유지한다. 사후 shrinkage로 얻을 것이 없다. Track 0의 성과는 SE 컬럼이다 |
| 2026-09-17 | P0-2 | `data/collect/61.snapshot_trades.py`, `_trades_api.py`, `output/raw/snapshot/2026-09-17/` | — | 첫 조회일 적재 완료(매매·전월세 6개월 × 25개 구, 4MB). 재실행 시 건너뛰는 것 확인. **매일 돌려야 한다** — `models/AGENTS.md`에 적었다 |
| 2026-09-17 | P0-5 | `models/index/62.build_dong_features.py`, `output/62.1` | — | 현행 gate(4분기 20건) 통과 행의 24.1%가 한 단지 거래 비중 50% 초과다. 거래 단지 수 하위 10%는 3개뿐이다. G-1이 단일 기준을 바꿀 근거다. DB 컬럼 추가는 feature 빌더가 완성되는 C-3b에서 한다 |
| 2026-09-17 | P0-4 | `models/index/64.measure_mu_weight.py` | 43, 47, 48 | 세대수 기준 커버리지 99.3%로 재고가중 채택. 매매 기록으로 95.6%, `bjd_code` 사전이 3.7%를 더 붙인다. 남은 188개 단지는 `bjd_code`가 비어 있다. (결정 44는 틀려서 47로 대체했다) |
| 2026-09-17 | P0-1 | `models/index/60.build_dong_index_se.py`, `_dong_index_se.py`, `data/db/003_dong_index_se.sql`, `output/60.1` | 42 | τ=0.0585. SE 중앙값은 거래 0건 0.058에서 50건 초과 0.010까지 단조 감소. 적재는 42.1 등 다른 산출물이 로컬에 없어 아직 못 했다 |
