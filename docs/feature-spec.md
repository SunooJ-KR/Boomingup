# 판단 보조 1차 산출물 산식

> 작성 2026-09-17. `process.md` §2.1의 작성 계획을 따른다. `models/index/69`는 이 문서를 코드로 옮긴 것이어야 한다. 산식이 바뀌면 코드가 아니라 이 문서를 먼저 고친다.
> 경계 사례와 문턱 근거의 수치는 `output/60.1`, `62.1`, `66.1`, `66.3`을 2026Q2 기준으로 집계한 값이다. 집계 스크립트는 `models/index/69`의 자체 검증에 그대로 옮긴다.

## 0. 공통 규칙

| 항목 | 규칙 |
|---|---|
| 기준 분기 T | `dong_index`의 최신 분기. 2026-09-17 현재 2026Q2. 네 산출물이 같은 T와 같은 `snapshot_id`를 쓴다 |
| 대상 동 | T에 `dong_index` 행이 있는 동 346개 |
| 값 이름 | 아래 표의 컬럼명이 곧 payload 필드명이다. `payload-schema.md`는 이름을 바꾸지 않는다 |
| 결측 | "값 없음"과 "0"을 구분한다. 매매 0건은 0, 지수 없음은 결측(빈 칸)이다 |
| 문턱 | 결정 7(매매 20건)과 `models/index/62`(단지 비중 0.5)를 재사용한다. 새로 정한 문턱은 SE 경계 하나뿐이고 근거는 §1.5에 있다 |
| 화면 단위 | log 차이 x는 `(exp(x) − 1) × 100`으로 %로 바꾼다. 문서 안 산식은 log 그대로다 |
| eligible | `dong_index.eligible` = 직전 4분기 취소 제외 매매 20건 이상(결정 7) |

산출물마다 정의, 입력, 산식, 결측·경계, 문턱과 근거, 경계 사례, 테스트 순서로 적는다.

## 1. F-1 표본 주의 flag

### 1.1 정의

동의 12개월 변화율을 얼마나 조심해서 읽어야 하는지 알리는 표시. 등급이 아니라 독립된 flag 세 개다.

### 1.2 입력

| 값 | 출처 | 비고 |
|---|---|---|
| `sale_n_all_4q` | `output/62.1.dong_complex_concentration.txt`, `as_of_quarter = T` | `dong_index.n_sales_4q`와 같은 값이다. 2026Q2 346개 동에서 불일치 0건 |
| `n_complexes_4q` | 같은 파일 | 직전 4분기에 거래가 있던 단지 수 |
| `dominant_complex_share_4q` | 같은 파일 | 가장 많이 거래된 단지의 몫. 매매 0건이면 빈 칸 |
| `index_se` | `dong_index.log_index_se`, `quarter = T` | 결정 42 정의(표본 잡음 + 수축 편향). active DB에 컬럼이 아직 없으면 `output/60.1.dong_index_se.txt`를 사용한다 |

### 1.3 산식

```text
FEW_SALES              = sale_n_all_4q < 20
ONE_COMPLEX_DOMINATES  = dominant_complex_share_4q > 0.5      (sale_n_all_4q ≥ 1일 때만 판정)
HIGH_INDEX_ERROR       = index_se ≥ 0.032
sample_flags           = 위 셋 중 참인 것의 목록. 순서는 FEW_SALES, ONE_COMPLEX_DOMINATES, HIGH_INDEX_ERROR
```

`index_se_band`도 함께 낸다. 화면의 "추정오차 구간 3단계"용이다.

```text
index_se < 0.016          → LOW
0.016 ≤ index_se < 0.032  → MID
index_se ≥ 0.032          → HIGH   (= HIGH_INDEX_ERROR)
```

### 1.4 결측·경계

| 상황 | 처리 |
|---|---|
| 매매 0건 (2026Q2 27개 동) | `dominant_complex_share_4q` 빈 칸. `ONE_COMPLEX_DOMINATES` 판정 안 함. `FEW_SALES`가 잡는다 |
| 비중이 정확히 0.5 | 부등호가 `>`이므로 flag 없음. §1.6 |
| `index_se` 빈 칸 | 지수가 없는 동. 산출물 행 자체를 내지 않는다. 2026Q2에는 없다 |
| 단지 1개에서만 거래 | 비중 1.0이라 `ONE_COMPLEX_DOMINATES`. 매매 20건 이상이어도 붙는다 |

