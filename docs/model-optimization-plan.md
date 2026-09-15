# 동별 12개월 변화율 모델 최적화 방법론 (v3.1)

> 상태: v3.1 (2026-09-15). sol 검토 v1(F01~F14, 재설계 필요) → v2 → 검토 v2(N01~N12, 수정 후 착수) → v3 → 검토 v3(K01~K09, P0 없음, 수정 후 착수)를 반영했다.
> **§7 계약 보완이 §1~§6과 충돌하면 §7이 우선한다.**
> **모든 결과는 과거 데이터에 대한 탐색적(retrospective exploratory) 결과다.** 2016~2025 OOT는 공식 평가(결정 16)에서 이미 관찰된 기간이라 독립 확인 구간이 없다.
> 아래 선택 규칙은 사전 등록이 아니라 **구현 전에 고정한 탐색적 선택 규칙**이다(결정 18 이후). 확정 시 결정 20~22로 기록한다(N12).

## 0. 목표와 판단 방식

- 주 대상 h=4(12개월). 참고 h=2·8·12(§4.6)
- 합격/불합격 판정 없음. §4.2 규칙으로 최종 설정(SEL)을 고르고 모든 변형 결과를 보고한다
- 주 지표: **기점 동일 가중 MAE** = 기점별 `mean_{T_t}|ŷ − y|`의 기점 평균. 보조: 행 가중 MAE
- CI는 기점 moving-block bootstrap으로 계산하며 **기술적 민감도**로만 해석한다(선택 후 CI, N07)
- 예측 구간은 선택 기준이 아니다. **경험적 구간**(conformal 보장 없음)의 실측 coverage·폭만 보고한다(N08)

## 1. 현 모델 진단과 데이터 사실

`output/44.1` h=4 분해: 시장 MAE 모델 0.0790 / B2 0.0959, 동 상대 MAE 모델 0.0499 / 0 예측 0.0459, 동 상대 상관 0.11.

- **target revision**(F03, N01): 전체 데이터 지수 target과 t+4 vintage 변화의 |차이|는 공식 h=4 평가 8,610행(2016Q1~2025Q2) 기준 평균 0.0098, 95% 0.0358, 최대 0.2512. 41 전체 eligible 12,403행(2011Q4~2025Q2) 기준 평균 0.0126, 95% 0.0429, 최대 0.4272
- **해제 거래 표시**는 2020년부터만 있다(연 3.4~7.7%). `cancel_share_4q`는 쓰지 않는다
- **거래 신고일·해제 신고일이 없다**(F04). 계약일 기준 근사만 가능하다
- **15억·9억 이상 비중**은 초기 기점 동의 60~85%가 0이다. 쓰지 않는다
- **건축물대장 최신 사용승인일 2025-03-05**. 공급 feature를 쓰지 않는다
- 41 vintage는 2011Q4부터다. 2008Q1 기점 vintage(eligible 201개 동)와 2009Q1 vintage의 target 계산은 가능함을 sol이 확인했다
- 42의 `sale_n_all_4q`는 해제 거래를 포함해 41의 유효 건수와 5,727행이 다르다. 거래량 feature는 유효 매매로 다시 계산한다

## 2. target과 표본

- **발행 시점 가정**: 기점 분기 t 종료 후 2개월. 계약일이 분기 t 이내인 유효 거래를 그때 알려진 거래로 근사한다
- **vintage 지수** `V_u(q)`: 계약 분기 ≤ u인 유효 매매만으로 `_dong_index.estimate_hedonic_index`(λ=5)를 추정한 분기 q 값
- **real-time target**: `y_rt[h][d,t] = V_{t+h}(t+h) − V_{t+h}(t)` = 기점 t+h vintage의 `mom_{h}q`(41과 같은 계산)
- **민감도 target**: `y_full[h][d,t]` = 40 전체 데이터 지수의 t→t+h 변화. "최종 수정 지수 기준 점수"로 부른다
- **포함 동** `E_t` = 기점 t vintage에서 `n_sales_4q ≥ 20`인 동. 서비스 예측 대상
- **target 관측 동** `T_t[h] = {d ∈ E_t : y_rt[h][d,t] 유한}`. **학습·평가는 `T_t`**, 서비스 예측은 `E_t`(N02). `|E_t|`, `|T_t|`, 결측 사유를 저장
- 시장 target `M_rt[h][t] = mean_{T_t}(y_rt)`, 상대 target `r_rt = y_rt − M_rt` (평균 분해는 해석용이며 MAE 성분 합이 전체 MAE와 같지 않다)
- 학습 label gap: 기점 t 모델은 `s + h ≤ t`인 기점 s의 label만 쓴다. label vintage `s + h ≤ t`이므로 t 이후 거래가 들어가지 않는다

