# models/ 작업 지침 (모델·데이터 담당 김용진)

이 파일은 `models/` 폴더 안에서 작업할 때만 적용한다. Codex는 이 파일을 직접 읽고, Claude Code는 같은 폴더의 `CLAUDE.md`(`@AGENTS.md` 한 줄)를 통해 읽는다. 규칙을 바꿀 때는 이 파일만 고친다.
저장소 루트의 `README.md`, `AGENTS.md`, `CLAUDE.md`는 리더가 관리하는 공통 지침이며, 이 폴더에서도 그대로 따른다.
**루트 지침 문서는 수정하지 않는다.** 모델·데이터 작업에만 필요한 규칙은 이 파일에 적는다.

## 진행 관리 (작업 시작 전과 끝난 뒤 반드시)

- 모델 작업을 시작하기 전에 `docs/model-build-process.md`를 먼저 읽는다. 어떤 작업이 `Doing`인지, 지금 Phase 게이트가 어디까지 열렸는지 확인하고, 맡을 작업의 상태를 `Doing`으로 바꾸고 현황판에 담당·시작일을 적는다.
- 작업이 끝나면 같은 문서에서 상태를 `Done`으로 바꾸고 §6 완료 기록에 날짜·산출물·결정 번호를 한 줄 남긴다. 완료 조건을 못 채웠으면 `Done`으로 바꾸지 않고 메모에 남은 일을 적는다.
- 계획 자체를 바꿀 때는 문서를 고치고 `docs/decisions.md`에 이유를 적는다. 계획의 원문은 `docs/model-develope-plan.md`다.
- 이 계획의 새 스크립트는 60번부터 쓴다. 기존 40~52번은 참고용이며 계획의 산출물로 치지 않는다.

## 브랜치

- 최신 `dev`에서 `dev-{작업내용}` 이름으로 브랜치를 만든다 (예: `dev-dong-model`)
- 작업이 끝나면 `dev`로 PR을 올린다. `main`에 직접 올리지 않는다

## 매일 돌릴 것

```bash
.venv/bin/python data/collect/61.snapshot_trades.py
```

최근 6개월 실거래를 조회일별로 남긴다(`output/raw/snapshot/{조회일}/`). 하루치 약 4MB다.
이 기록이 없으면 신고 지연을 보정하는 nowcast(N-1)를 영원히 학습할 수 없다. **하루 거르면
그날의 vintage는 되살릴 수 없다.** 같은 날 다시 돌리면 빠진 것만 이어받고 덮어쓰지 않는다.

## 실행 환경과 순서

- Python: 저장소 루트의 전용 가상환경 `.venv` (Python 3.13). 처음 한 번 만든다:

```bash
python3.13 -m venv .venv && .venv/bin/python -m pip install -r models/requirements.txt
```

- 산출물은 `output/`에 쓰고 커밋하지 않는다. 원천 캐시는 `output/raw/`
- API 키는 저장소 루트 `.env`(chmod 600)에 둔다: `DATA_GO_KR_KEY`(실거래·건축물대장), `KAKAO_REST_KEY`(지오코딩)
- 실행 순서 (저장소 루트에서):

```bash
PY=.venv/bin/python
$PY data/collect/11.collect_trades.py                 # 실거래 수집 (캐시 재사용)
$PY data/master/14.geocode_all.py                     # 단지 좌표 (카카오, output/cache_geocode.json 재사용)
$PY data/collect/19.collect_building_ledger.py        # 건축물대장 표제부 (14.1 + raw/reb 입력, 캐시 재사용)
$PY data/collect/35.collect_regulation.py             # 정비사업 추진현황·토지거래허가 원본
$PY models/index/test_dong_index.py                   # 지수 함수 합성 점검
$PY models/index/40.build_dong_index.py               # target 지수
$PY models/index/41.build_vintage_momentum.py         # 기점별 vintage 지수 (약 30분)
$PY models/index/42.build_dong_features.py            # 보유 데이터 feature
$PY models/index/43.build_macro_regulation.py         # 금리·투기과열지구
$PY models/index/44.evaluate_rolling_oot.py --drop-groups macro_regulation,location,redevelop   # 공식 평가
$PY models/index/45.build_conformal_intervals.py      # 예측 구간
```

