# 판단 보조 제품 작업 계획

> 목적: 동별 상승률 예측 중심 기획을 판단 보조 제품 기획으로 전환하고, 필요한 문서와 구현 작업을 단계별로 관리한다.
> 2026-09-17 개정. `investment-support-plan.md`와 `model-candidates.md` 개정에 맞춰 Phase 구성을 다시 짰다. 바뀐 점은 §7에 있다.

## 1. 운용 규칙

- 상태는 `Todo` / `Doing` / `Done`만 쓴다.
- 기획 문서는 `docs/`에서 관리하며, 초안이 확정되면 별도 임시 디렉터리를 남기지 않는다.
- 기존 제품·모델 결정과 충돌하는 내용은 `docs/decisions.md`에 새 결정으로 옮긴 뒤 본 문서를 갱신한다.
- 화면 문구는 기존 금지 표현 규칙에 `investment-support-plan.md` §5의 추가 금지 목록을 더해 따른다.
- 산출물은 수익률 예측이 아니라 표본 상태, 관측 수치, 비교군으로 표현한다. **과거 변화율에 라벨을 붙이지 않는다.**
- 1차에 학습하는 모델은 없다. 집계와 문턱 판정만 만든다. 학습 모델을 다시 넣으려면 결정 문서를 먼저 고친다.

## 2. 문서 작업 목록

| ID | 문서 | 상태 | 목적 | 완료 조건 |
|---|---|---|---|---|
| D-1 | `docs/README.md` | Done | 새 기획의 배경, 기존 문서에서 가져온 전제, 문서 목록 | 2026-09-17 통합 완료 |
| D-2 | `docs/investment-support-plan.md` | Done | 제품 방향, 화면 정보 구조, 표현 규칙, 성공 기준 | 2026-09-17 통합 완료 |
| D-3 | `docs/model-candidates.md` | Done | 1차·2차 산출물 정의와 검증 기준 | 2026-09-17 통합 완료 |
| D-4 | `docs/process.md` | Done | 문서·구현 작업 계획 관리 | 상태표와 Phase 게이트가 있음 |
| D-5 | `docs/feature-spec.md` | Done | 산출물 4개의 산식, 결측 처리, 문턱 판정 규칙 | §2.1의 완료 조건 충족. F-4 경계 사례 중 자치구 쏠림 예시만 69 첫 실행 뒤 추가 |
| D-6 | `docs/payload-schema.md` | Done | 새 산출물을 프론트 API에 실을 현행 payload 계약 | 목록·상세 응답 예시와 `status` 대체안이 있음 |
| ~~D-7~~ | ~~`evaluation-protocol.md`~~ | 삭제 | 검증은 `feature-spec.md` 경계 사례·`test_69.py`·`check-wording.mjs`로 한다. 결정 70 | — |
| D-8 | `docs/wording-guide.md` | Done | 화면 문구 가이드와 `check-wording.mjs` 추가 목록 | 금지 표현과 허용 문구가 산출물별로 있음 |
| D-9 | `docs/decisions.md` | Done | 결정 59~70을 정식 기록으로 이관 | 2026-09-17 통합 완료 |

### 2.1 D-5 `feature-spec.md` 작성 계획

#### 역할

`models/index/69`를 짜기 전에 산식을 글로 먼저 고정하는 문서다. 스크립트는 이 문서를 코드로 옮긴 것이어야 하고, `payload-schema.md`는 이 문서의 값 이름을 그대로 쓴다. 산식이 바뀌면 코드가 아니라 이 문서를 먼저 고친다.

**작성 완료(2026-09-17).** 아래 계획은 작성 당시의 요구사항이고, 실제 내용과 정한 값은 `feature-spec.md`에 있다. 둘이 어긋나면 `feature-spec.md`가 맞다.

#### 공통 규칙 (문서 첫 절에 적는다)

| 항목 | 규칙 |
|---|---|
| 기준 분기 T | `dong_index`의 최신 분기 하나. 네 산출물이 같은 T와 같은 `snapshot_id`를 쓴다 |
| 값 이름 | payload 필드명과 같게 snake_case. 여기서 정한 이름을 `payload-schema.md`가 바꾸지 않는다 |
| 결측 | "값 없음"과 "0"을 구분한다. 매매 0건은 0, 지수 없음은 결측이다 |
| 문턱 | 이미 결정에 있는 값을 재사용한다. 새 문턱은 분포 집계 근거와 `docs/decisions.md` 항목 없이는 넣지 않는다 |
| 화면 단위 | log 차이는 `(exp(x) − 1) × 100`으로 %로 바꾼다. 문서 안 산식은 log 그대로 쓴다 |