### 1.5 문턱과 근거

| 문턱 | 값 | 근거 |
|---|---|---|
| 매매 건수 | 20 | 결정 7. eligible 기준과 같은 값을 쓴다. 2026Q2 100/346개 동이 미만 |
| 단지 비중 | 0.5 | `models/index/62`가 이미 이 값으로 분포를 보고한다. 2026Q2 eligible 246개 중 62개가 초과 |
| SE 경계 | 0.032 | eligible 동 SE의 90분위(0.0324)를 소수 3자리로 내림. 이유는 아래 |

SE 경계를 0.032로 잡은 이유. eligible 동의 SE 분위는 다음과 같다.

| 분위 | 10% | 25% | 50% | 75% | 90% | 95% |
|---|---|---|---|---|---|---|
| SE | 0.0073 | 0.0096 | 0.0158 | 0.0261 | 0.0324 | 0.0364 |

SE 0.032면 12개월 δ 오차(§2.3)가 약 0.045, 2σ 띠가 ±9%다. 2026Q2 동 변화율의 10~90% 폭이 2.8%~22%라 δ 폭도 대략 ±10%다. 즉 이 경계를 넘는 동은 δ가 거의 언제나 "구분되지 않음"이 된다. flag 문장 "작은 변화는 읽지 않는 게 좋아요"가 실제로 맞는 지점이다. 75분위(0.026)로 잡으면 eligible의 25%가 flag를 받아 표시가 흔해진다. 비eligible 100개 중 97개는 이 경계 이상이고 3개는 `MID`다.

`FEW_SALES`지만 `MID`인 세 동은 11290_동소문동5가(17건, SE 0.0306), 11305_우이동(17건, SE 0.0318), 11560_영등포동2가(18건, SE 0.0306)다. 매매 건수와 SE는 서로 다른 주의 신호이므로 flag 산식은 바꾸지 않는다.

`index_se_band`의 아래 경계 0.016은 eligible 중앙값이다. 세 구간이 대략 eligible의 절반 / 40% / 10%로 갈린다.

경계값은 2026Q2 분포로 정한 고정 상수다. 분기마다 다시 계산하지 않는다. 분포가 바뀌면 `docs/decisions.md`에 항목을 만들어 바꾼다.

### 1.6 경계 사례 (2026Q2)

| 동 | 매매 | 단지 수 | 상위 단지 비중 | SE | 판정 |
|---|---|---|---|---|---|
| 11140_묵정동 | 20 | 3 | 0.650 | 0.0306 | eligible 경계. `ONE_COMPLEX_DOMINATES`, `MID` |
| 11710_삼전동 | 19 | 6 | 0.421 | 0.0384 | 한 건 차이로 `FEW_SALES` + `HIGH_INDEX_ERROR` |
| 11200_금호동2가 | 80 | 3 | 0.500 | 0.0285 | 정확히 0.5. flag 없음, `MID` |
| 11200_송정동 | 54 | 6 | 0.500 | 0.0306 | 정확히 0.5. flag 없음, `MID` |
| 11140_충무로5가 | 22 | 3 | 0.545 | 0.0364 | `ONE_COMPLEX_DOMINATES` + `HIGH_INDEX_ERROR` |
| 11200_금호동1가 | 170 | 5 | 0.541 | 0.0146 | 매매가 많아도 `ONE_COMPLEX_DOMINATES`, `LOW` |
| 11110_평동 | 22 | 1 | 1.000 | 0.0346 | 단지 하나. `ONE_COMPLEX_DOMINATES` + `HIGH_INDEX_ERROR` |
| 11170_후암동 | 24 | 6 | 0.625 | 0.0318 | `ONE_COMPLEX_DOMINATES`, SE 경계 바로 아래 `MID` |
| 11170_서빙고동 | 34 | 3 | 0.735 | 0.0331 | `ONE_COMPLEX_DOMINATES`, SE 경계 바로 위 `HIGH_INDEX_ERROR` |