- 14·19를 2006~ 원장으로 다시 돌리면 캐시에 없는 단지를 API로 새로 조회하고, 입주 feature(42) 값이 바뀐다. 공식 결과(결정 16·17)와 입력이 달라지므로 재실행하면 결정 기록을 남긴다
- 35가 새 분기 정비사업 파일을 받아도 42는 `raw/redevelop/redevelop_2606.xlsx`를 읽는다. 파일을 바꿀 때는 42의 경로를 함께 바꾼다

## 결정 기록과 결과 표시

- 사전 등록 절차는 폐기했다 (`docs/decisions.md` 결정 18). 조정은 결과를 보면서 하되, 바꾼 내용과 이유를 결정 번호를 이어 기록한다
- 결정 16·17(선별 고정 후 1회 실행한 공식 결과)은 그대로 유효하다. **그 뒤 2016Q1~ 평가 구간을 보며 조정한 수치는 "탐색적 결과"로 표시**하고, 사전 기준으로 검증한 수치처럼 인용하지 않는다
- `44`에서 `--first/last-eval-origin`을 바꾼 실행은 `.trial_*` 파일로 저장된다. 공식 파일(`44.1`, `44.2`)을 덮어쓰는 재실행은 결정 기록과 함께 한다

## 데이터·feature 규칙

- 동 키는 `sggCd` + `umdNm`이다. 법정동 코드 5자리만 쓰지 않는다
- feature는 기점 분기 말까지 공개된 정보로만 만들고 `as_of_quarter`를 둔다. 전체 데이터 지수(40)로 feature를 만들지 않는다
- 서울 전역에 같은 값인 변수(기준금리 등)는 원값을 feature로 쓰지 않는다 (결정 15)
- 외부 값(규제 지정일 등)은 원문으로 확인한 것만 쓰고, 확인 방법을 `docs/data-sources.md`에 적는다. 검색 요약만으로 넣지 않는다
- API 키는 로그에 남기지 않는다 (`mask_key()`)

## 번호와 산출물

- 수집 스크립트 11·14·19·35는 번호를 그대로 쓴다. 다른 스크립트가 `11.1`, `14.1`, `19.1` 같은 산출물 이름으로 읽기 때문이다
- 스크립트 번호는 40번부터 쓴다 (결정 3). `docs/model-build-process.md` 계획의 새 스크립트는 그중 60번부터 쓴다
- 산출물 이름은 `output/{번호}.{순서}.{이름}.txt`, 탭 구분
- 공용 함수는 `_이름.py`, 합성 데이터 점검은 `test_*.py`로 둔다

## 화면 표기 (payload를 만들 때)

- 판단 표현 금지: 저평가/고평가/적정가/싸다/비싸다/유망/추천/투자 적격
- 추정값에는 "추정"과 구간을 붙인다. "80% 보장"이라고 쓰지 않는다
- payload 스키마(`docs/payload-schema.md`)는 정선우 님과 합의한 뒤 바꾼다

## preview 배포 (자동 연동 전까지 수동)

고정 주소 `https://boomingup-preview.vercel.app`이 `dev` 내용을 보여준다. Vercel GitHub App이 저장소에
설치돼 있지 않아 push 자동 배포가 없다(저장소 admin 승인 필요). **`dev`가 바뀌면 직접 배포하고 alias를 다시 건다.**

```bash
git fetch origin && git worktree add -f <작업경로>/dev-tree origin/dev
cp -r front/.vercel <작업경로>/dev-tree/front/.vercel
cd <작업경로>/dev-tree/front
npx vercel deploy --yes --archive=tgz            # 출력의 배포 URL 확인
npx vercel alias set <배포 URL> boomingup-preview.vercel.app
curl -s https://boomingup-preview.vercel.app/api/meta | head -c 200   # source가 db인지 확인
```

- Vercel 프로젝트는 `yjkim-94s-projects/boomingup`, Root Directory는 `front`다
- 환경변수는 Vercel에 등록돼 있다: `DATABASE_READONLY_URL`(Secret), `NEXT_PUBLIC_KAKAO_JS_KEY`(Config, 도메인 제한 공개키)
- `source`가 `sample`로 나오면 환경변수가 빠진 것이다. 값은 저장소 루트 `.env`에서 읽고 출력하지 않는다
- 지도는 카카오 콘솔 JavaScript SDK 도메인에 `boomingup-preview.vercel.app`이 등록돼야 뜬다
- 배포는 `front/`를 바꾸는 일이므로 정선우 님에게 알린다