### 2.1 고칠 수 없는 한계

- 해제 여부는 현재 값이다. 과거 vintage도 나중에 해제된 거래를 뺀다(2020년 이후 거래의 3~8%). 모든 계약을 포함한 민감도는 마감상 하지 않고 한계로 보고한다(F04)

## 3. 모델

### 3.1 시장 모델 (서울 1행/기점, 기점 2008Q1~)

| ID | 역할 | 정의 |
|---|---|---|
| **M0** | 기준 | `M̂ = S_mom_4q` |
| **M1** | 후보 | `M̂ = S_mom_4q + ridge(z)`, z = [`S_mom_1q − S_mom_4q`, `rate_chg_4q`, `S_sale_vol_chg_4q`] |
| M2 | 민감도(선택 제외) | M1 z + `overheated_share` |
| M3 | 민감도(선택 제외) | M1 z + `policy_net_4q` |

- ridge 보정 target: `M_rt[s] − S_mom_4q[s]`
- **적합 규칙(N03)**: nested CV 없음. **λ = 10 고정**. 절편 포함(penalty 없음). 표준화 평균·표준편차는 기점 t의 학습 행(`s+4 ≤ t`, `s ≥ 2008Q1`)으로만 계산하고, 표준편차 0인 feature는 표준화값 0. 학습 기점 12개 미만이면 M1 = M0
- 행 가중치 없음(기점 1행). λ ∈ {1, 100} 결과는 민감도 부록으로만 보고
- feature 정의:
  - `S_mom_kq` = `mean_{E_t}(mom_kq)` (vintage 모멘텀)
  - `rate_chg_4q` = 분기 말 기준금리의 4분기 변화(43). `rate_level` 금지(결정 15)
  - `S_sale_vol_chg_4q` = log(서울 유효 매매 건수, 계약 분기 t−3..t) − log(같은 값, t−7..t−4)
  - `overheated_share` = 43 `reg_overheated`의 25개 구 평균
  - `policy_net_4q` = `event_dates.tsv`에서 `category=policy`, `effective_date`가 분기 t−3..t에 속하는 이벤트의 `tighten`=+1, `ease`=−1 합(§3.4)

### 3.2 동 상대 모델 (동×기점, feature 기점 2011Q4~)

| ID | 역할 | 정의 |
|---|---|---|
| **R0** | 기준 | `r̂ = 0` |
| **R1** | 후보 | ridge, feature 6개: `mom_1q_rel`, `mom_4q_rel`, `mom_12q_rel`, `price_rank`, `jeonse_ratio_rel`, `sale_vol_chg_rel` |
| **R2** | 후보 | LightGBM L1, R1 6개 + `old30_share_4q`, `median_age_4q`, `jeonse_share_4q`, `rent_n_log_change_4q`, `mom_2q_gu_rel`, `mom_8q_gu_rel` |

- feature 정의 (모두 기점 t, `E_t` 기준):
  - `mom_kq_rel = mom_kq − S_mom_kq`
  - `price_rank` = `sale_ppm2_med_4q`의 `E_t` 안 `rank(method="average", pct=True)`, 결측 0.5
  - `jeonse_ratio_rel = jeonse_ratio_4q − median_{E_t}`, 결측 0
  - `sale_vol_chg_rel` = 동 유효 매매 건수의 4분기 log 변화(`log1p`) − `mean_{E_t}`
