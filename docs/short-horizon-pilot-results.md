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

## P8 결과

P8도 holdout을 열지 않은 탐색적 분석이다. 조건을 통과한 역 단위 후보는 82행이며, 이를 `line × public_date × 사건 종류`로 묶으면 계획 1건, 착공 4건, 개통 14건이다. 세 window 중 하나 이상에서 분석 window·노출·outcome을 실제로 만족해 main 분석에 기여한 milestone의 합집합은 계획 1건, 착공 4건, 개통 8건이다. 아래 표의 milestone 수는 이 overall 합집합 수가 아니라 `67.2.pooled.txt`가 보고한 window별 수다. 개통 +6~+12에서는 2024년 12월 GTX-A 개통 뒤 +6개월 이상인 origin이 분석 종료월인 2025년 1월까지 존재하지 않아 개통 milestone이 7건만 남는다. 좌표가 없는 노선·구간 단위 사건 20개는 exposure를 계산할 수 없어 제외했다. `canonical=true`와 공개일이 origin 월말 이하인 행만 썼고, 개통은 `actual`만 썼다. 예정 개통 34행은 제외했다. 동별 exposure는 좌표가 있는 아파트 단지 가운데 역 반경 500m·1km 안에 있는 단지의 비율이다.

### P8a 역 사건 전후

값은 노출 동의 상대 3개월 변화율에서 같은 구·같은 origin의 비노출 동 평균을 뺀 값이다. 역별 1km exposure로 가중했고 CI는 project milestone cluster bootstrap 2,000회 결과다. sensitivity는 같은 origin에서 다른 사건의 ±12개월 window에 노출된 동을 control에서도 제외했다.

| 분석 | 사건 | event-time | 평균 차이 [95% CI] | milestone 수 | 동 수 |
|---|---|---:|---:|---:|---:|
| main | 계획 발표 | −12~−1 | −2.45% [NA (사건 1건)] | 1 | 4 |
| main | 계획 발표 | 0~+5 | 3.73% [NA (사건 1건)] | 1 | 4 |
| main | 계획 발표 | +6~+12 | 0.59% [NA (사건 1건)] | 1 | 4 |
| main | 착공 공개 | −12~−1 | −0.06% [−0.59, 1.44] | 4 | 20 |
| main | 착공 공개 | 0~+5 | 0.69% [−0.65, 1.31] | 3 | 18 |
| main | 착공 공개 | +6~+12 | −0.01% [−0.16, 0.74] | 3 | 17 |
| main | 개통 | −12~−1 | −0.20% [−0.87, 0.17] | 8 | 67 |
| main | 개통 | 0~+5 | −0.03% [−0.53, 0.47] | 8 | 63 |
| main | 개통 | +6~+12 | −0.78% [−1.23, −0.02] | 7 | 60 |
| sensitivity | 계획 발표 | −12~−1 | −2.45% [NA (사건 1건)] | 1 | 4 |
| sensitivity | 계획 발표 | 0~+5 | 3.73% [NA (사건 1건)] | 1 | 4 |
| sensitivity | 계획 발표 | +6~+12 | 0.59% [NA (사건 1건)] | 1 | 4 |
| sensitivity | 착공 공개 | −12~−1 | 0.45% [0.11, 1.57] | 4 | 20 |
| sensitivity | 착공 공개 | 0~+5 | 1.01% [−0.65, 1.75] | 3 | 17 |
| sensitivity | 착공 공개 | +6~+12 | 0.04% [−0.25, 0.49] | 3 | 16 |
| sensitivity | 개통 | −12~−1 | −0.32% [−1.18, 0.19] | 8 | 63 |
| sensitivity | 개통 | 0~+5 | 0.12% [−0.53, 0.92] | 8 | 59 |
| sensitivity | 개통 | +6~+12 | −1.04% [−1.83, −0.05] | 7 | 56 |