### 1.7 테스트 (`models/index/test_69.py`)

- 위 표의 동 9개에 대해 `sample_flags`와 `index_se_band`가 표와 같다.
- 매매 0건 동 27개에 `ONE_COMPLEX_DOMINATES`가 없다.
- `sale_n_all_4q`와 `dong_index.n_sales_4q`가 모든 동에서 같다.
- `FEW_SALES` 동은 100개이며, 그중 97개가 `HIGH`, 위 세 동이 `MID`다.
- `models/index/62`의 자체 검증(원장에서 단지별로 다시 세어 대조)을 표본 3개 동에 재실행한다.

## 2. F-2 12개월 변화 표시

### 2.1 정의

동의 지난 12개월 지수 변화, 서울 공통 변화(μ), 그 차이(δ)를 오차와 함께 낸다. 차이가 오차보다 작으면 수치 대신 "구분되지 않음"으로 낸다. 최근 5년 최고 지수 대비 현재 위치도 같은 규칙으로 낸다.

### 2.2 입력

| 값 | 출처 |
|---|---|
| `log_index`, `log_index_se` | `dong_index`, `quarter ∈ {T−19, …, T}` |
| 동별 세대수 | `models/index/_dong_weight.dong_households` (결정 43·47의 매핑) |

### 2.3 산식

```text
change_12m   = log_index[T] − log_index[T−4]
mu_12m       = Σ_d w_d · change_12m[d] / Σ_d w_d        (w = 세대수, T와 T−4 둘 다 있는 동만)
delta_12m    = change_12m − mu_12m
delta_se     = sqrt(se[T]² + se[T−4]²)
delta_state  = DISTINGUISHABLE   if |delta_12m| > 2 · delta_se
             = INDISTINGUISHABLE 그 외

peak_q       = argmax_{q ∈ T−19..T} log_index[q]
peak_5y_gap  = log_index[T] − log_index[peak_q]         (항상 ≤ 0)
peak_5y_gap_se = sqrt(se[T]² + se[peak_q]²)
peak_5y_state  = AT_PEAK           if peak_q == T
               = DISTINGUISHABLE   if |peak_5y_gap| > 2 · peak_5y_gap_se
               = INDISTINGUISHABLE 그 외
```

μ의 오차는 무시한다. 346개 동의 가중 평균이라 개별 SE보다 한 자릿수 작다. 화면 각주에 "서울 평균 자체의 오차는 표시하지 않음"을 적는다.

### 2.4 결측·경계

| 상황 | 처리 |
|---|---|
| T−4 지수 없음 | `change_12m` 이하 전부 빈 칸. μ 계산에서도 뺀다. 2026Q2에는 없다(346/346 존재) |
| 세대수 없음 | μ 가중에서 뺀다. δ는 계산한다 |
| 5년 창에 지수가 20분기 미만 | `peak_5y_*` 빈 칸. 2026Q2에는 없다 |
| `FEW_SALES` 또는 `HIGH_INDEX_ERROR` | `peak_5y_gap`, `peak_5y_gap_se` 빈 칸, `peak_5y_state` 빈 칸. §2.5 |
| `delta_state == INDISTINGUISHABLE` | `delta_12m`은 파일에는 남긴다. 화면이 숫자를 내지 않는다(`payload-schema.md`) |

### 2.5 문턱과 근거

**2σ를 유지한다.** 2026Q2에서 `DISTINGUISHABLE`은 137/346(39.6%)이다. eligible 134/246(54%), 비eligible 3/100. 0%도 100%도 아니고, 표본이 많은 동에서 갈리고 적은 동에서 안 갈린다. 규칙이 의도대로 작동한다. μ를 등가중으로 놓으면 0.120, 거래가중이면 0.127인데 두 경우 `DISTINGUISHABLE` 수가 137로 같았다. 세대수 가중은 그 사이에 있을 것이라 결과가 크게 다르지 않는다.