산출물마다 다음 일곱 항목을 같은 순서로 적는다. 하나라도 비면 그 산출물은 미완이다.

1. 정의 — 한 문장. 무엇을 알려 주는 값인지
2. 입력 — 테이블·컬럼 또는 `output/` 파일과 컬럼
3. 산식 — 수식 또는 의사코드
4. 결측·경계 처리 — 입력이 없을 때, 0일 때, 분모가 0일 때
5. 문턱과 근거 — 값과 그 값이 나온 결정 번호 또는 집계
6. 경계 사례 — 판정이 갈리는 실제 동 3개 이상. 동 이름과 수치
7. 테스트 기준 — `models/index/test_69.py`로 옮길 수 있는 문장

#### F-1 표본 주의 flag

| 항목 | 내용 |
|---|---|
| 입력 | `dong_feature.sale_n_all_4q`(T), `output/62.1`의 `n_complexes_4q`·`dominant_complex_share_4q`(T), `dong_index.log_index_se`(T) |
| 산식 | `FEW_SALES` = `sale_n_all_4q` < 20. `ONE_COMPLEX_DOMINATES` = `dominant_complex_share_4q` > 0.5. `HIGH_INDEX_ERROR` = `log_index_se` ≥ 경계값 |
| 결측 | 매매 0건이면 비중이 결측이므로 `ONE_COMPLEX_DOMINATES`는 판정하지 않는다. `FEW_SALES`가 잡는다. `log_index_se` 결측은 지수가 없는 동이라 산출물 전체를 내지 않는다 |
| 문서에서 정할 것 | `HIGH_INDEX_ERROR` 경계값. eligible 동의 SE 분포 상위 구간으로 P1-2에서 집계한다. `output/62.1`의 `sale_n_all_4q`가 `dong_feature`의 값과 같은지 대조한다. 두 스크립트가 따로 세므로 어긋날 수 있다 |
| 경계 사례 | 매매 19·20·21건 동, 비중이 0.5 정확히인 동, 매매 1건에 단지 1개인 동 |
| 테스트 | 경계값 세 쌍이 문서 판정과 같다. 매매 0건 동에 `ONE_COMPLEX_DOMINATES`가 없다. `models/index/62`의 자체 검증(원장에서 다시 세어 대조)을 재사용한다 |

#### F-2 12개월 변화 표시

| 항목 | 내용 |
|---|---|
| 입력 | `dong_index.log_index`·`log_index_se`(T, T−4), 동별 세대수 `models/index/_dong_weight.dong_households` |
| 산식 | `change_12m` = `log_index[T]` − `log_index[T−4]`. `mu_12m` = 세대수 가중 평균(`change_12m`), 두 분기 모두 있는 동만(결정 43). `delta_12m` = `change_12m` − `mu_12m`. `delta_se` = √(`se[T]`² + `se[T−4]`²). `delta_state` = `DISTINGUISHABLE` if \|`delta_12m`\| > 2 × `delta_se` else `INDISTINGUISHABLE`. `peak_5y_gap` = `log_index[T]` − max(`log_index[T−19..T]`), `peak_5y_gap_se` = √(`se[T]`² + `se[peak]`²) |
| 결측 | T−4 지수가 없으면 변화를 내지 않고 μ 계산에서도 뺀다. 세대수가 없는 동은 μ에서 빼되 δ는 계산한다. 5년 창에 지수가 20분기 미만이면 `peak_5y_gap`을 내지 않는다 |
| 문서에서 정할 것 | 2σ 문턱을 유지할지. P1-3에서 `DISTINGUISHABLE` 동 수를 세고 0% 또는 100% 근처면 다시 정한다. μ 자체의 오차는 무시하고 각주로 적을지. 잡음 큰 계열의 최댓값은 위로 치우치므로 `FEW_SALES`·`HIGH_INDEX_ERROR` 동에 `peak_5y_gap`을 낼지, 낸다면 오차를 어떻게 키울지 |
| 경계 사례 | \|δ\|가 2σ 바로 위·아래인 동, 비eligible인데 `DISTINGUISHABLE`인 동(있으면 SE 정의 점검 대상) |
| 테스트 | δ의 세대수 가중합이 0에 가깝다. `delta_se`가 두 SE 중 큰 쪽보다 크다. `_dong_weight`로 만든 μ와 손으로 계산한 가중 평균이 같다 |

