# 단기 동 상대 예측 algorithm 비교

이 분석은 exploratory 비교다. 기존 MAIN 설정인 동 단위 3개월 relative target `r`, MAIN feature set, 적격 기준 `n_3m >= 10`을 그대로 사용했다. 평가 origin은 2012년 1월부터 2025년 1월까지만 포함했다. 2025년 5월 이후 holdout은 열거나 사용하지 않았다.

## 방법

`64.evaluate_relative_models.py`와 같이 expanding window에서 12개 origin마다 refit했고, training row는 `s+3 <= t` 조건으로 purge했다. Linear model과 RBF kernel model에는 origin별 cross-sectional z-score를 적용했다. 모든 metric은 origin에 같은 weight를 주었다. 95% CI는 6개월 moving-block bootstrap 2,000회와 seed 42로 계산했다.

Ridge와 LightGBM은 같은 fit을 다시 계산하지 않고 `output/64.3.predictions.txt`의 MAIN prediction을 재사용했다. Ridge grid와 LightGBM 설정은 따라서 64번과 완전히 같다. ElasticNet은 `(alpha, l1_ratio)` 후보 `(0.0001, 0.2)`, `(0.0001, 0.8)`, `(0.001, 0.2)`, `(0.001, 0.8)`, `(0.01, 0.5)`를 비교했다. RandomForest는 tree 300개를 고정하고 `min_samples_leaf`를 5, 20, 50 중에서 골랐으며 `random_state=42`, `n_jobs=4`를 사용했다. SVR은 RBF kernel에서 `C`를 0.1, 1, 10 중에서 골랐고 `gamma="scale"`, `epsilon=0.001`을 사용했다. ElasticNet, RandomForest, SVR의 선택에는 64번과 같은 purged inner validation을 적용했다.

SVR은 runtime을 제한하기 위해 refit마다 training row를 seed 42로 최대 5,000개 random subsample했다. Inner fit과 final fit은 각각 해당 단계의 training pool에서 독립적으로 같은 규칙을 적용했다. scikit-learn version은 1.9.1이며 `models/requirements.txt`에 pin했다.

## 결과

`R0 대비 relative-MAE 개선`은 양수가 좋다. `Ridge 대비 차이`는 `Ridge relative MAE - candidate relative MAE`이므로 역시 양수가 좋다. 방향 정확도는 relative target `r`의 부호 일치율이다. R0는 항상 0을 예측하므로 Spearman과 방향 정확도를 정의하지 않았다.

| 기간 | Candidate | R0 대비 relative-MAE 개선 (95% CI) | Mean Spearman (95% CI) | 방향 정확도 | Ridge 대비 차이 (95% CI) |
|---|---|---:|---:|---:|---:|
| 2012–2019 | R0 | 0.0000 (0.0000, 0.0000) | NA | NA | -0.0000 (-0.0001, 0.0001) |
| 2012–2019 | OLS | -0.0057 (-0.0175, 0.0050) | 0.0490 (-0.0171, 0.1201) | 0.5165 | -0.0001 (-0.0002, -0.0000) |
| 2012–2019 | Ridge | 0.0019 (-0.0063, 0.0092) | 0.0551 (-0.0226, 0.1381) | 0.5176 | 0.0000 (0.0000, 0.0000) |
| 2012–2019 | ElasticNet | 0.0021 (-0.0060, 0.0090) | 0.1672 (-0.0465, 0.3206) | 0.5536 | 0.0000 (-0.0000, 0.0000) |
| 2012–2019 | RandomForest | -0.0132 (-0.0287, -0.0007) | 0.0222 (-0.0305, 0.0678) | 0.5080 | -0.0002 (-0.0004, -0.0001) |
| 2012–2019 | SVR RBF | -0.0880 (-0.1222, -0.0635) | 0.0098 (-0.0183, 0.0407) | 0.5042 | -0.0014 (-0.0017, -0.0011) |
| 2012–2019 | LightGBM | 0.0021 (0.0003, 0.0044) | 0.0366 (-0.0150, 0.0971) | 0.5149 | 0.0000 (-0.0001, 0.0001) |
| 2020–2025.01 | R0 | 0.0000 (0.0000, 0.0000) | NA | NA | -0.0001 (-0.0002, 0.0000) |
| 2020–2025.01 | OLS | 0.0094 (0.0005, 0.0196) | 0.1318 (0.0640, 0.2187) | 0.5469 | 0.0001 (-0.0000, 0.0003) |
| 2020–2025.01 | Ridge | 0.0039 (-0.0016, 0.0113) | 0.0587 (-0.0159, 0.1419) | 0.5228 | 0.0000 (0.0000, 0.0000) |
| 2020–2025.01 | ElasticNet | 0.0032 (-0.0019, 0.0100) | 0.1140 (-0.0225, 0.2966) | 0.5487 | -0.0000 (-0.0000, 0.0000) |
| 2020–2025.01 | RandomForest | -0.0183 (-0.0398, -0.0024) | 0.0498 (-0.0507, 0.1120) | 0.5103 | -0.0005 (-0.0010, -0.0002) |
| 2020–2025.01 | SVR RBF | -0.0579 (-0.0798, -0.0406) | 0.0404 (-0.0037, 0.0832) | 0.5119 | -0.0013 (-0.0016, -0.0011) |
| 2020–2025.01 | LightGBM | 0.0001 (-0.0034, 0.0037) | 0.0279 (-0.0315, 0.0823) | 0.5075 | -0.0001 (-0.0002, 0.0000) |

## Candidate별 결론

- R0는 비교 기준이며 동 간 순위를 설명하지 않는다.
- OLS는 후기 기간에 작은 개선이 있었지만 초기 기간에서 재현되지 않아 안정적인 signal의 근거가 아니다.
- Ridge는 두 기간 모두 개선 CI가 0을 포함해 reference 결론을 유지한다.
- ElasticNet은 Ridge와 실질적으로 같은 relative MAE이고 Spearman CI도 두 기간 모두 0을 포함한다.
- RandomForest는 두 기간 모두 R0와 Ridge보다 relative MAE가 나빠졌다.
- SVR RBF는 두 기간 모두 가장 큰 relative MAE 악화를 보였다.
- LightGBM은 초기 기간에 0.21%의 작은 개선이 있었지만 후기 기간에서는 사라졌고 Ridge보다 낫다는 근거도 없다.

어떤 algorithm도 동-relative signal이 확립되지 않았다는 pilot 결론을 바꾸지 않는다. 후기 OLS와 초기 LightGBM의 부분 결과는 기간 전체에서 반복되지 않았고, multiple candidate를 exploratory하게 비교한 결과이므로 confirmatory evidence로 해석하지 않는다.

## Runtime과 산출물

| Candidate | 이번 실행의 fit·tuning runtime (초) |
|---|---:|
| R0 | 0.000 |
| OLS | 0.349 |
| Ridge | 0.000 |
| ElasticNet | 1.743 |
| RandomForest | 847.017 |
| SVR RBF | 395.081 |
| LightGBM | 0.000 |

Runtime은 candidate fit과 inner tuning에 걸린 wall-clock time이며 prediction 시간과 공통 panel 준비 시간은 제외했다. Ridge와 LightGBM의 0초는 계산이 공짜라는 뜻이 아니라 64번의 기존 fit 결과를 재사용해 이번 실행에서 fit하지 않았다는 뜻이다. 전체 실행 시간은 1,268.0초였다.

상세 metric은 `output/78.1.algorithm_comparison.txt`, refit별 선택값은 `output/78.2.tuning.txt`, runtime은 `output/78.3.runtimes.txt`에 저장했다.