- **결측 처리(N04)**: R1은 위 규칙 뒤 남은 결측을 0으로 채운다. R2는 LightGBM 기본 결측 처리(NaN 유지)
- **학습 규칙(N04)**: 기점 s 예측 모델은 `u + h ≤ s`인 기점 u의 `T_u` 행으로 학습. target `r_rt`. 행 가중치 없음
  - R1: 표준화(학습 행 기준, 표준편차 0이면 0), **λ = 10 고정**, 절편 포함
  - R2 L1: num_leaves 15, min_data_in_leaf 100, learning_rate 0.03, 300 rounds, feature_fraction 0.7, bagging_fraction 0.8, bagging_freq 1, lambda_l2 5, seed 20260915, num_threads 8
  - **최소 학습 기준**: 학습 기점 8개 이상이고 학습 행 1,500개 이상. 미달이면 그 기점의 R1·R2 예측은 R0(0)으로 두고 `r_model_status="insufficient_train"`
- **재중심화**: 예측 후 `r̂_centered = r̂_raw − mean_{E_s}(r̂_raw)` (서비스 대상 `E_s` 기준)
- **γ 선택(N05)**: 모델별 `γ_R[t]`. 기점 t에서 `s + h ≤ t`이고 `r_model_status="ok"`인 과거 기점 s의 `T_s` 행 `(r̂_centered, r_rt)`만 모은다. γ ∈ {0, 0.25, 0.5, 0.75, 1}마다 기점 동일 가중 `mean|γ·r̂_centered − r_rt|`를 계산하고 최소 γ 선택, **동률이면 작은 γ**. 과거 기점 8개 미만 또는 행 1,000개 미만이면 γ = 0

### 3.3 최종 결합

- `ŷ[d,t] = M̂[t] + γ_R[t] · r̂_centered[d,t]`
- 모든 예측 행에 `max_train_origin`, `max_label_vintage`, `n_train_origins`, `n_train_rows`를 기록하고 `max_label_vintage ≤ prediction_origin`, `max_train_origin + h ≤ prediction_origin`을 assert(F07)

### 3.4 이벤트 코딩 (M3 전용)

- `category=policy`만, `direction` ∈ {tighten:+1, ease:−1, 그 외 0}. 혼합 대책은 표의 `direction` 그대로, 한 대책은 기준일 1개. 결정 기록에 고정

## 4. 평가와 선택

### 4.1 구간

- **튜닝 구간**: h=4 기점 2016Q1~2020Q4(20개). 선택은 여기서만
- **최근 구간 점검**: 2021Q1~2025Q2(18개). 선택 후 계산해 보고만 한다
- 표본 고정: 한 구간 안에서 모든 변형은 **같은 (dong, origin) 행**(`T_t`)으로 점수를 계산한다. 공통 표본 assert

### 4.2 선택 규칙 (N06)

1. 시장: 튜닝 구간 기점 동일 가중 시장 MAE `mean_t|M̂ − M_rt|`에서 `(MAE_M0 − MAE_M1) / MAE_M0 ≥ 0.02`(full precision)이면 M1, 아니면 M0
2. 상대: 튜닝 구간 기점 동일 가중 상대 MAE `mean_t mean_{T_t}|γ·r̂_centered − r_rt|`에서 R0 대비 개선율 0.02 이상인 R 중 개선율이 큰 것. 없으면 R0. 동률이면 단순한 쪽(R0 > R1 > R2)
3. 2% 문턱은 실무 문턱이며 통계적 유의성이 아니다. 연도별 개선율과 leave-one-year-out 개선율을 **보고만** 한다(선택 게이트 아님)

### 4.3 비교 대상