`delta_se`는 `model-candidates.md` §4의 √2 × SE를 두 시점 SE가 다를 때로 일반화한 것이다. 두 SE가 같으면 같은 값이다.

#### F-3 구조 유형

| 항목 | 내용 |
|---|---|
| 입력 | `output/66.1.dong_cluster.txt` 최신 `as_of`, `output/66.3.cluster_profile.txt`, K-S 행렬 8변수(`log_ppm2`, `jeonse_ratio`, `log_stock`, `new_share`, `lat`, `lng`, `dist_cbd`, `dist_gangnam`, `models/index/66`의 `build_matrix`) |
| 산식 | `structure_type` = 최신 기점 `cluster`. `structure_desc` = 클러스터 중앙값이 서울 중앙값에서 표준화 편차 절대값으로 가장 멀리 벗어난 변수 2개를 문구로. `lat`·`lng`는 설명 후보에서 뺀다(거리 변수가 대신한다). 변수→문구 사전은 `wording-guide.md`에 둔다 |
| 결측 | `66.1`에 없는 동(행렬 결측으로 빠진 동)은 `structure_type` 없음. 함께 볼 동도 없음 |
| 문서에서 정할 것 | `66.3`에는 5개 변수만 있어 8변수 프로필을 다시 계산할지. k-means 라벨 번호는 재실행 때 바뀔 수 있으므로 `66.1` 파일을 정본으로 삼고, 재실행 시 이전 소속과 ARI 최대 매칭으로 번호를 잇는 규칙 |
| 경계 사례 | 크기 4 클러스터의 동 4개. 두 클러스터 경계에 있는 동(최근접 중심 거리 차가 작은 동) |
| 테스트 | 4개 클러스터 설명이 `66.3` 수치와 맞는지 수동 확인. 같은 동의 소속이 `66.1` 최신 행과 같다 |

#### F-4 함께 볼 동

| 항목 | 내용 |
|---|---|
| 입력 | F-3의 소속, K-S 표준화 행렬(같은 `StandardScaler`) |
| 산식 | 같은 `cluster` 안에서 8변수 유클리드 거리 최근접 5개, 자기 자신 제외. `reason` = 거리 기여가 가장 작은 변수 2개를 문구로 |
| 표시 조건 | 관심 동이 eligible, 클러스터 크기 ≥ 10. 아니면 `peer_dongs`를 빈 배열이 아니라 결측으로 낸다. 화면은 블록을 숨긴다 |
| 결측 | 후보가 5개 미만이면 있는 만큼만 |
| 문서에서 정할 것 | 후보를 eligible 동으로 제한할지. `lat`·`lng`를 거리에 넣으면 같은 자치구로 쏠린다. Phase 2 게이트 실패 시 첫 조정은 `lat`·`lng` 제외로 정해 둔다 |
| 경계 사례 | 클러스터 크기 10 근처 동, 후보 5개 중 4개가 같은 자치구인 동 |
| 테스트 | 자기 자신이 없다. 관계는 대칭이 아니어도 된다고 명시한다. 크기 4 클러스터 동은 결측이다 |

#### 산출 파일

`output/69.1.dong_support.txt` 한 파일. 네 산출물이 같은 T를 쓰므로 나누지 않는다.

| 컬럼 | 출처 |
|---|---|
| `dong`, `as_of` | 공통 |
| `sale_n_all_4q`, `n_complexes_4q`, `dominant_complex_share_4q`, `index_se`, `sample_flags` | F-1 |
| `change_12m`, `mu_12m`, `delta_12m`, `delta_se`, `delta_state`, `peak_5y_gap`, `peak_5y_gap_se` | F-2 |
| `structure_type`, `structure_desc` | F-3 |
| `peer_dongs` (JSON 문자열) | F-4 |

컬럼 이름이 곧 payload 필드명이다. 바꾸면 `payload-schema.md`도 같이 바꾼다.

