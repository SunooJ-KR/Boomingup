# Boomingup 작업 지침

이 파일은 `README.md`의 협업 규칙을 AI 에이전트가 따라야 할 형태로 정리한 것이다.
규칙이 바뀌면 `README.md`와 `AGENTS.md`를 함께 갱신한다. `CLAUDE.md`는 `@AGENTS.md` 한 줄로 이 파일을 참조하므로 따로 고치지 않는다.

## 언어 규칙

- commit 메시지, PR 설명, 문서, 코드 주석은 모두 한국어로 작성한다.
- 읽는 사람이 바로 이해할 수 있게 쉬운 문장으로 서술한다. 용어만 나열하지 않는다.
- `feat`, `fix`, `docs` 같은 commit type 키워드와 코드, 명령어, 에러 메시지는 원문 그대로 둔다.

## 브랜치

- `main`에 직접 push하지 않는다. 급한 수정도 브랜치와 PR을 거친다.
- 모든 작업은 최신 `dev`에서 분기한 작업 브랜치에서 진행한다.
- 작업 브랜치 → PR → `dev` → build 검증 → PR → `main` 순서를 지킨다.
- GitHub 기본 브랜치는 `main`이다. 작업 브랜치 PR은 base를 `dev`로 직접 지정하고, `dev`를 `main`으로 올릴 때는 base를 `main`으로 둔다.
- `main`에 hotfix가 들어갔으면 `main`을 `dev`로 다시 merge해 두 브랜치를 맞춘다.

브랜치 이름 예시:

```text
feat/front-map-filter
fix/data-geocode-matching
docs/update-project-rules
model/horizon-metrics
```

## 디렉터리

| 경로 | 용도 |
|---|---|
| `data/` | 데이터 수집, 가공, 검증 스크립트 |
| `models/` | 모델, 지표 계산, 예측 관련 코드 |
| `front/` | 프론트엔드 애플리케이션 |
| `docs/` | 기획서, 의사결정, 설계, 발표 자료, mockup 문서 |
| `output/` | 실행 결과, 샘플 산출물 |

- `data/`, `models/`, `front/`에는 실행과 배포에 필요한 소스코드와 설정만 둔다.
- 문서 성격의 파일은 `docs/`에 둔다. 해당 디렉터리 실행 방법을 설명하는 짧은 `README.md`만 예외다.
- `output/`의 큰 파일이나 민감한 파일은 commit하지 않는다.

## Commit

- 작업 단위마다 commit하고, 한 commit에는 하나의 의도만 담는다.
- commit 메시지에는 무엇을 왜 바꿨는지 한국어 문장으로 적는다.
- `update`, `fix`, `작업함`, `최종` 같은 메시지는 쓰지 않는다.

좋은 예시:

```text
feat(front): 지도 검색에 자치구 필터 추가
fix(data): 지오코딩 결과가 없을 때 명시적으로 처리
docs: 협업 워크플로 가이드 문서 추가
model: 단지별 겨울 일조량 점수 계산 로직 추가
```

commit 전 확인:

- 불필요한 임시 파일, 개인 설정, 대용량 산출물이 포함되지 않았는가
- 문서 파일이 `docs/` 밖에 흩어져 있지 않은가
- 실행 코드와 문서 변경이 한 commit에 과하게 섞이지 않았는가
- 한국어로, 다른 사람이 읽고 바로 이해할 수 있게 적었는가

## PR

PR 설명에 최소한 다음을 적는다.

- 변경 요약
- 테스트 또는 확인 방법
- 영향받는 영역: `data`, `models`, `front`, `docs` 등
- 리뷰어가 특별히 봐야 할 부분
- 아직 남은 작업이나 알려진 제한

PR은 작게 유지하고, 여러 영역을 건드리면 영역별로 구분해서 설명한다.

## 검증

`dev`에 merge한 뒤 build를 검증한다. 통과하지 못하면 `main`에 올리지 않는다.

```bash
cd front && npx tsc --noEmit && npm run build
```

## 문서

- 의사결정은 `docs/decisions.md`에 근거와 함께 기록한다.
- 데이터 출처와 수집 기준은 `docs/data-sources.md`에 정리한다.
- 알고리즘과 모델링 판단은 `docs/algorithms.md` 또는 관련 문서에 남긴다.
- 코드 변경으로 사용법, 데이터 스키마, 실행 순서가 바뀌면 관련 문서도 같은 PR에서 갱신한다.
- 화면 문구는 `docs/wording-guide.md`를 정본으로 삼는다. 관측과 전망을 구분하고, 투자 판단이나 지역의 우열로 읽히는 표현을 쓰지 않는다.

## 충돌 방지

- 같은 파일을 크게 수정해야 하면 작업 범위를 먼저 공유한다.
- 공통 인터페이스나 산출물 형식이 바뀌면 영향받는 담당자에게 먼저 알린다.
- `output/` 산출물을 다음 단계가 쓴다면 파일명, 컬럼, 생성 조건을 PR에 명시한다.