**저거래 동에는 `peak_5y_gap`을 내지 않는다.** 잡음이 큰 계열 20개의 최댓값은 위로 치우친다. SE 0.05인 계열이면 기대 편향이 약 +0.09라 "최고 대비 −9%"가 잡음만으로 생긴다. 실제로 비eligible 100개 동의 92%는 `|gap| < gap_se`이고 43%는 지금이 최고점이다. 낼 정보가 없다. eligible 동도 SE 0.016이면 편향 약 +0.03이 있는데, 이건 오차 병기와 2σ 규칙으로 흡수한다.

참고로 2026Q2는 상승장이라 eligible 동의 50%가 지금이 5년 최고점(`AT_PEAK`)이고, 78%는 `|gap| < 2 · gap_se`다. 즉 대부분의 동에서 이 값은 "5년 최고와 구분되지 않음"으로 나간다. 그래도 넣는 이유는 사용자가 이 값을 확인한다는 것이 `investment-support-plan.md` §2.1의 채택 근거이고, 다른 서비스가 오차 없이 내는 값을 우리는 오차와 함께 내기 때문이다.

### 2.6 경계 사례 (2026Q2, μ 등가중 0.120 기준. 세대수 가중으로 바뀌면 값이 조금 움직인다)

| 동 | 매매 | change | δ | δ 오차 | \|δ\| / 2σ | 판정 |
|---|---|---|---|---|---|---|
| 11290_하월곡동 | 465 | 0.146 | +0.026 | 0.013 | 1.01 | 2σ 바로 위. `DISTINGUISHABLE` |
| 11470_목동 | 856 | 0.103 | −0.017 | 0.009 | 0.99 | 2σ 바로 아래. `INDISTINGUISHABLE` |
| 11305_번동 | 256 | 0.084 | −0.036 | 0.018 | 0.99 | `INDISTINGUISHABLE` |
| 11560_영등포동3가 | 4 | 0.363 | +0.243 | 0.075 | 1.62 | 비eligible인데 `DISTINGUISHABLE`. `FEW_SALES` 문장이 위에 붙는다 |
| 11290_삼선동4가 | 15 | 0.024 | −0.096 | 0.047 | 1.03 | 비eligible `DISTINGUISHABLE` 3개 중 하나 |

5년 최고 대비:

| 동 | 매매 | gap | gap 오차 | 최고 분기 | 판정 |
|---|---|---|---|---|---|
| 11140_황학동 | 225 | −0.069 | 0.019 | 2026Q1 | `DISTINGUISHABLE`. 화면 "5년 최고 대비 −6.7% (오차 ±1.9%)" |
| 11140_중림동 | 29 | −0.112 | 0.055 | 2026Q1 | 원시 판정은 `INDISTINGUISHABLE`. `HIGH_INDEX_ERROR`라 산출물은 빈 칸 |
| 11140_흥인동 | 29 | −0.068 | 0.060 | 2021Q4 | 원시 판정은 `INDISTINGUISHABLE`. `HIGH_INDEX_ERROR`라 산출물은 빈 칸 |
| 11110_효제동 | 8 | −0.082 | 0.075 | 2025Q4 | `FEW_SALES`라 빈 칸 |

### 2.7 테스트

- Σ w_d · delta_12m[d] = 0 (세대수 가중합, 허용 오차 1e-9).
- 모든 동에서 `delta_se ≥ max(se[T], se[T−4])`.
- `_dong_weight`로 만든 μ와 같은 가중치로 손계산한 가중 평균이 같다.
- `peak_5y_gap ≤ 0`이고 `peak_q == T`이면 정확히 0이며 `AT_PEAK`.
- `FEW_SALES` 또는 `HIGH_INDEX_ERROR`인 동은 `peak_5y_*`가 전부 빈 칸.
- 위 경계 사례 9개 동의 `delta_state`, `peak_5y_state`가 표와 같다 (μ를 세대수 가중으로 바꾼 뒤 |δ|/2σ가 0.95~1.05인 동은 다시 확인한다).
- `DISTINGUISHABLE` 비율이 eligible에서 비eligible보다 높다.

## 3. F-3 구조 유형

### 3.1 정의

동이 속한 K-S 클러스터(결정 57, K=4)와 그 클러스터를 서울 전체와 구분해 주는 변수 두 개의 자동 설명.

### 3.2 입력