#### 작성 순서

1. 공통 규칙과 일곱 항목 틀
2. F-1, F-2 초안. 문턱은 비워 둔다
3. P1-2(SE 경계), P1-3(`DISTINGUISHABLE` 동 수) 집계를 돌리고 문턱을 채운다
4. F-3, F-4. `66.3` 재계산 여부를 먼저 정한다
5. 산출 파일 컬럼 확정, `payload-schema.md`에 넘긴다

#### 완료 조건

- 산출물 4개 모두 일곱 항목이 채워져 있다
- "문서에서 정할 것" 여섯 개(SE 경계, 2σ 유지, 저거래 동의 `peak_5y_gap` 처리, `66.3` 재계산, 라벨 번호 잇기, 후보 eligible 제한)에 답과 근거가 있다
- 경계 사례가 실제 동 이름과 수치로 적혀 있다
- 테스트 기준을 `models/index/test_69.py`로 옮길 때 문장을 다시 해석할 필요가 없다
- `model-candidates.md` §3~§6과 어긋나는 곳이 없다. 어긋나면 이 문서가 아니라 `model-candidates.md`를 고친다

## 3. 구현 작업 계획

### Phase 0 — 전환 합의

| ID | 작업 | 상태 | 산출물 | 의존 |
|---|---|---|---|---|
| P0-1 | 기존 상승률 예측 실패 결론을 새 기획의 전제로 고정 | Done | `README.md` §1~2 | `docs/decisions.md` 51·55·57·58 |
| P0-2 | 하지 않는 것 정의 | Done | `README.md` §6, `investment-support-plan.md` §5 | P0-1 |
| P0-3 | 초안 비판 검토와 개정 | Done | `investment-support-plan.md` §9, `model-candidates.md` §8 | P0-2 |
| P0-4 | `README.md` §1·§4·§6을 개정판에 맞춤 | Done | `README.md` | P0-3 |
| P0-5 | 새 방향을 공식 결정으로 정리 | Done | `docs/decisions.md` 59~70 | P0-4 |
| P0-6 | 결정 59~70을 `docs/decisions.md`로 이관 | Done | `docs/decisions.md` | P0-5 |

### Phase 1 — 표본 상태와 변화 표시

1차 화면의 뼈대다. 이 둘이 없으면 나머지 블록을 낼 수 없다.

| ID | 작업 | 상태 | 산출물 | 의존 |
|---|---|---|---|---|
| P1-1 | 표본 주의 flag 3개 판정 규칙 확정 | Done | `feature-spec.md` §1 | `output/62.1`, 결정 7·42 |
| P1-2 | `HIGH_INDEX_ERROR`의 SE 구간 경계를 분포로 확인 | Done | `feature-spec.md` §1.5. 경계 0.032 | `dong_index.log_index_se` |
| P1-3 | δ 오차 문턱(2σ)에서 `DISTINGUISHABLE` 동 수 집계 | Done | `feature-spec.md` §2.5. 137/346 | μ는 등가중 근사. 세대수 가중은 69에서 |
| P1-4 | 산출 스크립트 작성 | Todo | `models/index/69`, `output/69.1` | `feature-spec.md` §6 |
| P1-5 | 경계 사례 표를 `test_69.py`로 옮기고 통과 확인 | Todo | `models/index/test_69.py` | P1-4 |

### Phase 2 — 구조 유형과 함께 볼 동

| ID | 작업 | 상태 | 산출물 | 의존 |
|---|---|---|---|---|
| P2-1 | K-S 최신 기점 소속을 화면용 구조 유형으로 정리 | Done | `feature-spec.md` §3 | `output/66.1`, 결정 57 |
| P2-2 | 프로필 자동 설명 규칙 작성 | Done | `feature-spec.md` §3.3, `wording-guide.md` §4 | `output/66.3` |
| P2-3 | 같은 클러스터 안 최근접 5개 산출 | Todo | `models/index/69` | P1-4 |
| P2-4 | 같은 자치구 쏠림 보고와 F-4 경계 사례 추가 | Todo | `feature-spec.md` §4.6 | P2-3. 69 첫 실행 출력 |

### Phase 3 — payload와 화면