| ID | 내용 | 표기 |
|---|---|---|
| B1 | 동 `mom_4q` | baseline |
| B2 | `S_mom_4q` (= M0 + R0) | baseline |
| Mx+Ry | M0~M3 × R0~R2 전 조합 | 탐색 |
| **SEL** | §4.2 선택 | 탐색 |
| V0 | 공식 모델 `44.1` | **비교 불가능한 historical reference**. future-revised target(y_full) 학습에 따른 잠재적 누출과 target mismatch가 있어 순위 판정에서 제외(N09) |

모든 변형은 `y_rt`와 `y_full` 두 기준으로 점수를 낸다.

### 4.4 지표

- 전체: 기점 동일 가중 MAE(주), 행 가중 MAE(보조)
- 성분: 시장 MAE, 상대 MAE, 상대 상관(기점별 Pearson의 평균), 시장 방향 부호 일치율
- 연도별 기점 동일 가중 MAE 표

### 4.5 bootstrap (N07)

- 대상: 기점별 `D_t = MAE_t(A) − MAE_t(B)`(같은 `T_t` 행). 비교 쌍: SEL−B2, SEL−B1, M1−M0(시장 MAE), Ry−R0(상대 MAE)
- 방식: **비순환(non-circular) moving-block bootstrap**. 구간 기점 수 T, 블록 길이 L이면 시작점을 `{0..T−L}`에서 균등 추출해 블록을 이어 붙이고 길이 T에서 자른다. 2,000회, seed 42. 통계량은 `mean(D*)`, 2.5·97.5 백분위
- L = 4(주), 6(민감도). 구간별(튜닝·최근·전체) 따로 계산. 결측 기점은 표본에서 제외하고 개수를 보고
- 튜닝 구간 CI는 선택 후 CI라 기술적 참고로만 표기

### 4.6 참고 기간 h=2·8·12 (N10)

- §2~§4의 모든 `4`를 h로 바꾼다: target `mom_{h}q`(vintage t+h), 학습 gap `s+h ≤ t`, γ maturity, 구간 maturity, B1=`mom_{h}q`, B2·M0=`S_mom_{h}q`
- 구조(M·R 선택 결과)와 하이퍼파라미터(λ, L1 설정)는 h=4 SEL에서 가져온다. 참고 기간에서 재선택하지 않는다
- h=12의 `mom_12q`는 vintage 12분기 전 값이 필요하므로 가능 기점만 쓴다

### 4.7 경험적 예측 구간 (N08)

- 대상: SEL. 기점 t에서 `s + h ≤ t`인 **최근 8개 기점**의 `T_s` 행 잔차 `e = |y_rt − ŷ|`
- 가중치: 각 잔차에 `1 / |T_s|`(기점 동일 가중). **가중 80% 분위수** = 잔차 오름차순 누적 가중치가 전체의 0.8 이상이 되는 첫 잔차
- 최소 조건: 8개 기점, 1,000행. 미달이면 구간 없음
- 구간: `[ŷ − q, ŷ + q]`. 튜닝·최근 구간 coverage와 반폭 중앙값 보고. 화면에는 과거 coverage와 함께 표시

## 5. 구현 (terra 작성, sol 검증)

### 5.1 스크립트

| 스크립트 | 내용 |
|---|---|
| `models/index/47.build_realtime_panel.py` | 2007Q1~2011Q3 vintage 추가 계산(41과 같은 함수·λ), 41과 병합, target·시장 panel·상대 feature 생성 |
| `models/index/48.evaluate_realtime_two_stage.py` | 모든 변형 rolling OOT, γ, SEL 선택, 지표·bootstrap·경험적 구간 |
| `models/index/49.build_final_model.py` | SEL을 label 있는 모든 기점(h=4: s ≤ 2025Q2)으로 학습, 기점 2026Q2 서비스 예측 |
| `models/index/test_realtime_two_stage.py` | 합성 데이터: label gap, T_t/E_t 구분, 재중심화, γ 동률·최소 표본, fold gap assert, bootstrap 길이·결정성, 가중 분위수 |

### 5.2 산출물 스키마 (N11)

모든 파일은 탭 구분. `origin`류는 `YYYYQn` 문자열, 불리언은 `True/False`.