| 값 | 출처 |
|---|---|
| `cluster` | `output/66.1.dong_cluster.txt`, `as_of` 최댓값(2026Q2). 346개 동 전부 있다 |
| 구조 변수 8개 | `models/index/66`의 `feature_matrix`를 import해 T 한 기점만 만든다. `log_ppm2`, `jeonse_ratio`, `log_stock`, `new_share`, `lat`, `lng`, `dist_cbd`, `dist_gangnam` |

`output/66.3.cluster_profile.txt`는 변수 5개만 있고 서울 중앙값이 없어 설명 생성에는 쓰지 않는다. 보고용으로 둔다. 8변수 프로필은 69가 위 행렬로 다시 계산한다.

### 3.3 산식

```text
structure_type = cluster                              (66.1 최신 기점 값 그대로)

설명 후보 변수 = {log_ppm2, jeonse_ratio, log_stock, new_share, dist_cbd, dist_gangnam}   (lat, lng 제외)
z[c, v] = (median_{d∈c} x[d, v] − median_{all d} x[d, v]) / sd_{all d} x[·, v]
structure_desc = |z[c, v]|가 큰 순서로 변수 2개를 골라 wording-guide.md §4의 사전으로 문구화. " · "로 잇는다
```

k-means를 다시 돌리지 않는다. `66.1`이 정본이다. `66`을 재실행해 번호가 바뀌면, 이전 `66.1`과 새 결과의 혼동행렬에서 겹침이 최대가 되게 번호를 다시 붙인 뒤 `66.1`을 덮어쓴다. 69는 그 규칙을 모른다.

### 3.4 결측·경계

| 상황 | 처리 |
|---|---|
| `66.1`에 없는 동 | `structure_type`, `structure_desc` 빈 칸. F-4도 빈 칸. 2026Q2에는 0개 |
| 구조 변수 결측 | `feature_matrix`가 같은 구 중앙값으로 채운다. 경계 중심점이 없어 못 채운 동은 위와 같이 처리 |
| 두 변수의 \|z\|가 같음 | 후보 변수 나열 순서(위 집합의 순서)로 앞선 것을 쓴다 |

### 3.5 문턱과 근거

문턱 없음. K=4는 결정 57(인접 기점 ARI 0.903). 설명 변수 2개는 화면 폭 때문이고 `investment-support-plan.md` §5가 정했다.

### 3.6 경계 사례 (2026Q2)

| 클러스터 | 동 수 | eligible | `66.3` 프로필 (평당가 만원 / 전세가율 / 신축비중 / 도심 km / 강남 km) |
|---|---|---|---|
| 0 | 111 | 104 | 2,104 / 0.44 / 0.00 / 7.5 / 6.9 |
| 1 | 98 | 94 | 1,095 / 0.56 / 0.00 / 8.9 / 13.3 |
| 2 | 4 | 1 | 1,489 / 0.61 / 0.28 / 6.1 / 10.5 |
| 3 | 133 | 47 | 1,225 / 0.61 / 0.00 / 2.9 / 9.3 |

- 클러스터 2의 동 4개: 11230_신설동, 11290_동선동1가, 11500_공항동, 11560_영등포동2가. 신축 비중 하나로 갈라진 묶음이다. F-4 표시 조건을 못 채운다.
- 클러스터 3은 133개 중 eligible이 47개뿐이다. 도심 근접 저거래 동이 몰려 있다. F-4 후보를 eligible로 제한하면(§4.5) 이 클러스터의 후보 풀은 47개다.
- 69 첫 실행의 자동 설명을 4개 전부 확인했다: 0 "평당가 높음 · 강남 7km대", 1 "강남 13km대 · 도심 9km대", 2 "신축 비중 높음 · 아파트 세대수 적음", 3 "아파트 세대수 적음 · 도심 3km대".

### 3.7 테스트

- 346개 동 모두 `structure_type`이 `66.1` 2026Q2 행과 같다.
- `structure_desc`에 `lat`, `lng` 유래 문구가 없다.
- 클러스터 4개의 설명이 각각 서로 다르다.
- 클러스터 2의 설명에 "신축"이 들어간다 (z가 압도적).

## 4. F-4 함께 볼 동