| ID | 작업 | 상태 | 산출물 | 의존 |
|---|---|---|---|---|
| P3-1 | 목록 payload v2 작성 | Done | `payload-schema.md` §3 | — |
| P3-2 | 상세 payload v2 작성 | Done | `payload-schema.md` §4 | — |
| P3-3 | `status`와 `dong_prediction` 처리 결정 | Done | `docs/decisions.md` 66 | — |
| P3-4 | `prediction-card`, `status-badge` 교체 범위 확정 | Done | `payload-schema.md` §7 | — |
| P3-5 | `check-wording.mjs`에 추가 금지어 반영 | Todo | `front/scripts/check-wording.mjs` | `wording-guide.md` §2.2 |
| P3-6 | `app.dong_support` DDL과 `50.load_db.py --kind support` | Todo | `data/db/` | P1-4 |
| P3-7 | API `queries.ts`를 `dong_support`로 교체, `flows` 집계 추가 | Todo | `front/lib/queries.ts` | P3-6 |
| P3-8 | 화면 컴포넌트 교체 (`payload-schema.md` §7 목록) | Todo | `front/components/dong/` | P3-7, P3-5 |
| P3-9 | 샘플 JSON v2 갱신 | Todo | `front/public/data/` | P3-2 |
| P3-10 | build 검증 `npx tsc --noEmit && npm run build && npm run check:wording` | Todo | — | P3-8, P3-9 |

### Phase 4 — 사용자 검증 (MVP 배포 뒤)

MVP 최우선 결정(2026-09-17, 결정 70)으로 Phase 3 뒤로 미룬다. 산출물 문서는 그때 정한다.

| ID | 작업 | 상태 | 산출물 | 의존 |
|---|---|---|---|---|
| P4-1 | 인터뷰 질문지 작성 | Todo | 미정 | `investment-support-plan.md` §2.1·§7 |
| P4-2 | 인터뷰 담당자와 일정 확정 | Todo | — | P4-1 |
| P4-3 | 인터뷰 5명 진행과 기록 | Todo | 미정 | Phase 3, P4-2 |
| P4-4 | 성공 기준 4개 판정 | Todo | `docs/decisions.md` | P4-3 |

### Phase 5 — 2차 후보 (게이트 통과 후)

| ID | 작업 | 상태 | 산출물 | 의존 |
|---|---|---|---|---|
| P5-1 | 이벤트 전후 경로 오차 띠 설계 | Todo | `model-candidates.md` §7.1 | Phase 4 통과 |
| P5-2 | leave-one-complex-out 변화율 | Todo | `model-candidates.md` §7.2 | Phase 4 통과 |
| P5-3 | 면적대 구성 변화 분포 확인 | Todo | `model-candidates.md` §7.3 | Phase 4 통과 |

## 4. Phase 게이트

| 게이트 | 통과 조건 | 실패 시 |
|---|---|---|
| Phase 0 → 1 | 예측 헤드라인 제거와 라벨 금지를 팀이 동의 | 기존 예측 화면과 새 화면이 충돌하므로 payload 작업 보류 |
| Phase 1 → 2 | `test_69.py` 통과. `feature-spec.md` §1.6·§2.6 경계 사례가 세대수 가중 μ에서도 유지됨. `DISTINGUISHABLE` 비율이 0%나 100%에 붙지 않음 (2026Q2 39.6%로 확인) | 문턱을 다시 정한다. 그래도 안 되면 δ 수치를 아예 내지 않고 동 변화율만 낸다 |
| Phase 2 → 3 | 69 첫 실행 보고에서 5개 중 4개 이상 같은 자치구인 동이 절반 미만. 자동 설명 4개가 프로필 수치와 맞음 | `lat`·`lng`를 거리에서 뺀다. 그래도 안 되면 구조 유형만 내고 함께 볼 동 블록을 뺀다 |
| Phase 3 → MVP | `npx tsc --noEmit && npm run build` 통과, `npm run check:wording` 0건(추가 금지어 포함), `dev` merge | 문구·타입을 고친다 |
| Phase 4 → 5 | `investment-support-plan.md` §7 기준 4개 통과 | **화면을 더 만들지 않는다.** §2 가설로 돌아가 제품 방향을 다시 본다 |

Phase 4를 통과하지 못했는데 Phase 5로 넘어가지 않는다. 기능을 더 붙여서 통과하는 것은 통과가 아니다.

