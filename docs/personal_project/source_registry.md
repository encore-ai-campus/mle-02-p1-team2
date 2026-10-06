# 데이터·API 출처 기록

확인일: 2026-10-02. ①~⑦은 사용자가 지정한 공공데이터포털 자료다. 자료별 이용조건 검토 결과는 [`data_usage_rights.md`](data_usage_rights.md)에 정리했다. `fileData.do`는 **자료 소개·파일 다운로드 페이지**이며 API 요청 주소가 아니다. ②~⑥의 API 주소는 각 페이지의 공식 Swagger 명세에서 확인했다. 2026-09-29에 `.env`의 키로 ②~⑥을 소량 호출해 HTTP 200·응답 구조를 확인했고, 전체 30·30·30·30·5행을 수집했다. 스냅샷과 검증 기록은 개인 데이터 폴더에 둔다.

| 번호 | 사용 단계 | 자료명·공식 페이지 | 받은 원본 | API 주소·키 변수 | 주의 |
| --- | --- | --- | --- | --- | --- |
| ① | SIF 심층분석·RAG 후보 | [KOSHA SIF 아카이브](https://www.data.go.kr/data/15140383/fileData.do) | `data/personal/raw/source_01/source_01_sif_archive.xlsx` | 파일만 확인, 키 없음 | 2016~2023 사례. 공공누리 제3유형(출처표시·변경금지). 전처리·청킹·임베딩·LLM 전송·RAG 노출 범위 확인 필요. 원본 XLSX는 수정하지 않음 |
| ② | Dashboard 사고재해자 | [산업중분류별 규모별 사고재해자수](https://www.data.go.kr/data/15084672/fileData.do) | `data/personal/raw/source_02/source_02_accident_injured.csv` | `https://api.odcloud.kr/api/15084672/v1/uddi:8a4523d3-816b-4eb0-ad2f-9d88d5895e71` · `SOURCE_02_ACCIDENT_INJURED_API_KEY` | CSV 30행, CP949. 포털 이용허락범위 제한 없음. OpenAPI 활용신청은 별도 |
| ③ | Dashboard 사고사망자 | [산업중분류별 규모별 사고사망자수](https://www.data.go.kr/data/15084674/fileData.do) | `data/personal/raw/source_03/source_03_accident_deaths.csv` | `https://api.odcloud.kr/api/15084674/v1/uddi:6b3e32f7-6431-4a2f-978a-e207b058ae1d` · `SOURCE_03_ACCIDENT_DEATHS_API_KEY` | CSV 30행, CP949. 포털 이용허락범위 제한 없음. OpenAPI 활용신청은 별도 |
| ④ | Dashboard 사업장 수 | [산업중분류별 규모별 사업장수](https://www.data.go.kr/data/15064487/fileData.do) | `data/personal/raw/source_04/source_04_establishments.csv` | `https://api.odcloud.kr/api/15064487/v1/uddi:d8b9a405-5ec5-445f-b1d1-99484da54212` · `SOURCE_04_ESTABLISHMENTS_API_KEY` | CSV 30행, CP949. 포털 이용허락범위 제한 없음. 사업장 수는 사망만인율의 분모가 아님 |
| ⑤ | Dashboard 사망만인율 | [산업중분류별 규모별 사망만인율](https://www.data.go.kr/data/15064491/fileData.do) | `data/personal/raw/source_05/source_05_fatality_rate.csv` | `https://api.odcloud.kr/api/15064491/v1/uddi:041d50b2-e50a-4bdd-95d9-bae6bdf4cee2` · `SOURCE_05_FATALITY_RATE_API_KEY` | CSV 30행, CP949. 포털 이용허락범위 제한 없음. 정의는 임금근로자 1만 명당 사망자 수로, ③ 사고사망자수 및 ④ 사업장수를 사용한 재계산 지표와 다름. 분자·분모·기간 확인 |
| ⑥ | RAG 문서 출처 목록 | [고용노동부 사고정보·예방조치 AI친화 학습데이터](https://www.data.go.kr/data/15162988/fileData.do) | `data/personal/raw/source_06/source_06_rag_source_index.csv` | `https://api.odcloud.kr/api/15162988/v1/uddi:6aad2c14-2c8e-4381-bc3b-9397ffe99a03` · `SOURCE_06_RAG_SOURCE_INDEX_API_KEY` | UTF-8 CSV 5행은 URL 안내 목록이지 보고서 본문이 아님. 포털은 AI유형을 선택했으나 실제 공공저작물은 제3유형으로 이용하고 원문 PDF·사이렌은 조건을 따로 확인하라고 안내. 보관한 조사보고서 PDF 3개에 제3유형이 적용되는지, PDF 청킹·임베딩·외부 LLM 전송·RAG 인용 가능 범위를 문의 초안에 정리 |
| ⑦ | 검색어 확장 실험 | [산업현장 법률용어 정의 데이터](https://www.data.go.kr/data/15161288/fileData.do) | `data/personal/raw/source_07/source_07_safety_terms.zip` 및 압축 해제 CSV 2개 | 파일만 확인, 키 없음 | 포털 표기는 CSV이나 실제 파일은 ZIP. 사전 5,751행·검색어 103행(헤더 제외). 포털 이용허락범위 제한 없음 |
| ⑧ | RAG 공식 지침 | KOSHA GUIDE | `data/personal/raw/source_08/` · 사용자가 준 ZIP 2개, README, 색인 CSV, PDF 18개 | API 키 없음 | PDF 해시 18개를 색인과 대조. 549쪽 중 텍스트 부족 101쪽, `A-G-2-2025` 전쪽 OCR 필요. 개별 이용허락 유형을 확인하지 못해 공개·재배포·외부 임베딩 범위는 기관 문의 필요 |

원본 수집 기록과 SHA-256은 `data/personal/raw/download_manifest.csv`에 있다. 원본 파일은 개인 작업 폴더에서 Git 제외된다. 팀과 원본 또는 가공물을 공유하기 전 각 자료의 이용조건을 재확인한다.

## API 키 규칙

②~⑥은 **각 API별 키 변수 이름만** `.env.example`에 마련했다. 실제 키는 본인 `.env`에 입력한다. 같은 서비스 키가 여러 API에서 허용되면 여러 변수에 같은 값을 넣어도 된다. 한 자료가 기간별 API로 나뉘고 서로 다른 키를 받으면 `SOURCE_03_ACCIDENT_DEATHS_2024_API_KEY`처럼 파일명·기간을 반영한 변수와 출처표의 행을 추가한다. API 키 자체는 문서·노트북·수집 로그에 남기지 않는다.

공식 Swagger는 각 자료의 `https://infuser.odcloud.kr/oas/docs?namespace=<자료번호>/v1`에 있다. 현재 경로는 2026-09-29 확인된 최신 파일의 UUID다. `page`, `perPage`, `serviceKey` 소량 호출과 전체 수집을 검증했다. 이후 기간별 이전 파일의 UUID와 자료 기준연도도 확인한다.

②~⑤의 현재 포털 파일명은 모두 `_20251231`로 끝난다([②](https://www.data.go.kr/data/15084672/fileData.do), [③](https://www.data.go.kr/data/15084674/fileData.do), [④](https://www.data.go.kr/data/15064487/fileData.do), [⑤](https://www.data.go.kr/data/15064491/fileData.do)). CSV 본문에 기준일 열이 없으므로 M2 전처리 노트북은 원본 4개 SHA-256을 수집 기록과 대조한 뒤 기준일 `2025-12-31`을 붙인다. 이후 포털 파일이 갱신되면 파일명·기준일·해시를 함께 갱신한다.

## 분석 전 확인

- ②~⑤는 같은 업종·규모·기준연도인지 확인한 뒤 결합한다. 각 파일의 `대업종`, `구분` 등 실제 열을 기준으로 키를 정한다.
- ④ 사업장 수로 사고 건수를 나눈 값은 별도 정의의 사업장당 사고 지표다. ⑤ 사망만인율을 재계산하려면 공식 근로자 수와 정의가 필요하다.
- ① XLSX에는 안내 시트와 제조업 등·건설업 시트가 있어 헤더 행을 확인한 뒤 읽는다.
- ⑥의 5행 자체를 RAG 본문으로 취급하지 않는다. 실제 보고서·사이렌 문서별 원본 URL, 게시일, 저작권을 따로 기록한다.

## M0·M1 실제 검증 기록 (2026-09-29)

- ①~⑦ 다운로드 원본의 SHA-256이 매니페스트와 일치했다.
- ②~⑥ API는 각각 HTTP 200이었고 응답 열과 파일 열이 일치했다. 전체 수집량은 ②~⑤ 각 30행, ⑥ 5행이다.
- API 스냅샷과 내려받은 CSV의 행 내용도 일치했다. ⑤ 사망만인율은 API의 `0.30` 문자열과 CSV의 `0.3` 숫자처럼 표기 형식이 달라 수치로 정규화해 비교했다. 양쪽에 결측 14칸이 같다.
- `data/personal/reports/m0_source_validation.json`, `m1_collection_summary.json`, `data/personal/raw/api_collection_log.csv`에서 재현 기록을 확인할 수 있다. 이 파일들은 개인 작업 자료이며 Git에서 제외된다.

## 개인 작업에서 추가 확인한 RAG 자료 (2026-10-01)

- ⑥의 CSV 5행은 보고서 본문이 아니다. 고용노동부 [재해조사보고서 목록](https://moel.go.kr/info/dsstExaminRpt/list.do)에서 실제 PDF 3개를 골라 원본·SHA-256·게시 URL을 `source_06/reports/manifest.csv`에 남겼다. 현재 공식 다운로드 ZIP의 PDF 3개가 보관본과 바이트 단위로 일치하며, 게시일 2026-05-26은 사고 발생일과 구별한다.
- ⑧은 사용자가 준 `kosha_1.zip`, `kosha_2.zip`을 원본으로 보관하고 18개 PDF를 풀었다. `kosha_guide_index.csv`의 PDF 해시를 전부 검증했다. 18개 공식 다운로드 URL의 응답도 현재 보관본과 바이트 단위로 일치했다.
- ① 6,032건 + ⑥ 3건 + ⑧ 18건을 6,053개 문서로 등록했다. PDF 총 578쪽 중 글자가 거의 안 나온 105쪽(⑥ 4쪽, ⑧ 101쪽)은 제외했고 6,731개 청크를 만들었다. 특히 `A-G-2-2025`는 검색되지 않는다.
- ⑦의 5,751행 유의어 사전은 M7의 장비 표현 확장 실험에 썼다. 검색 문항 10개와 결과는 `data/personal/evaluation/`에 보관한다.


## M0·M1 재검증 기록 (2026-10-03)

- `00_M0_주제_API_확정.ipynb`와 `01_M1_API_데이터수집.ipynb`를 현재 프로젝트 환경에서 다시 실행했다. ②~⑤는 각 30행, ⑥은 5행을 수집했다. 2026-10-03 재검증에서 다섯 API 모두 정상 응답했고 API 결과의 열·전체 행이 포털 CSV와 일치했다. 키 값은 기록하지 않았다.
- M1 수집 요약에는 실패 원인이 남고 `required_complete`는 false다. ③ 로컬 CSV와 2026-10-01에 검증했던 30행은 보존했지만, 이번 재호출 성공으로 간주하지 않는다. 새 키를 적용한 뒤 ③을 포함해 전체 수집을 다시 확인한다.
- 공식 ① 소개 페이지는 로컬 파일을 받은 2026-09-29 다음 날인 2026-09-30 수정됐고 파일명은 `_20260401`로 표시된다. 페이지의 메타데이터 전체 행은 6,069, 설명 본문의 사례 수는 6,032(2016~2023년)다. 로컬 XLSX에서는 6,032건을 전처리했다. 전체 행과 사례 건수는 집계 기준이 다를 수 있으므로 숫자 차이만으로 파일 갱신 또는 오류를 단정하지 않는다. 2026-10-03 공식 페이지의 최신 표시 파일을 별도로 내려받아 로컬 XLSX와 크기(1,431,108바이트) 및 SHA-256이 같은 것을 확인했다. 비교 기록은 `data/personal/reports/sif_latest_compare.json`이다. 포털 메타데이터 전체 행 6,069와 설명상 사례 6,032의 차이는 기준 정의가 확인되지 않아 별도 표기한다.
- 원문 재해개요 앞부분에서 2016~2023년 범위 밖으로 해석되는 연도 54건(2013~2015년 53건, 2024년 1건)이 관찰됐다. 이는 원문 서술에서 추출한 연도이지 공식 발생연도 검증 결과가 아니다. 발표 때는 기간 추세를 확정적으로 말하지 않는다.
- ①·⑥의 표시된 이용조건은 출처표시·변경금지다. 개인 수업 작업에서의 내부 분석과 외부 공개·변형·임베딩·LLM 입력의 허용 범위가 모두 같다고 가정하지 않는다. 현재 문의 초안은 미발송이고 팀 프로젝트 외부에 연락하지 않았다.
