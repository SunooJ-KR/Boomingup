# 자치구 3개월 상대 가격 예측 결과

이 실험은 동 단위 MAIN 결과를 본 뒤 수행한 탐색적 분석이다. 평가에는 2012-01부터 2025-01까지 157개 origin만 썼다. holdout origin 2025-05~2026-04는 target 생성, feature 생성, 학습, 평가 어디에서도 사용하지 않았다.

## 설정

각 origin t에서 최근 3개월 거래가 10건 이상인 법정동을 eligible 동으로 정했다. 구 target은 eligible 동별 hedonic log 변화 `W(t+1..t+3) − W(t−2..t)`의 동일가중 평균이고, 같은 origin의 구 target 서울 평균을 뺀 상대값이다. eligible 동이 3개 미만인 구-origin은 제외했다. 전체 25구×157 origin 3,925개 중 203개를 제외했고, 평가에 들어간 구는 origin당 평균 23.71개, 최소 14개, 최대 25개였다.

기존 `output/61.1.origin_panel.txt`의 target fit과 `output/61.2.pastfit.txt`의 feature용 pastfit을 재사용했다. 동·구 가격 feature는 pastfit(t−3), 서울 market momentum은 pastfit(t−L), volume은 t−L까지만 썼다. publication lag L(t)는 2020-03 이전 2개월, 이후 1개월이다. 분기 feature는 기존 extra-quarter lag을 유지했다. 코드에서 `local_max_sale ≤ t−3`, `forecast_max_sale ≤ t−L`, `origin ≤ 2025-01`을 assert했다.

R0는 상대 변화 0을 예측한다. 서울 momentum implied baseline은 모든 구에 같은 값을 주므로 상대값으로 바꾸면 R0와 같다. 구 momentum baseline은 t−3의 구 momentum을 origin별로 재중심화했다. Ridge는 origin별 cross-sectional z-score와 λ `10^-2`~`10^7` grid를 썼다. LightGBM은 deterministic 설정과 purged inner validation, early stopping을 썼다. expanding window에서 12개 origin마다 refit했고 학습 label은 `s+3≤t`인 행만 허용했다. CI는 origin moving-block bootstrap, block 6개월, 2,000회, seed 42로 계산했다.

## Target reliability

기존 advisor 계산은 6개월 간격 33개 origin에서 0.590이었다. 같은 거래 반분과 Spearman-Brown 보정을 157개 full origin에 다시 적용한 결과 평균 reliability는 0.561이었다. origin별 중앙값은 0.680이었다. 구 aggregation으로 measurement noise가 줄기는 하지만 reliability가 높은 수준은 아니다.

## Baseline 결과

아래 상대 MAE와 나머지 지표는 origin을 동일 가중한 평균이다. 개선 CI와 Spearman CI는 model 표에서 보고한다.

| 기간 | baseline | 상대 MAE | R0 대비 개선 | Spearman | 방향 정확도 | 80% coverage |
|---|---|---:|---:|---:|---:|---:|
| 전체 | R0 | 0.0104 | 0.00% | 정의 안 됨 | 0.000 | 0.715 |
| 전체 | 서울 momentum implied | 0.0104 | 0.00% | 정의 안 됨 | 0.000 | 0.715 |
| 전체 | 구 momentum | 0.0140 | −34.61% | 0.069 | 0.525 | 0.701 |
| 2012–2019 | 구 momentum | 0.0119 | −33.66% | 0.040 | 0.515 | 0.715 |
| 2020–2025-01 | 구 momentum | 0.0172 | −35.67% | 0.116 | 0.540 | 0.679 |

서울 momentum implied baseline과 R0는 이 상대 target에서 수학적으로 같은 예측이다. 구 momentum은 두 기간 모두 R0보다 나빴다.

## Model 결과

개선은 R0 대비 상대 MAE 개선율이다. 대괄호는 95% block-bootstrap CI다.

| 기간 | 모델 | 개선 [95% CI] | Spearman [95% CI] | 방향 정확도 | 80% coverage |
|---|---|---:|---:|---:|---:|
| 전체 | Ridge | 0.83% [−1.31%, 2.48%] | 0.121 [0.017, 0.205] | 0.541 | 0.715 |
| 전체 | LightGBM | −0.16% [−0.77%, 0.40%] | 0.044 [−0.019, 0.113] | 0.515 | 0.713 |
| 2012–2019 | Ridge | 0.29% [−2.51%, 2.71%] | 0.112 [−0.006, 0.227] | 0.544 | 0.727 |
| 2012–2019 | LightGBM | 0.29% [−0.56%, 0.95%] | 0.065 [−0.043, 0.165] | 0.526 | 0.723 |
| 2020–2025-01 | Ridge | 1.42% [−0.73%, 3.92%] | 0.135 [0.004, 0.278] | 0.536 | 0.698 |
| 2020–2025-01 | LightGBM | −0.67% [−1.40%, 0.09%] | 0.017 [−0.027, 0.096] | 0.498 | 0.700 |

LightGBM은 157개 origin 중 16개에서 구별 예측이 상수라 Spearman을 정의할 수 없었다. 표의 전체 LightGBM Spearman은 정의 가능한 141개 origin 평균이다. Ridge λ는 14회 refit 중 10회 grid edge가 선택됐다. 두 현상 모두 안정적인 model selection의 근거가 부족함을 보인다.

## Kill criterion 판정

Kill criterion은 상대 MAE 개선이 2% 미만이거나 그 95% CI가 0을 포함하고, 동시에 origin별 Spearman 95% CI 하한이 0.10 이하이면 중단하는 것이다.

Ridge는 개선 0.83%이고 CI가 0을 포함하며 Spearman CI 하한이 0.017이므로 kill이다. LightGBM은 개선 −0.16%이고 CI가 0을 포함하며 Spearman CI 하한이 −0.019이므로 kill이다. 따라서 구 단위 3개월 상대 가격 target도 development 결과에서 중단 기준을 통과하지 못했다. 이 결과로 holdout을 열지 않으며 구 forecast를 채택하지 않는다.

## 한계

단면 단위가 최대 25개 구뿐이라 origin별 rank correlation의 cluster 수가 적다. 구 안 동을 동일가중했지만 eligible 동의 구성은 origin마다 달라진다. split-half reliability의 일부 origin은 적은 구와 noisy half fit 때문에 불안정하다. 이 분석은 동 단위 결과를 본 뒤 설계한 exploratory 결과이며 confirmatory evidence가 아니다. 경험적 80% interval coverage도 Ridge 71.5%, LightGBM 71.3%로 목표보다 낮다. holdout 2025-05~2026-04는 계속 untouched 상태다.

## 실행과 산출물

합성 unit test 3개가 통과했다. Smoke 72는 8.36초, smoke 73은 0.96초였고, full 72는 596.83초였다. 최종 full 73은 3.56초였다. 결과는 `output/72.*`와 `output/73.*`에 tab-separated 형식으로 저장했다.