## 5. 우선 실행 순서

문서는 전부 있다. 남은 것은 구현이다.

1. `models/index/69` + `test_69.py` (P1-4, P1-5, P2-3). 첫 실행 보고로 F-4 경계 사례를 채운다 (P2-4).
2. `check-wording.mjs` 금지어 추가 (P3-5). 코드 교체 전에 넣어야 교체 중 걸리는 문구가 보인다.
3. `dong_support` DDL과 적재 (P3-6).
4. API·타입·컴포넌트 교체 (P3-7~P3-9).
5. build 검증과 `dev` merge (P3-10).

## 6. 남은 결정

초안의 질문 다섯 개 중 셋은 개정에서 답했다.

| 질문 | 답 | 근거 |
|---|---|---|
| 12개월 추정 변화율을 완전히 제외할 것인가 | 동별 예측값은 제외. μ는 "예측 아님" 표기로 접어서 남긴다 | 결정 53, `investment-support-plan.md` §3 |
| 신뢰도 등급을 A~D로 할 것인가 3단계로 할 것인가 | 둘 다 아니다. 주의 flag 3개 | `model-candidates.md` §8-1 |
| 클러스터 이름을 사람이 붙일 것인가 | 아니다. 프로필 상위값 자동 설명 | `model-candidates.md` §5 |
| 전세 구조 점수와 이벤트 민감도를 MVP에 넣을 것인가 | 넣지 않는다. 라벨은 만들지 않고 이벤트는 경로 그래프로 2차 | `model-candidates.md` §8-4·8-5 |

`status`와 `dong_prediction` 처리는 결정 66에서 답했다.

남은 결정 두 개:

1. **함께 볼 동을 같은 가격대 안에서만 고를 것인가.** 1차는 같은 클러스터 안 최근접만. 가격대 위 후보는 2차 검토, 아래 후보는 넣지 않는 쪽으로 기운다(`investment-support-plan.md` §8-1).
2. **인터뷰를 누가 언제 하는가.** MVP 배포 뒤 P4-2에서 정한다.

## 7. 2026-09-17 개정 내용

| 이전 | 이후 | 이유 |
|---|---|---|
| Phase 1 "신뢰도와 왜곡 감지" | Phase 1 "표본 상태와 변화 표시" | 신뢰도 등급과 "왜곡"이라는 이름을 뺐다. δ 표시 규칙이 1차 뼈대로 올라왔다 |
| Phase 2 "국면 분류와 비슷한 동" | Phase 2 "구조 유형과 함께 볼 동" | 국면 라벨을 삭제했다. 결정 55~58이 닫은 모멘텀의 재포장이다 |
| Phase 3 "보조 설명 모델" (전세 구조 점수, 이벤트 민감도) | 삭제. 일부는 Phase 5로 | 해석 라벨은 투자 조언으로 읽힌다. 이벤트 반응은 저거래 동에서 잡음에 묻힌다 |
| 사용자 검증 단계 없음 | Phase 4 신설 | 1차 버전의 목적이 기능 완성이 아니라 제품 방향 확인이기 때문 |
| 게이트 실패 시 "산식 단순화", "라벨 이름을 낮춤" | 실패 시 그 블록을 빼는 선택지를 명시 | 통과할 때까지 설계를 바꾸면 그 통과는 의미가 없다 (결정 49의 같은 규칙) |
| 산출 스크립트 `69.*` 후보 여러 개 | `models/index/69` 하나 | 네 산출물이 같은 입력과 기점 기준을 쓴다 |
| D-7 `evaluation-protocol.md` 예정 | 삭제 (같은 날 2차) | MVP 최우선. 산출물 검증 항목은 `feature-spec.md`에 산출물별로 이미 있고, 인터뷰는 화면이 있어야 가능하므로 Phase 4를 MVP 뒤로 옮겼다. 결정 70 |
| D-5·D-6·D-8·D-9 Todo | Done (같은 날 2차) | 네 문서 작성. feature-spec의 문턱과 경계 사례는 `output/60.1`·`62.1`·`66.1`·`66.3` 2026Q2 집계로 채웠다 |
| Phase 3에 구현 작업 없음 | P3-6~P3-10 추가 | payload v2가 정해져 DB·API·화면·검증 작업을 나열할 수 있게 됐다 |
