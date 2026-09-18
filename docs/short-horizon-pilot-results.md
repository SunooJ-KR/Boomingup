# 동별 3개월 변화율 예측 파일럿 1단계 결과

> 작성 2026-09-18. 모든 수치와 선택은 탐색적 파일럿 결과다.
> holdout 기점 2025-05~2026-04는 열지 않았다. 가격은 적재 단계에서 2025-04 뒤 거래를 버리고 assert했으며, 파일럿 origin은 2025-01이 마지막이다.

## 결론

MAIN 설계에서 동 상대 변화를 예측하는 신호는 확정되지 않았다. Ridge의 R0 대비 상대 MAE 개선은 0.28% [95% CI −0.35%, 0.76%]였고 Spearman은 0.055 [−0.011, 0.114]였다. LightGBM은 0.12% [−0.12%, 0.31%]와 0.033 [−0.006, 0.074]였다. 두 모델 모두 구간이 0을 포함한다.

SENS_LAG와 SENS_CURRENT는 sensitivity 결과다. 특히 SENS_CURRENT는 target base window와 현재 모멘텀이 같은 가격 측정 오차를 공유하므로 measurement-noise sensitivity reference로만 보고한다. 이 결과로 신호의 존재나 출처를 주장하지 않는다.

## 설계

target fit은 기존처럼 origin t마다 거래 [t−35,t+3]에서 target만 만들었다. feature용 pastfit(t)는 [t−35,t]만으로 별도 추정해 cache했다. 구조 B의 기간은 W(t−2..t), W(t−5..t−3), …에서 끝난다.

publication lag L(t)는 2020-03 이전 2개월, 이후 1개월이다. 모든 운영 가능 baseline과 feature는 최대 t−L의 거래만 쓴다.

- MAIN: 동·구·인접·동−구 가격 feature는 pastfit(t−3), 서울 market feature는 pastfit(t−L), volume은 t−L까지 쓴다.
- SENS_LAG: 모든 가격 모멘텀을 pastfit(t−L)에서 가져온다.
- SENS_CURRENT: 기존 current-window 행동을 재현한 leaky reference다.
- 분기 42/43 feature는 기존 extra-quarter lag을 유지했다.

평가는 2012-01~2025-01의 157개 origin에서 했다. expanding window로 12개 origin마다 refit했고 학습 행은 s+3≤t로 purge했다. LightGBM inner validation은 학습 기간의 마지막 24개 origin이며, fit 행은 s+3≤validation 시작을 만족한다. CI는 moving-block bootstrap(block 6, 2,000회, seed 42)이다.

## P0·P1

데이터 끝은 2026-08이고, 2026-08 거래량은 직전 12개월 중앙값의 0.51배였다. 마지막 완결 월은 2026-07, target이 완결된 마지막 origin은 2026-04로 판단했다. 따라서 기존 holdout 2025-05~2026-04를 유지했다.

신고일 열이 없어 historical snapshot을 복원할 수 없다. 2026-08과 2026-07의 계약일별 건수를 비교한 거친 근사에서 계약 후 10~19일의 가용 비율은 0.66~0.73이었다. 이 근사의 불확실성 때문에 과거 final snapshot의 origin t 거래를 쓰지 않고 publication lag를 강제했다.

## P2 시간 구조

post-hoc threshold를 선택 근거에서 제외했다. split-half reliability는 A 0.371, B 0.502였고, 거래량 5개 bin 모두에서 B가 A보다 높았다. 이 결과로 구조 B를 권고했다.

y_t와 y_t+3은 인접 non-overlapping 기간의 변화이지만 중간 경계 지수 창을 반대 부호로 공유한다. 따라서 오차가 독립적이라고 해석하지 않았다.

## P3 baseline

publication lag를 적용한 전체 기간 N=10 결과다.

| baseline | MAE | 상대 MAE | Spearman | 80% coverage | 구간 폭 |
|---|---:|---:|---:|---:|---:|
| B0 0 | 0.0335 | 0.0178 | – | 0.745 | 0.0799 |
| B1 동, t−L | 0.0375 | 0.0267 | −0.044 | 0.769 | 0.1058 |
| B2 구, t−L | 0.0336 | 0.0206 | 0.051 | 0.764 | 0.0926 |
| B3 서울, t−L | 0.0326 | 0.0182 | – | 0.763 | 0.0909 |
| B1' 동, t−3 | 0.0394 | 0.0258 | 0.041 | 0.760 | 0.1075 |
| B2' 구, t−3 | 0.0364 | 0.0208 | 0.055 | 0.754 | 0.0975 |

B3은 절대 MAE가 가장 낮지만 상대 MAE는 B0보다 높다. baseline의 서열을 동 상대 예측 신호의 근거로 쓰지 않는다.

## P4 상대 target 모델

R0는 기점별 상대 target에 0을 예측한다. 개선은 R0 대비 상대 MAE 개선율이다.

