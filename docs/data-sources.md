# 데이터 출처와 수집 기준

값을 쓰기 전에 원문으로 확인한 방법까지 적는다. 검색 결과 요약만으로 확인한 값은 쓰지 않는다.
(실제로 검색 요약의 "2022-09-26 서울 전 지역 조정대상지역 해제"는 원문 공고와 달랐다.)

## 1. 실거래 (국토교통부 실거래가 API)

| 항목 | 내용 |
|---|---|
| 엔드포인트 | 매매 `RTMSDataSvcAptTradeDev`(상세, `aptSeq` 포함), 전월세 `RTMSDataSvcAptRent` |
| 기간 | 매매 2006-01~2026-08, 전월세 2011-01~2026-08 |
| 제공 시작 확인 | 2026-09-15 강남구(11680) 실측: 전월세 2006-01 `totalCount` 0, 2011-01 1,603건. 매매 2006-01·2010-01·2015-01·2020-01 모두 `aptSeq` 100% 채워짐 |
| 수집 스크립트 | `data/collect/11.collect_trades.py` — (구, 연월, 종류) JSON 캐시 `output/raw/{sale,rent}/`, 실패 시 재실행하면 이어받음 |
| 산출물 | `output/11.1.trades_sale.txt`, `output/11.2.trades_rent.txt` (git 비추적) |
| 알려진 품질 이슈 | 원장 `sggCd`와 `umdNm`이 서로 다른 구를 가리키는 동 키 6개: `11200_신당동`, `11290_청량리동`, `11305_도봉동`, `11410_길동`, `11590_봉천동`, `11620_사당동`. 단지 번호(`aptSeq`) 앞자리는 실제 소속 구를 가리키며(예: 한진해모로 `11140-1012` → 중구), 구 경계 단지의 신고 구 코드가 다르게 기록된 것으로 보인다. 합계 유효 매매 31건(0.0022%), eligible 분기 0개, 모델 표본(47.2) 0행이라 지수·모델 영향 없음. 법정동 경계와도 매칭되지 않는다(§6) |

## 2. 기준금리 (한국은행)