**`output/47.1.vintage_momentum_all.txt`** — 키 (dong, as_of_quarter), 2007Q1~2026Q2

| 컬럼 | 타입 | 결측 |
|---|---|---|
| dong, sggCd, umdNm | str | 불가 |
| as_of_quarter | str | 불가 |
| n_sales_4q | int | 불가 |
| eligible | bool | 불가 |
| mom_1q, mom_2q, mom_4q, mom_8q, mom_12q, mom_2q_gu_rel, mom_8q_gu_rel | float | 허용(이전 분기가 범위 밖) |
| vintage_source | str (`41` / `47_early`) | 불가 |

**`output/47.2.realtime_targets.txt`** — 키 (dong, origin, horizon_q), 행 = 모든 `E_t`, origin 2008Q1~2026Q2, h ∈ {2,4,8,12}

| 컬럼 | 타입 | 결측 |
|---|---|---|
| dong, sggCd, origin, horizon_q, target_vintage | str/int | 불가 |
| eligible_at_origin | bool | 불가(항상 True) |
| y_rt, y_full | float | 허용 |
| target_observed | bool | 불가 (`y_rt` 유한) |
| target_missing_reason | str: `""` / `beyond_data` / `no_vintage_row` / `index_nan` | 불가 |

**`output/47.3.seoul_market_panel.txt`** — 키 origin, 2008Q1~2026Q2

| 컬럼 | 결측 |
|---|---|
| origin, n_E | 불가 |
| S_mom_1q, S_mom_2q, S_mom_4q, S_mom_8q, S_mom_12q | 허용 |
| rate_chg_4q, S_sale_vol_4q, S_sale_vol_chg_4q, overheated_share, policy_net_4q | 불가 |
| n_T_h2, n_T_h4, n_T_h8, n_T_h12, M_rt_h2, M_rt_h4, M_rt_h8, M_rt_h12, M_full_h2, M_full_h4, M_full_h8, M_full_h12 | M은 허용(`n_T=0`) |

**`output/47.4.dong_relative_features.txt`** — 키 (dong, origin), 행 = `E_t`, origin 2011Q4~2026Q2. §3.2의 12개 feature + dong, sggCd, origin. 결측 규칙은 §3.2

**`output/48.1.predictions.txt`** — 키 (dong, prediction_origin, horizon_q, variant)

`dong, sggCd, prediction_origin, horizon_q, variant, market_model, relative_model, in_T, M_hat, M_rt, r_hat_raw, r_hat_centered, gamma, y_hat, y_rt, y_full, lambda, n_train_origins, n_train_rows, max_train_origin, max_label_vintage, r_model_status, lower, upper, n_calibration_origins, n_calibration_rows`
- `lower`/`upper`/`n_calibration_*`는 SEL 행만, 나머지 결측

**`output/48.2.metrics.txt`** — 키 (horizon_q, segment, target_basis, variant, metric)

`horizon_q, segment(tuning/recent/all), target_basis(rt/full), variant, metric(mae_origin/mae_row/market_mae/relative_mae/relative_corr/market_sign_hit), value, n_origins, n_rows`

**`output/48.3.bootstrap.txt`** — 키 (horizon_q, segment, target_basis, comparison, block_length)

`comparison, block_length, n_origins, n_missing_origins, mean_diff, ci_low, ci_high, n_boot, seed`

**`output/48.4.selection_log.txt`** — 키 (decision, candidate)

`decision(market/relative), candidate, tuning_mae, baseline_mae, improvement_ratio, selected, reason`, 이어서 연도별·leave-one-year-out 개선율 행(`decision=stability`)

**`output/48.5.interval_coverage.txt`** — 키 (horizon_q, segment)

`n_origins_with_interval, n_rows, coverage, median_half_width`

**`output/49.model/model.json`**: `selected_market, selected_relative, lambda, market_scaler(mean/std/feature 순서), market_coef, market_intercept, relative_scaler·coef·intercept(R1) 또는 lightgbm_model 파일명(R2), gamma, interval_half_width, n_calibration_origins, train_origin_min, train_origin_max, label_vintage_max, input_sha256{파일:해시}, created_at`