### 4.1 정의

관심 동과 같은 구조 유형 안에서 구조 변수 거리가 가장 가까운 eligible 동 5개.

### 4.2 입력

F-3의 `cluster`와 표준화 행렬. 표준화는 `StandardScaler`를 T 기점 346개 동 전체에 적합한다(66과 같은 방식).

### 4.3 산식

```text
후보(d) = {p : cluster[p] == cluster[d], p ≠ d, eligible[p]}
dist(d, p) = sqrt(Σ_v (z[d, v] − z[p, v])²)     v ∈ 8변수
peer_dongs(d) = 후보를 dist 오름차순으로 5개
reason(d, p) = (z[d, v] − z[p, v])²가 가장 작은 변수 2개를 wording-guide.md §5의 사전으로 문구화
```

표시 조건을 못 채우면 `peer_dongs`는 빈 배열이 아니라 빈 칸이다.

```text
표시 조건 = eligible[d]  AND  |{p : cluster[p] == cluster[d], eligible[p]}| ≥ 10
```

### 4.4 결측·경계

| 상황 | 처리 |
|---|---|
| 후보가 5개 미만 (10개 이상 조건은 통과) | 있는 만큼만. 일어나지 않는다 (조건이 10 이상) |
| 관심 동이 비eligible | 빈 칸. 2026Q2 100개 동 |
| 클러스터 eligible 수 < 10 | 빈 칸. 2026Q2 클러스터 2 (eligible 1개) |
| 관계의 비대칭 | 허용. A의 peer에 B가 있어도 B의 peer에 A가 없을 수 있다 |

### 4.5 문턱과 근거

| 항목 | 결정 | 근거 |
|---|---|---|
| 후보를 eligible로 제한 | 한다 | 비교 대상의 사실 정보(변화율, 전세가율)가 표본 부족이면 비교가 성립하지 않는다. 클러스터 3은 133개 중 47개만 남지만 5개 뽑기에 충분하다 |
| 크기 조건 | 같은 클러스터 eligible ≥ 10 | 후보 10개에서 5개를 고르면 절반이라 "가장 가까운"이라는 말이 성립하는 하한이다. `investment-support-plan.md` §4.1 |
| `lat`, `lng` 포함 | 1차는 포함 | 66과 같은 행렬을 쓴다는 원칙. 같은 자치구 쏠림이 확인되면 첫 조정은 두 변수 제외다(Phase 2 게이트) |
| 5개 | 고정 | 화면 폭. `investment-support-plan.md` §4.1 |

### 4.6 경계 사례 (2026Q2)

| 동 | 상황 | 판정 |
|---|---|---|
| 11230_신설동 외 클러스터 2의 4개 동 | 클러스터 eligible 1개 | `peer_dongs` 빈 칸 |
| 11710_삼전동 (매매 19건) | 관심 동이 비eligible | 빈 칸 |
| 11140_묵정동 (매매 20건) | 관심 동 eligible 경계 | 함께 볼 동 5개 표시 |
| 클러스터 3의 eligible 47개 | 후보 풀이 가장 작음 | 5개를 표시하고 같은 자치구 비율 집계에 포함 |

69 첫 실행에서 peer가 표시된 245개 동 중 86개(35.1%)가 5개 중 4개 이상 같은 자치구였다. Phase 2 → 3 게이트의 50% 미만 조건을 통과해 `lat`·`lng`를 유지한다.

| 관심 동 | 같은 자치구 peer | 함께 볼 동 5개 |
|---|---:|---|
| 11170_용산동5가 | 4 | 한강로2가, 한강로3가, 한강로1가, 효창동, 금호동2가 |
| 11170_원효로4가 | 4 | 산천동, 한강로2가, 한강로1가, 이태원동, 용강동 |
| 11170_이태원동 | 4 | 서빙고동, 원효로4가, 한강로1가, 응봉동, 한강로2가 |

### 4.7 테스트