계획 발표 수치는 사건 1건과 4개 동만의 case study이며 CI를 계산하지 않았다. 개통 +6~+12의 음의 평균 차이와 CI는 main 7개 cluster와 sensitivity 7개 cluster에만 근거한다. 사건 종류와 여러 window를 multiplicity correction 없이 함께 검정했고, 같은 구 control로도 지역별 confounding을 통제하지 못했다. sensitivity에서 일부 추정치도 달라진다. 따라서 개통 +6~+12 결과는 causal opening effect의 충분한 evidence가 아니며, 이 표는 forecastable association의 기술일 뿐이다. capitalization이 발표·착공·개통 중 언제 일어나는지에 관한 어떤 주장도 지지하지 않는다.

### P8b 예측 feature 추가

`vs R0`와 `vs MAIN`은 상대 MAE 개선율이고, 괄호는 MAIN과의 기점별 상대 MAE 차이(`추가 set − MAIN`)의 block-bootstrap 95% CI다. 음수이면 추가 set의 오차가 작다.

| feature set | 기간 | 모델 | vs R0 | vs MAIN | MAE 차이 95% CI | Spearman |
|---|---|---|---:|---:|---:|---:|
| MAIN | 2012–2019 | Ridge | 0.19% | 0.00% | [0.00000, 0.00000] | 0.054 |
| MAIN+RAIL | 2012–2019 | Ridge | −0.15% | −0.35% | [0.00001, 0.00011] | 0.041 |
| MAIN+SUPPLY | 2012–2019 | Ridge | 0.45% | 0.26% | [−0.00007, −0.00001] | 0.094 |
| MAIN+RAIL+SUPPLY | 2012–2019 | Ridge | 0.18% | −0.01% | [−0.00003, 0.00005] | 0.082 |
| MAIN | 2012–2019 | LightGBM | 0.21% | 0.00% | [0.00000, 0.00000] | 0.036 |
| MAIN+RAIL | 2012–2019 | LightGBM | −0.13% | −0.35% | [0.00003, 0.00010] | −0.016 |
| MAIN+SUPPLY | 2012–2019 | LightGBM | 0.58% | 0.36% | [−0.00012, −0.00002] | 0.049 |
| MAIN+RAIL+SUPPLY | 2012–2019 | LightGBM | 0.36% | 0.15% | [−0.00009, 0.00002] | 0.024 |
| MAIN | 2020–2025-01 | Ridge | 0.39% | 0.00% | [0.00000, 0.00000] | 0.058 |
| MAIN+RAIL | 2020–2025-01 | Ridge | 0.44% | 0.05% | [−0.00003, 0.00001] | 0.060 |
| MAIN+SUPPLY | 2020–2025-01 | Ridge | 0.28% | −0.11% | [−0.00001, 0.00006] | 0.047 |
| MAIN+RAIL+SUPPLY | 2020–2025-01 | Ridge | 0.00% | −0.39% | [−0.00002, 0.00022] | 0.043 |
| MAIN | 2020–2025-01 | LightGBM | 0.01% | 0.00% | [0.00000, 0.00000] | 0.028 |
| MAIN+RAIL | 2020–2025-01 | LightGBM | 0.01% | −0.00% | [−0.00002, 0.00003] | 0.021 |
| MAIN+SUPPLY | 2020–2025-01 | LightGBM | −0.02% | −0.03% | [−0.00004, 0.00006] | 0.053 |
| MAIN+RAIL+SUPPLY | 2020–2025-01 | LightGBM | 0.02% | 0.01% | [−0.00004, 0.00005] | 0.033 |