**`output/49.1.latest_predictions.txt`** — 키 dong, 기점 2026Q2의 vintage 전 동

`dong, sggCd, umdNm, origin, horizon_q, status(PREDICTED/INSUFFICIENT_SALES), n_sales_4q, M_hat, r_hat_centered, gamma, y_hat, change_pct_est, lower_pct, upper_pct`
- `change_pct_est = (exp(y_hat) − 1) × 100`, 구간도 같은 변환. `INSUFFICIENT_SALES`는 예측 컬럼 결측

### 5.3 필수 assert

- 모든 산출물 키 유일
- 학습 행 `max_label_vintage ≤ prediction_origin`, `max_train_origin + h ≤ prediction_origin`
- 한 (horizon, segment, target_basis)에서 변형 간 평가 행 집합 동일
- `r_hat_centered`의 `E_s` 평균 = 0 (|값| < 1e-9)
- 47.2의 h=4 `y_rt`가 41 `mom_4q`(t+4)와 2011Q4 이후 일치

## 6. 위험과 한계

- 시장 모델의 독립 정보는 몇 번의 국면뿐이다(20개 튜닝 기점 ≈ 비중첩 5개 연 구간)
- 모든 결과는 이미 관찰된 기간의 탐색적 결과다. 2026Q3 이후 target이 쌓여야 독립 확인이 가능하다
- 해제 거래 시점·신고 시점은 복원할 수 없다
- 경험적 구간은 coverage를 보장하지 않는다

## 7. v3.1 계약 보완 (sol 검토 v3 K01~K09)

### 7.1 h 치환 allow-list (K01, §4.6 대체)

h ∈ {2, 4, 8, 12}에서 **아래만** h로 바꾼다. 나머지(모든 4분기 trailing feature, `n_sales_4q` eligible 기준, `rate_chg_4q`, R allow-list, bootstrap 블록 길이 4·6)는 h와 무관하게 고정한다.

| 항목 | h 치환 |
|---|---|
| target | `y_rt[h] = V_{t+h}(t+h) − V_{t+h}(t)`, `y_full[h]` |
| 학습 label gap | `s + h ≤ t` (시장·상대 모두) |
| γ maturity, 경험적 구간 maturity | `s + h ≤ t` |
| B1 | `mom_{h}q` |
| B2, M0 | `S_mom_{h}q` |
| M1~M3 ridge 보정 target | `M_rt[h][s] − S_mom_{h}q[s]` |
| M1 z 첫 feature | `S_mom_1q − S_mom_4q` 그대로(고정) |

### 7.2 full target 기준 표본 (K04)

- `U_t = {d ∈ T_t : y_full 유한}`
- `M_full[t] = mean_{U_t}(y_full)`, `r_full = y_full − M_full`
- `target_basis=full` 지표: 전체 MAE `|ŷ − y_full|`, 시장 MAE `|M̂ − M_full|`, 상대 MAE `|γ·r̂_centered − r_full|`, 모두 `U_t`에서 계산
- 공통 표본 assert는 basis별 universe(rt: `T_t`, full: `U_t`)에서 모든 변형이 같은 행을 쓰는지 확인
- 47.3의 `M_full_h*`는 `U_t` 평균, `n_U_h*` 컬럼 추가

### 7.3 ridge 정의와 파라미터 이름 (K05)

- 새 의존성 없이 numpy로 푼다. 학습 행으로 feature 평균 `μ`, 모집단 표준편차 `σ`(ddof=0)를 구하고 `Z = (X − μ)/σ` (σ=0이면 그 열 0)
- 절편은 penalty 없음: `b = mean(y)`, `w = (ZᵀZ + αI)⁻¹ Zᵀ(y − b)` (**제곱합 손실**, 행 수로 나누지 않음)
- 예측 `ŷ = b + Z_new w`
- 파라미터 이름: `index_ridge_lambda = 5`(40·41·47 vintage), `market_ridge_alpha = 10`, `relative_ridge_alpha = 10`, `lightgbm_lambda_l2 = 5`. 48.1·model.json에 각각 따로 저장