- 모든 동에서 `peer_dongs`에 자기 자신이 없다.
- `peer_dongs`의 모든 동이 같은 `cluster`이고 eligible이다.
- 클러스터 2의 4개 동과 비eligible 100개 동은 `peer_dongs`가 빈 칸이다.
- 표시된 동은 정확히 5개다.
- `reason`의 변수 2개가 실제 거리 기여 하위 2개와 같다 (표본 5개 동 수동 대조).
- 첫 실행 보고: 5개 중 4개 이상 같은 자치구인 동의 수와 비율.

## 5. 산출 파일

`output/69.1.dong_support.txt`, 탭 구분, 346행, T 한 기점.

| 컬럼 | 형식 | 출처 |
|---|---|---|
| `dong`, `as_of` | 문자열 | 공통. `as_of = "2026Q2"` |
| `sale_n_all_4q`, `n_complexes_4q` | 정수 | F-1 |
| `dominant_complex_share_4q` | 실수 또는 빈 칸 | F-1 |
| `index_se` | 실수 | F-1 |
| `index_se_band` | `LOW` / `MID` / `HIGH` | F-1 |
| `sample_flags` | `;`로 이은 문자열. 없으면 빈 칸 | F-1 |
| `change_12m`, `mu_12m`, `delta_12m`, `delta_se` | 실수 (log) | F-2 |
| `delta_state` | `DISTINGUISHABLE` / `INDISTINGUISHABLE` | F-2 |
| `peak_5y_gap`, `peak_5y_gap_se` | 실수 또는 빈 칸 | F-2 |
| `peak_5y_state` | `AT_PEAK` / `DISTINGUISHABLE` / `INDISTINGUISHABLE` / 빈 칸 | F-2 |
| `structure_type` | 정수 0~3 또는 빈 칸 | F-3 |
| `structure_desc` | 문자열 | F-3 |
| `peer_dongs` | JSON 배열 문자열 `[{"dong":"…","reason":"…"}]` 또는 빈 칸 | F-4 |

`mu_12m`은 모든 행에 같은 값이 들어간다. 파일을 한 줄만 읽어도 μ를 알 수 있게 두는 것이다.

DB 적재는 `app.dong_support` 테이블로 한다. 컬럼은 위와 같고 `snapshot_id`를 앞에 붙인다. 적재는 `data/db/50.load_db.py`가 다른 정제 테이블과 같은 snapshot에 함께 넣는다. 원장처럼 `--kind`로 나누지 않는다. 이 결정은 `docs/decisions.md` 결정 66이다.

## 6. 스크립트 `models/index/69.build_dong_support.py` 요구사항

- 입력: DB(`dong_index`, `dong_feature`, 세대수, 경계 중심점) + `output/62.1` + `output/66.1`. 구조 행렬은 `_dong_cluster.feature_matrix`, 세대수는 `_dong_weight.dong_households`를 import한다. active DB에 `log_index_se`가 아직 없으면 `output/60.1`로 폴백한다.
- 출력: `output/69.1.dong_support.txt` 하나.
- 자체 검증: §1.7, §2.7, §3.7, §4.7의 항목을 `assert`로 실행하고, F-4 쏠림 보고를 출력한다. 실패하면 파일을 쓰지 않는다.
- 테스트: `models/index/test_69.py`에 경계 사례 표의 동을 고정값으로 넣는다. μ 가중 방식이 바뀌어 |δ|/2σ가 0.95~1.05인 동의 판정이 뒤집히면 이 문서의 표를 고친다.
- 재현성: DB 조회에 `order by` (결정 46).

## 7. 정한 것 요약

| 미결이었던 것 | 답 | 근거 |
|---|---|---|
| SE 경계 | 0.032 (eligible 90분위), band 하한 0.016 (중앙값) | §1.5 |
| 2σ 유지 | 유지. 39.6% | §2.5 |
| 저거래 동 `peak_5y_gap` | `FEW_SALES` 또는 `HIGH_INDEX_ERROR`면 빈 칸 | §2.5 |
| `66.3` 재계산 | 69가 8변수로 다시 계산. `66.3`은 보고용 | §3.2 |
| 라벨 번호 잇기 | `66.1` 정본. 66 재실행 시 혼동행렬 최대 겹침으로 번호 재부여 | §3.3 |
| 후보 eligible 제한 | 한다. 크기 조건도 eligible 수로 | §4.5 |