| 항목 | 내용 |
|---|---|
| 출처 | [한국은행 기준금리 추이(목록)](https://www.bok.or.kr/portal/singl/baseRate/list.do?dataSeCd=01&menuNo=200643) |
| 확인 방법 | 2026-09-15 페이지 HTML을 `output/raw/macro/bok_base_rate.html`로 저장하고, `43`이 표 행을 정규식으로 직접 파싱한다(61행, 1999-05-06 ~ 2026-08-27). 별도로 WebFetch 추출본과 행 수·처음·끝 값이 일치함. 캐시를 지우면 43이 다시 받는다 |
| 사용 | `43.1.gu_macro_regulation.txt`의 분기 말 `base_rate_pct`, 4분기 변화 `base_rate_change_4q` |

## 3. 투기과열지구 (서울 전환점)

| 효력 발생일 | 서울 지정 자치구 | 원문 |
|---|---|---|
| 2006-01-01 (지수 시작) | 25개 구 전 지역 | 2008-11-07 해제가 22개 구를 풀고 강남3구만 남겼으므로 그 전에는 전역 지정 상태다. 최초 지정일은 지수 범위 밖이라 확인하지 않았다 |
| 2008-11-07 | 강남구·서초구·송파구 | [국토부 정책Q&A](https://www.molit.go.kr/USR/policyTarget/dtl.jsp?idx=85): "강남 3구를 제외한 수도권 투기과열지구 전역을 모두 해제하는 고시가 11월 7일 관보에 게재", 해제 대상 "서울 (22개구)" 목록 |
| 2011-12-22 | 없음 | [국토해양부고시 제2011-795호](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=8827&lcmspage=16&psize=10&srch_usr_titl=Y): "해제지역 : 서울특별시 강남구, 서초구, 송파구", "해제일 : 2011년 12월 22일" |
| 2017-08-03 | 25개 구 전 지역 | [정부 공감 2017-08-07](https://gonggam.korea.kr/newsContentView.es?mid=a12502000000&section_id=&content=&code_cd=&news_id=EBC6D401411D4203E0540021F662AC5F): "서울 25개 구 전 지역", "8월 3일부터 즉시 효과가 발생한다". 국토부 행정규칙 목록에 같은 날짜 `투기과열지구 지정` 고시(idx 15117, 첨부 hwp) 존재 |
| 2022-07-05, 2022-11-14 | 변화 없음 (전역 유지) | 국토교통부공고 제2022-882·883호, 제2022-1407·1408호 PDF: 서울 "서울특별시 전역(25개區) → 좌동". 2022-09-26 고시는 첨부 PDF가 없으나 11-14 고시의 변경 전 상태가 전역이므로 서울 변화 없음 |
| 2023-01-05 | 서초·강남·송파·용산 | 국토교통부공고 2023-1호(투기과열)·2023-2호(조정대상) PDF: "지정해제 지역: 서울시 종로구·중구·…", 변경 후 "서초구·강남구·송파구·용산구", "공고한 날부터 효력" |
| 2025-10-16 | 25개 구 전 지역 | [국토부 2025-10-15 주택시장 안정화 대책 원문 PDF](https://www.molit.go.kr/portal/common/download/DownloadMltm2.jsp?FilePath=/upload/portal/DextUpload/202510/20251015_130538_052.pdf&FileName=251015(%EC%84%9D%EA%B0%84)(%EC%95%88%EA%B1%B4)_%EC%A3%BC%ED%83%9D%EC%8B%9C%EC%9E%A5_%EC%95%88%EC%A0%95%ED%99%94_%EB%8C%80%EC%B1%85(%EC%A3%BC%ED%83%9D%EC%A0%95%EC%B1%85%EA%B3%BC).pdf): "강남구 서초구 송파구 용산구 4개구는 유지하고 나머지 21개구를 신규 지정", "(적용시기) 10.16(목) 일자로 지정 및 효력 발생" |

- 국토부 사이트는 세션 쿠키 없이 요청하면 307 리다이렉트가 반복된다. `portal.do`에서 쿠키를 받은 뒤 같은 쿠키로 요청한다
- **조정대상지역은 별도 feature로 두지 않는다.** 원문으로 확인한 서울 전환점(2023-01-05, 2025-10-16)에서 투기과열지구와 범위가 같다. 서울의 조정대상지역 최초 지정일은 2017년 고시 첨부가 hwp라 확인하지 못했다
- **투기지역(기획재정부 소관)은 1차 범위에서 제외**한다
- 원문 파일: `output/raw/regulation/` (git 비추적)

## 4. 정비사업 추진현황 (서울 열린데이터광장)

| 항목 | 내용 |
|---|---|
| 파일 | `output/raw/redevelop/redevelop_2606.xlsx` (2026-06 기준, 496구역) |
| 사용 열 | 2 자치구, 4 대표 지번, 10 기존 가구수, 11 구역지정(최초), 13 추진위원회, 14 조합설립인가, 16 사업시행인가(최초), 18 관리처분계획인가(최초), 22 착공 — 2026-09-15 병합 헤더 확인 |
| 한계 | 한 시점 파일이라 해제·완료되어 목록에서 빠진 구역이 없다(생존 편향). 대표 지번 파싱 실패 4구역은 제외 |

## 5. 임앤장에서 가져온 산출물

2026-09-15 이전 프로젝트에서 서버 복사한 뒤, 새 파이프라인이 쓰는 파일만 남기고 나머지 복사본은 지웠다.
생성 스크립트도 옮겨 이 저장소 안에서 다시 만들 수 있다.

| 파일 | 생성 스크립트 | 비고 |
|---|---|---|
| `output/14.1.geocoded_master.txt`, `output/cache_geocode.json` | `data/master/14.geocode_all.py` | 카카오 지오코딩. 19의 입력 |
| `output/19.1.building_ledger.txt`, `output/raw/ledger/` | `data/collect/19.collect_building_ledger.py` | 건축물대장 표제부. 42 입주 feature |
| `output/raw/reb/apt_registry.csv` | 수동 다운로드 | 한국부동산원 공동주택 단지 식별정보 파일(로그인 없이 받은 CSV). 19의 입력 |
| `output/raw/redevelop/`, `output/raw/regulation/` | `data/collect/35.collect_regulation.py` | 정비사업 추진현황·토지거래허가 원본. 규제 고시 PDF는 직접 받은 원문 |

입지 지표·단지 지표(`23.*`)와 정비사업 단지 매칭(`31.1`)은 쓰지 않는다. 입지·용적률 feature는 결정 14 선별에서 제외됐고, 정비사업은 42가 원천 파일에서 동 단위로 직접 집계한다.

## 6. 법정동 경계 (지도용)

| 항목 | 내용 |
|---|---|
| 출처 | [GIS Developer, 대한민국 최신 행정구역(SHP) 다운로드](http://www.gisdeveloper.co.kr/?p=2332) — 2023년 7월판 `emd_20230729.zip` (SHA-256 `34aa5bc6ee81c79f5a604fc4ff187c6cc4c428f672da21ff6eea8165956655f4`) |
| 원문 설명 | "읍면동의 동은 법정동입니다. 도로명주소 DB의 행정구역도를 기반으로 잘못된 내용을 보완 … 출처를 언급해 주시면 감사하겠습니다." 원본은 도로명주소 DB(juso.go.kr) 17개 행정구역도 취합(작성자 댓글) |
| 좌표계 | GRS80 UTM-K(EPSG:5179), 인코딩 cp949. `52`가 EPSG:4326 GeoJSON으로 변환 |
| 출처 표기 | "행정구역 경계: GIS Developer(gisdeveloper.co.kr), 원본 도로명주소 DB" |
| 산출물 | `output/52.1.seoul_bjd_boundary.geojson`(서울 467개 법정동, 3.8MB), `output/52.2.dong_boundary_match.txt`(지수 346개 동 중 340개 매칭, 6개는 §1 품질 이슈), `front/public/data/dong-boundary.geojson`(53이 지수 동 340개만 줄여서 내보낸 프론트 지도용 파일, 결정 42), `front/public/data/gu-boundary.geojson`(53이 동 경계를 합쳐 만든 자치구 25개 경계, 결정 44) |
| 검토했지만 쓰지 않은 출처 (2026-09-15) | 공공데이터포털 국토지리정보원 읍면동경계(15062310)·공간정보공동활용 읍면동(15123128): 404 / 국가공간정보포털 행정구역_읍면동(법정동): 서버 DNS 해석 실패, 우회 수집 33회 실패 / 서울 열린데이터광장 OA-13221: 2021-07-16 제공 종료, 공공누리 3유형(변경금지) / 서울 데이터허브 법정동 경계: 다운로드가 동적 스크립트라 경로 미확보 / 주소기반산업지원서비스 구역 도형: 목록 페이지 404, 제공은 기관 승인 필요 / VWorld WFS `LT_C_ADEMD_INFO`: 인증키 필요(미보유) / 지오서비스웹 아카이브(2023-12 이후판): 로그인·결제 경로 |
| 52.1 복원 | 원천 SHP가 없어도 `app.dong_boundary`에서 같은 파일을 만들 수 있다(결정 45). active snapshot을 읽어 `output/52.1.seoul_bjd_boundary.geojson`으로 저장한다. `properties`는 `dong`, `sgg_cd`, `emd_cd`, `umd_nm`, `eng_nm`, `in_index` 순서와 무관하게 이름만 맞으면 된다<br>`select json_build_object('type','FeatureCollection','features', json_agg(json_build_object('type','Feature','properties', json_build_object('dong',dong,'sgg_cd',sgg_cd,'emd_cd',emd_cd,'umd_nm',umd_nm,'eng_nm',eng_nm,'in_index',in_index),'geometry',geometry) order by dong)) from app.dong_boundary where snapshot_id = (select snapshot_id from app.dataset_snapshot where is_active limit 1)` |
| 검토했지만 쓰지 않은 것 (2026-09-16) | 행정동 경계 GeoJSON(서울 425개). 자치구 경계로는 쓸 수 있지만 행정동이라 법정동 키와 맞지 않아 동 경계로 쓸 수 없고, `app.dong_boundary`로 법정동 경계를 복원할 수 있게 되어 쓰지 않는다(결정 45) |
| 한계 | 2023-07 기준이다. 서울 법정동 경계는 변경이 드물고 지수 동 340개가 모두 매칭됐지만, 이후 경계 조정은 반영되지 않았다. 최신판이 필요하면 VWorld 인증키나 도로명주소 구역 도형 신청이 필요하다 |

## 7. 미수집

| 항목 | 상태 |
|---|---|
| 교통 호재(역 개통일) | 공공데이터포털 `전국도시철도역사정보표준데이터`에 개통일 항목 없음. 위키백과·미래철도DB 등 2차 출처만 확인. 절단 순서 1순위(handoff §2) |
| 입주 예정 물량 | 미수집. 건축물대장 사용승인일로 과거 준공만 만든다 |
| 주담대 금리 | 한국은행 ECOS API 키 필요 |