### 7.4 48.1 행 범위·계보·결측 규칙 (K03)

- 행 범위: 모든 `E_t` × 모든 variant × h, origin은 variant가 정의되는 기점부터(시장 2008Q1~). 평가는 `in_T=True`와 basis별 유한 조건으로 거른다
- variant enum: `B1`, `B2`, `M0_R0`, `M0_R1`, `M0_R2`, `M1_R0` … `M3_R2`(12개), `SEL`(선택된 조합 행을 복제), `V0`(44.1이 있는 기점·동만)
- 계보 컬럼(단일 `lambda`, `n_train_*`, `max_*` 대체):
  - `market_model, market_status, market_n_train_origins, market_max_train_origin, market_max_label_vintage, market_ridge_alpha`
  - `relative_model, r_model_status, relative_n_train_origins, relative_n_train_rows, relative_max_train_origin, relative_max_label_vintage, relative_ridge_alpha, lightgbm_lambda_l2`
- baseline 표현:

| variant | M_hat | r_hat_raw / r_hat_centered | gamma | 계보 |
|---|---|---|---|---|
| B1 | `S_mom_{h}q` | `mom_{h}q − S_mom_{h}q` (centered 동일) | 1 | `baseline`, 수치 결측 |
| B2 | `S_mom_{h}q` | 0 | 0 | `baseline` |
| V0 | `mean_{V0 행}(pred)` | `pred − M_hat` | 1 | `historical_reference`, 수치 결측 |

- `market_status` enum: `ok`, `insufficient_train`(M1~M3 학습 기점 12개 미만 → M0 값 사용), `baseline`
- `r_model_status` enum: `ok`, `insufficient_train`(8기점·1,500행 미만 → 0), `no_features`(기점 < 2011Q4 → 0), `baseline`. 미달이어도 실제 `relative_n_train_origins`, `relative_n_train_rows`는 기록

### 7.5 48.x 스키마 수정 (K02)

- **48.3.bootstrap**: 컬럼 `horizon_q, segment, target_basis, comparison, block_length, n_origins, n_missing_origins, mean_diff, ci_low, ci_high, n_boot, seed`. 키 (horizon_q, segment, target_basis, comparison, block_length)
- **48.4.selection_log**: 컬럼 `record_type(selection/stability_year/stability_loyo), decision(market/relative), candidate, slice_id(all / 연도 / 제외한 연도), tuning_mae, baseline_mae, improvement_ratio, selected, reason`. 키 (record_type, decision, candidate, slice_id). `selected`는 selection 행만, 나머지 결측
- **48.5.interval_coverage**: 컬럼 `horizon_q, segment, n_origins_with_interval, n_rows, coverage, median_half_width`. 키 (horizon_q, segment). rt basis만

### 7.6 bootstrap 결측 처리·분위수 (K06)

- 원래 분기 격자에서 블록을 만든다. 구간 안에 `D_t` 결측 기점이 있으면 결측을 포함하지 않는 완전한 연속 블록의 시작점만 허용한다. 허용 시작점이 없으면 CI 결측
- 백분위는 `numpy.percentile(..., method="linear")`

### 7.7 파일 형식·센티널 (K07)

- `output/49.model/model.json`(JSON)과 LightGBM 모델 텍스트는 탭 구분 규칙의 예외
- `target_missing_reason`은 관측 행에 `none`을 쓴다. 읽을 때 `keep_default_na=False`로 문자열 컬럼을 읽는다

### 7.8 동 키 불변식 (K08)

- 모든 입력·산출물에서 `dong == sggCd + "_" + umdNm`, `dong → (sggCd, umdNm)` 1:1을 assert

### 7.9 LightGBM 결정성 (K09)

- `seed = bagging_seed = feature_fraction_seed = data_random_seed = 20260915`, `deterministic = True`, `force_row_wise = True`, `num_threads = 8`