| feature set | 기간 | 모델 | 개선 [95% CI] | Spearman [95% CI] |
|---|---|---|---:|---:|
| MAIN | 2012~2019 | Ridge | 0.19% [−0.63, 0.92] | 0.054 [−0.024, 0.137] |
| MAIN | 2012~2019 | LightGBM | 0.21% [0.03, 0.44] | 0.037 [−0.015, 0.097] |
| MAIN | 2020~2025-01 | Ridge | 0.39% [−0.16, 1.13] | 0.058 [−0.017, 0.142] |
| MAIN | 2020~2025-01 | LightGBM | 0.01% [−0.34, 0.37] | 0.028 [−0.031, 0.083] |
| SENS_LAG | 전체 | Ridge | 0.73% [0.08, 1.39] | 0.093 [0.048, 0.133] |
| SENS_LAG | 전체 | LightGBM | 0.26% [−0.07, 0.57] | 0.071 [0.031, 0.111] |
| SENS_CURRENT | 전체 | Ridge | 2.49% [1.25, 3.46] | 0.203 [0.140, 0.249] |
| SENS_CURRENT | 전체 | LightGBM | 2.59% [1.50, 3.57] | 0.210 [0.164, 0.247] |

MAIN permutation importance의 상대 MAE 증가는 모두 0.00009 이하였다. SENS_CURRENT에서만 주변 모멘텀 importance가 크게 나왔다. 이 차이는 current-window 가격 측정 오차의 영향으로 해석한다.

Ridge λ grid는 10^−2~10^7이다. edge 선택은 MAIN 9/14회, SENS_LAG 5/14회, SENS_CURRENT 2/14회였다. MAIN의 안정적인 모델 선택이 되지 않았다는 추가 증거다. LightGBM은 deterministic seed 42, fixed 8 threads, purged inner validation과 early stopping을 사용했다.

## P5 사후 구 shrink 실험

이 실험은 계획서의 hierarchical pooling을 구현한 것이 아니다. MAIN에서 선택된 Ridge 예측을 사후에 구 평균으로 shrink한 민감도 실험이다.

N=10/20/30의 MAIN Ridge 개선은 각각 0.28%, 0.30%, 0.39%였고 모두 bootstrap CI가 0을 포함했다. 예측 동 수는 origin당 187, 149, 126개로 줄었다.

80% residual interval 폭은 3개월 거래 0건 0.0877, 1~4건 0.0994, 5~9건 0.1095, 10~19건 0.1027, 20~29건 0.0939, 30건 이상 0.0774였다. target 자체가 ridge λ=5로 구 변화 쪽으로 shrink되고, target 거래 0건 비율이 3개월 거래 0건 bin에서 56%다. 따라서 sparse-dong metric은 낙관적이며 hierarchical pooling 성능으로 해석할 수 없다.

## sol 검토 반영

| 등급 | 검토 지적 | 반영 내용 |
|---|---|---|
| P0 | target fit의 future 거래가 FE를 통해 feature에 유입 | target fit과 모든 origin의 pastfit을 분리했고 61~65를 재실행했다. |
| P0 | target base window와 current momentum의 measurement noise 공유 | MAIN의 동·구·인접 feature를 t−3으로 끝냈고 current 방식은 sensitivity로 강등했다. |
| P0 | 과거 final snapshot의 origin-t 거래 사용 | 2020-03 이전 L=2, 이후 L=1 publication lag를 baseline·model·volume에 강제했다. |
| P1 | Ridge grid edge와 LightGBM early stopping 누락 | λ grid를 10^−2~10^7로 넓혀 edge 횟수를 보고했고 purged 24-origin validation과 early stopping을 추가했다. |
| P1 | P5가 hierarchical pooling이 아님 | 제목을 “사후 구 shrink 실험”으로 바꾸고 미구현 범위와 target measurement error의 낙관 편향을 명시했다. |
| P2 | P2 post-hoc threshold와 부정확한 “겹치지 않는 변화” | threshold를 결정 근거에서 제외하고 volume bin별 split-half reliability로 B를 권고했으며 경계 지수 창 공유를 명시했다. |
| P2 | 신호 존재·주변 모멘텀 출처 over-claim | MAIN CI가 0을 포함하는 결과로 결론을 바꾸고 해당 주장을 삭제했다. |

## 실행 시간과 검증

- 합성 test: 통과.
- smoke 61, 2개 구×12개 origin: 6.74초. smoke 62: 6.41초.
- full 61: 1,595.24초. full 62: 112.47초. full 63: 5.79초. full 64: 19.91초. full 65: 2.71초.
- `pastfit.max_sale_ym ≤ pastfit.origin`, `MAIN local_max_sale ≤ t−3`, `forecast_max_sale ≤ t−L`, `deal_ym ≤ 202504`, `origin ≤ 202501`을 assert로 확인했다.

## 한계

이 파일럿은 결과를 본 뒤 redesign한 탐색적 분석이다. MAIN은 noise-sharing을 줄였지만 historical reporting snapshot을 복원한 것은 아니다. target reliability는 B에서도 0.50 수준이고, 인접 origin의 target은 경계 지수 창을 공유한다. MAIN Ridge의 λ가 grid edge에 9/14회 있어 모델 선택도 불안정하다. holdout은 계속 보존한다.
