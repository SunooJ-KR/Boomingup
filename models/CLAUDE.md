# models/ 작업 지침 (모델·데이터 담당 김용진)

이 파일은 `models/` 폴더 안에서 작업할 때만 적용한다. 저장소 루트의 `README.md`, `AGENTS.md`, `CLAUDE.md`는 리더가 관리하는 공통 지침이며, 이 폴더에서도 그대로 따른다.
**루트 지침 문서는 수정하지 않는다.** 모델·데이터 작업에만 필요한 규칙은 이 파일에 적는다.

## 브랜치

- 최신 `dev`에서 `dev-{작업내용}` 이름으로 브랜치를 만든다 (예: `dev-dong-model`)
- 작업이 끝나면 `dev`로 PR을 올린다. `main`에 직접 올리지 않는다

## 실행 환경과 순서

- Python: `/home/yjkim/test/imnjang/.venv/bin/python` (Python 3.13, pandas·scipy·lightgbm)
- 산출물은 `output/`에 쓰고 커밋하지 않는다. 원천 캐시는 `output/raw/`
- 실행 순서 (저장소 루트에서):

```bash
PY=/home/yjkim/test/imnjang/.venv/bin/python
$PY data/collect/11.collect_trades.py                 # 실거래 수집 (캐시 재사용)
$PY models/index/test_dong_index.py                   # 지수 함수 합성 점검
$PY models/index/40.build_dong_index.py               # target 지수
$PY models/index/41.build_vintage_momentum.py         # 기점별 vintage 지수 (약 30분)
$PY models/index/42.build_dong_features.py            # 보유 데이터 feature
$PY models/index/43.build_macro_regulation.py         # 금리·투기과열지구
$PY models/index/44.evaluate_rolling_oot.py --drop-groups macro_regulation,location,redevelop   # 공식 평가
$PY models/index/45.build_conformal_intervals.py      # 예측 구간
```

## 사전 등록 규율

- target·평가·채택 기준은 `docs/decisions.md` 결정 4~15가 정본이다. **결과를 본 뒤 규칙을 바꾸면 원래 규칙을 지우지 않고 deviation 표에 적고, 두 결과를 함께 보고한다**
- 공식 판정은 `44`의 기본 평가 구간(2016Q1~)으로 한 번만 한다. `--first/last-eval-origin`을 바꾼 실행은 `.trial_*` 파일로 저장되며 판정에 쓰지 않는다
- feature 선별은 2014Q1~2015Q4 기점에서만 한다 (결정 14)

## 데이터·feature 규칙

- 동 키는 `sggCd` + `umdNm`이다. 법정동 코드 5자리만 쓰지 않는다
- feature는 기점 분기 말까지 공개된 정보로만 만들고 `as_of_quarter`를 둔다. 전체 데이터 지수(40)로 feature를 만들지 않는다
- 서울 전역에 같은 값인 변수(기준금리 등)는 원값을 feature로 쓰지 않는다 (결정 15)
- 외부 값(규제 지정일 등)은 원문으로 확인한 것만 쓰고, 확인 방법을 `docs/data-sources.md`에 적는다. 검색 요약만으로 넣지 않는다
- API 키는 로그에 남기지 않는다 (`mask_key()`)

## 번호와 산출물

- 새 스크립트 번호는 40번부터 쓴다. 임앤장에서 복사한 `output/01.*`~`37.*`와 겹치지 않게 하기 위해서다 (결정 3)
- 산출물 이름은 `output/{번호}.{순서}.{이름}.txt`, 탭 구분
- 공용 함수는 `_이름.py`, 합성 데이터 점검은 `test_*.py`로 둔다

## 화면 표기 (payload를 만들 때)

- 판단 표현 금지: 저평가/고평가/적정가/싸다/비싸다/유망/추천/투자 적격
- 추정값에는 "추정"과 구간을 붙인다. "80% 보장"이라고 쓰지 않는다
- payload 스키마(`docs/payload-schema.md`)는 정선우 님과 합의한 뒤 바꾼다
