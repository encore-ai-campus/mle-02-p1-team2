# 산업재해 RAG 프로젝트 데이터 수집

최초 수집일: 2026-09-28 (KST)

## 수집 완료

| 파일 | 데이터 | 출처 |
|---|---|---|
| `raw/15084672_industry_size_accident_injured_2025.csv` | 산업중분류·규모별 사고재해자수 | [공공데이터포털 15084672](https://www.data.go.kr/data/15084672/fileData.do) |
| `raw/15084674_industry_size_fatalities_2025.csv` | 산업중분류·규모별 사고사망자수 | [공공데이터포털 15084674](https://www.data.go.kr/data/15084674/fileData.do) |
| `raw/15064487_industry_size_workplaces_2025.csv` | 산업중분류·규모별 사업장수 | [공공데이터포털 15064487](https://www.data.go.kr/data/15064487/fileData.do) |
| `raw/15064491_industry_size_fatality_rate_2025.csv` | 산업중분류·규모별 사망만인율 | [공공데이터포털 15064491](https://www.data.go.kr/data/15064491/fileData.do) |
| `raw/15162988_accident_prevention_ai_dataset_20260917.csv` | 산업재해 사고정보·예방조치 AI친화 학습데이터 | [공공데이터포털 15162988](https://www.data.go.kr/data/15162988/fileData.do) |

파일은 포털에서 받은 원본 바이트 그대로 보관했습니다. CSV는 CP949 인코딩이므로 읽을 때 `encoding="cp949"`를 지정하세요. 파일명만 프로젝트 용도에 맞게 정리했습니다.

## SIF 및 검색 코퍼스 상태

| 데이터 | 출처/로컬 위치 | 현재 상태 |
|---|---|---|
| 산업재해 고위험요인(SIF) 아카이브 | [공공데이터포털 15140383](https://www.data.go.kr/data/15140383/fileData.do); 원본 XLSX는 사용자 Downloads 폴더 | 제조업 등 2,573건과 건설업 3,459건의 시트·컬럼·행 식별자만 읽기 전용으로 프로파일링했습니다. 원본 XLSX는 저장소에 복사하거나 본문을 내보내지 않았습니다. 변경·임베딩 색인 허용 범위가 확인되지 않아 본문 전처리와 색인은 HOLD입니다. 상세 내용은 `processed/sif_source_profile.md` 및 `processed/rag_corpus_source_audit.md`를 확인하세요. |
| SIF 아카이브 조회 OpenAPI | [공공데이터포털 15161362](https://www.data.go.kr/data/15161362/openapi.do); `raw/sif_openapi_cases.jsonl` → `processed/sif_rag_documents.jsonl` | 연결 확인 후 10개 검색어에서 1,048건을 수집했고, 사례 단위 RAG 문서로 정규화했습니다. 고유 사례 ID 1,048개, 중복 0입니다. 키워드 표본이며 전체 아카이브가 아닙니다. |
| 산업안전 현장·법률 용어사전 | [공공데이터포털 15161288](https://www.data.go.kr/data/15161288/fileData.do); `raw/15161288_industrial_safety_terms_20251231.zip` | 수집·전처리 완료. `processed/15161288_safety_glossary_pairs.csv`의 7,169개 용어쌍은 검색어 확장에만 사용하며 사고 근거 코퍼스로 쓰지 않습니다. |
| 산업재해 사고정보·예방조치 AI친화 학습데이터 | `raw/15162988_accident_prevention_ai_dataset_20260917.csv` | 다운로드한 5행 공개자료 경로 목록입니다. 보고서 본문 데이터가 아니므로 RAG 사고사례 코퍼스로 사용하지 않습니다. |

### API 수집 상태

- 사용자가 활용신청 후 재시험을 요청했고 API 연결에 성공해 기본 키워드 수집까지 진행했습니다.
- 공식 페이지에는 이용허락범위 제한 없음, 개발계정 일 1,000회, 운영계정 심의승인으로 표시됩니다.
- 인증키는 채팅에 다시 붙이지 말고 로컬 `.env`에서만 관리합니다. 수집 자료는 `raw/sif_openapi_cases.jsonl`에 있으며 키워드 검색 표본의 한계를 유지합니다.
- pandas 프로파일 결과 `processed/sif_api_corpus_profile.md`에서 `disasterType`이 1,048건 모두 비어 있고 `cateSeNm`이 단일 값(`전업종`)임을 확인했습니다. 이 필드는 업종/재해유형 hard filter로 쓰지 말고, 원본에 없는 재해유형을 추론해 채우지 않습니다.
- 이 API 조건은 API 반환자료에만 적용합니다. SIF XLSX 파일의 이용조건과 임베딩/외부 배포 허용 여부는 별도로 확인하며, 출처별 판정은 `processed/rag_corpus_source_audit.md`가 기준입니다.

## 수집 메모

- 요청에 처음 적힌 규모별 사고사망자 자료(15084663)는 산업중분류가 없어 장기 추세 보조자료로 분리하고, 산업중분류가 포함된 15084674를 주 지표로 수집했습니다.
- 내려받은 통계 파일은 2025-12-31 기준 자료입니다. 산업중분류·규모별 파일은 연간 갱신 데이터입니다.
- 포털 페이지는 오픈 API도 안내하지만, API 호출은 회원 가입 및 활용 신청이 필요하다고 명시합니다. 이번 수집은 인증키 없이 받을 수 있는 파일데이터를 사용했습니다.
- 사고사례 코퍼스가 허용 범위 안에서 확정되기 전까지 사례 본문 전처리·청킹·임베딩·DB 적재를 진행하지 않습니다.
- 포털의 이용 조건은 데이터별 상세 페이지와 제공기관의 명시적 회신을 따릅니다. 파일 이용조건과 API 이용조건은 각각 구분해 기록합니다.