2012–2019에는 SUPPLY가 Ridge와 LightGBM의 상대 MAE를 MAIN보다 각각 0.26%, 0.36% 개선했고 paired CI도 0 아래였다. 그러나 2020–2025-01에는 방향이 유지되지 않았다. RAIL은 어느 기간·모델에서도 안정적인 개선을 보이지 않았다. permutation importance의 MAE 증가는 rail 최대 0.000016, supply 최대 0.000056으로 작았다. Ridge λ edge 선택은 MAIN 9/14회, MAIN+RAIL 8/14회, MAIN+SUPPLY 6/14회, 둘 다 추가한 set 5/14회였다. 이 결과만으로 rail 또는 supply feature를 채택할 수 없다.

### 관련 문헌

- 황현주·정의철(2019)은 신분당선 정자–광교의 사업제안·착공·개통 단계를 비교했다. 개통·운영 단계 가격은 사업제안 단계보다 약 15% 높았고, 역에서 100m 멀어질 때의 가격 차이는 제안 단계 −1.0%에서 개통·운영 단계 −2.4%로 커졌다([논문 원문 페이지](https://journal.kci.go.kr/krer/archive/articleView?artiId=ART002478678)).
- 김재형·이상근·김진화(2025)는 동북선 착공 발표와 실제 착공을 DID로 나눠 측정했다. 600m·800m·1km 역세권에서 발표 후 2.7~3.6% 상승했고 착공 후 추가 상승을 보고했다([논문 원문 페이지](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003230614)).
- 한국교통연구원 성현곤 외(2010)는 서울 9호선 개통을 STAR 모형으로 분석했다. 급행 운행은 4.5%, 역 반경 1km 이내는 비교 아파트보다 평균 7.7% 높은 가격과 연결됐다([공식 연구보고서 원문 페이지](https://www.nkis.re.kr/subject_view1.do?eoSeq=0&otpId=KOTI00008322&otpSeq=0)).
- 최필성·현동우(2022)는 광교신도시 신분당선 개통 전후 DID에서 도보거리 600m 이내 최대 12.7%를 추정했고, 효과는 개통 2년 뒤부터 더 뚜렷했다고 보고했다([논문 원문 페이지](https://www.dbpia.co.kr/journal/articleDetail?nodeId=NODE11114498)).

문헌의 effect size는 장기 capitalization 또는 특정 노선의 인과 추정을 목표로 하며, 여기의 3개월 forecastable association과 estimand가 다르다. 따라서 문헌 수치를 P8의 기대 효과나 검증 기준으로 쓰지 않았다.

### 데이터와 해석의 한계

공급은 현재 건축물대장 snapshot의 strict apartment `법정동×사용승인월` flow만 합산했다. 누적 stock을 복원하지 않아 철거·말소 건물 부재에 따른 survivorship bias는 이 flow에 직접 적용되지 않지만, late registration과 사후 정정은 과거 completion month에 소급될 수 있다. 경계 key와 맞지 않은 공급은 원남동 1개 월 행, 2세대였다. origin별 실제 사용 최대월과 허용 최대월을 QC에 기록했으며 rail·supply 위반은 모두 0건이었다. P8 전체는 결과를 본 뒤 수행한 탐색적 분석이며 holdout 성능이나 서비스 적용 근거가 아니다.

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
- smoke 67: 2.0초. smoke 68: 115.6초. full 67: 11.3초. full 68: 140.3초.
- `pastfit.max_sale_ym ≤ pastfit.origin`, `MAIN local_max_sale ≤ t−3`, `forecast_max_sale ≤ t−L`, `deal_ym ≤ 202504`, `origin ≤ 202501`을 assert로 확인했다.
- P8에서 `rail.public_date ≤ origin 월말`, `completion month ≤ t−L`을 assert로 확인했다.

## 한계

이 파일럿은 결과를 본 뒤 redesign한 탐색적 분석이다. MAIN은 noise-sharing을 줄였지만 historical reporting snapshot을 복원한 것은 아니다. target reliability는 B에서도 0.50 수준이고, 인접 origin의 target은 경계 지수 창을 공유한다. MAIN Ridge의 λ가 grid edge에 9/14회 있어 모델 선택도 불안정하다. holdout은 계속 보존한다.
