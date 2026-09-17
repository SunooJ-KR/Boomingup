# 모델 개발 환경

이 폴더는 동 단위 지수 산출, feature 생성, rolling-origin 평가, conformal interval, 최종 예측 payload 생성을 담당한다. 2026-09-17 현재 이 작업환경에서는 `models/.venv` 기준으로 설치와 import 검증을 마쳤다.

## 현재 확인한 컴퓨팅 자원

| 항목 | 확인값 | 판단 |
|---|---:|---|
| CPU | AMD RYZEN AI MAX+ 392 w/ Radeon 8060S, 논리 프로세서 24개 | LightGBM, 패널 백테스트, 부트스트랩 실행에 충분 |
| 메모리 | 총 약 27.6 GiB | 대체로 충분하나 대형 rolling 평가 전에는 브라우저와 빌드 프로세스를 줄이는 것을 권장 |
| 디스크 | `C:` 여유 약 86 GiB, `D:` 여유 약 624 GiB | snapshot과 원천 캐시는 가능하면 `D:` 또는 `output/raw/` 정책에 맞춰 관리 |
| GPU | NVIDIA GPU는 확인되지 않음 | 현재 모델 계획은 CPU 중심이라 필수 아님 |
| Python | 3.14.5 | 현재 설치 기준. 팀 표준이 Python 3.13이면 별도 설치 후 재검증 필요 |
| Node | 24.15.0 | 프론트 확인용으로 설치됨 |

## Python 환경

현재 로컬에는 저장소 루트가 아니라 `models/.venv`에 모델 전용 가상환경을 만들었다. Windows PowerShell 기준 실행 방법은 다음과 같다.

```powershell
python -m venv models/.venv
models/.venv/Scripts/python.exe -m pip install -r models/requirements.txt
```

설치 후 import 검증:

```powershell
models/.venv/Scripts/python.exe -c "import numpy,pandas,scipy,lightgbm,requests,openpyxl,psycopg,pyproj,shapefile,sklearn,statsmodels; print('imports ok')"
```

2026-09-17 현재 위 검증 결과는 `imports ok`다.

## 필수 패키지

`models/requirements.txt`에 고정된 주요 패키지는 다음 용도다.

| 패키지 | 용도 |
|---|---|
| `numpy`, `pandas`, `scipy` | 지수 추정, feature 생성, 통계 계산 |
| `lightgbm` | rolling-origin 모델 평가와 최종 예측 모델 |
| `scikit-learn` | elastic net 등 선형 기준 모델과 전처리 |
| `statsmodels` | HAC/DM 검정 등 통계 검정 후보 |
| `requests`, `openpyxl` | 외부 데이터 수집, 엑셀 원천 파일 처리 |
| `psycopg[binary]` | PostgreSQL 적재와 DB 연동 |
| `pyproj`, `pyshp` | 행정동 경계 좌표 변환과 shapefile 처리 |

## 실행 전 요구사항

- 저장소 루트 `.env`에 API 키와 DB 연결 문자열을 둔다. 키 값은 로그와 문서에 출력하지 않는다.
- 원천 데이터와 캐시는 `output/raw/` 아래에 둔다. 큰 산출물과 민감한 파일은 commit하지 않는다.
- DB 적재 스크립트는 PostgreSQL 접속 권한이 필요하다.
- `models/AGENTS.md`에는 루트 `.venv`와 Python 3.13 기준 명령이 남아 있다. 현재 머신에서는 Python 3.14 기반 `models/.venv`로 검증했으므로, 팀 표준을 맞출 때는 가상환경 위치와 Python 버전을 한 번 정해서 문서를 정리해야 한다.

## 기본 실행 순서

저장소 루트에서 실행한다.

```powershell
$PY = "models/.venv/Scripts/python.exe"

& $PY models/index/test_dong_index.py
& $PY models/index/40.build_dong_index.py
& $PY models/index/41.build_vintage_momentum.py
& $PY models/index/42.build_dong_features.py
& $PY models/index/43.build_macro_regulation.py
& $PY models/index/44.evaluate_rolling_oot.py --drop-groups macro_regulation,location,redevelop
& $PY models/index/45.build_conformal_intervals.py
```

원천 수집부터 다시 하는 경우에는 `data/collect/`와 `data/master/` 스크립트가 먼저 실행되어야 한다. API 호출과 DB 적재가 포함되므로 `.env`와 원천 캐시 상태를 먼저 확인한다.

## 간단 검증

환경 설치 후 최소 검증은 다음 순서로 한다.

```powershell
$PY = "models/.venv/Scripts/python.exe"
& $PY -c "import numpy,pandas,scipy,lightgbm,psycopg,pyproj,shapefile,sklearn,statsmodels; print('imports ok')"
& $PY models/index/test_dong_index.py
& $PY models/index/test_realtime_two_stage.py
```

데이터 원천이 없거나 DB 연결이 없으면 전체 파이프라인은 실패할 수 있다. 이 경우 Python 환경 문제가 아니라 입력 데이터 또는 접속 설정 문제로 분리해서 본다.
