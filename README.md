# 산업재해 데이터 분석·RAG 프로젝트

SIF 실제 사고사례를 검색해 유사사례와 예방대책을 출처와 함께 제시하고, 산업재해 통계는 별도 정형 데이터 경로에서 분석하는 프로젝트입니다.

전체 데이터 수집부터 전처리, PostgreSQL 저장, 대시보드·RAG 검색·평가까지의 흐름은 [RAG 설계도](docs/rag-architecture.md)와 [Project_1 통합 서비스 아키텍처](docs/product-architecture.md#project_1-통합-서비스-흐름)를 참고합니다.

## 데이터 구조

새 팀원의 PC 준비와 설치 확인은 [SETUP.md](SETUP.md)를 따릅니다. 현재 검증된 Windows 절차는 PowerShell에서 Python을 실행하고 PostgreSQL Docker 명령은 WSL Ubuntu에서 실행합니다.

- `data/raw/`: 다운로드한 원본 파일. 원본은 수정하지 않습니다.
- `data/processed/`: pandas 전처리 결과와 품질 보고서.
- `src/sif_rag/preprocess_datasets.py`: 정형 통계·용어사전·공개자료 목록 전처리 스크립트.
- `src/sif_rag/load_analytics.py`: 전처리된 통계·용어사전을 PostgreSQL에 적재.
- `src/sif_rag/query_expansion.py`: 용어사전 기반 오프라인 검색어 확장.
- `src/sif_rag/profile_sif_xlsx.py`: SIF 엑셀을 읽기 전용으로 점검하고 본문을 내보내지 않는 프로파일 스크립트.
- `src/sif_rag/profile_sif_api_corpus.py`: 수집한 SIF API JSONL의 필드·중복·본문 길이 품질을 본문 복제 없이 점검합니다.
- `src/sif_rag/prepare_sif_documents.py`: 승인된 SIF API 표본을 출처·업종 metadata를 보존하는 사례 단위 RAG 문서로 정규화합니다.
- `src/sif_rag/rag_cli.py`: API key 없이 BM25 검색, 근거 필드 표시, 출처 인용을 실행하는 로컬 RAG 테스트 CLI입니다.
- `src/sif_rag/vector_store.py`: 승인된 SIF API 문서의 임베딩 적재와 pgvector 의미 검색을 담당합니다.
- `src/sif_rag/search.py`, `collect.py`, `sif_openapi.py`: 기존 검색/API 실험 코드. 로컬 XLSX 파이프라인은 별도 구현 대상입니다.
- `sql/001_sif_cases_pgvector.sql`: SIF 사례 RAG용 PostgreSQL + pgvector 빈 테이블 스키마.

## 저장소 구조

- `src/sif_rag/`: 데이터 수집·전처리·검색·평가 코드
- `apps/streamlit/app.py`: Streamlit 시연 화면
- `apps/accident_assistant/`: SIF/KOSHA 통합 Streamlit 앱과 앱 전용 서비스·의존성·테스트
- `sql/`: PostgreSQL 및 pgvector 스키마
- `scripts/`: 로컬 개발환경 설정 스크립트
- `data/`: 로컬 데이터 위치. 승인되지 않은 원본·수집물·평가 산출물은 저장소에 포함하지 않습니다.
- `docs/`: 아키텍처, 운영 가이드, 데이터 출처와 사용 범위 안내
- `PROJECT_BRIEF.md`: 프로젝트 목표와 범위

데이터 파일별 출처와 현재 확인 상태는 [데이터 출처 안내](docs/data-sources.md), 공개 범위 원칙은 [데이터 안내](data/README.md)를 확인하세요.

원본·수집 JSONL·전처리 산출물·평가 파일은 권한 확인 전까지 Git에 포함하지 않습니다. 필요한 로컬 데이터는 출처 안내에 따라 별도로 준비하세요.


## 저장소 선택

RAG 벡터 저장소는 **PostgreSQL + pgvector**로 사용합니다. 사례 벡터 검색과 metadata 필터를 PostgreSQL에서 처리하고, 통계 데이터 조회도 향후 같은 DB 기반으로 통합할 수 있습니다. 과제 안내의 ChromaDB 스택과 다른 선택이므로 제출 전 대체 허용 여부를 확인합니다.

2026-09-28 SIF 조회 API 연결이 확인되어 기본 키워드 수집을 완료했습니다. `data/raw/sif_openapi_cases.jsonl`에 10개 검색어에서 1,048건을 받았으며 사례 ID 중복과 필수 필드 누락은 없습니다. 이는 키워드 기반 표본이지 전체 아카이브가 아닙니다. 통계 CSV 전처리 결과도 준비되어 있고, 변경금지 조건인 SIF XLSX는 별도 HOLD입니다. 평가 질문 20개는 초안이며 `expected_case_ids` 라벨은 수집 사례를 검토해 채웁니다.

pgvector 스키마를 로컬 PostgreSQL에서 초기화할 때는 서버에 pgvector 확장이 설치되어 있어야 합니다. SQL의 `vector(1536)`은 `text-embedding-3-small` 기준이므로, 임베딩 모델을 바꾸면 벡터 차원도 함께 맞춥니다. 현재 SQL 파일은 빈 구조만 만들며 SIF 파일을 읽거나 적재하지 않습니다.

### 로컬 PostgreSQL 실행

`.env.example`을 `.env`로 복사하고 `POSTGRES_PASSWORD`를 로컬 전용 값으로 설정합니다. `.env`는 Git에 포함하지 않습니다. Docker Compose 명령은 Docker가 연결된 WSL 터미널에서 프로젝트 폴더로 이동해 실행합니다.

```powershell
Copy-Item .env.example .env
docker compose up -d
docker compose ps
```

첫 실행 시 `sql/001_sif_cases_pgvector.sql`이 적용됩니다. 이미 데이터 볼륨이 만들어진 경우 init SQL은 자동 재실행되지 않습니다. DB 준비 상태만 확인할 때는 `docker compose exec postgres pg_isready -U postgres -d industrial_safety`를 사용합니다.

현재 개발 환경에서는 기존 서비스가 5432 포트를 사용 중이라 프로젝트 DB를 5433으로 실행합니다. 포트를 바꿀 때는 `.env`의 `POSTGRES_PORT`와 `DATABASE_URL` 포트를 함께 변경합니다. PostgreSQL 17과 pgvector 0.8.6이 정상 실행되고 `sif_cases` 빈 테이블이 생성된 것을 확인했습니다. SIF 적재와 임베딩은 이용 조건 및 임베딩 API 준비 뒤 진행합니다.

## 전처리 재실행

프로젝트 루트에서 실행합니다.

```powershell
python -m src.sif_rag.preprocess_datasets
```

기본 입력은 `data/raw/`, 출력은 `data/processed/`입니다. 다른 폴더를 사용할 때는 다음처럼 지정합니다.

```powershell
python -m src.sif_rag.preprocess_datasets --input-dir data/raw --output-dir data/processed
```

전처리 결과는 업종·규모별 통계를 tidy long 형식으로 바꾸고, 원본 행과 원본 분류 표기를 보존합니다. 사망만인율 결측값은 0으로 채우지 않습니다. `data/processed/preprocessing_report.md`에서 처리 행 수와 품질 점검 결과를 확인할 수 있습니다.

SIF 구조 점검은 pandas와 openpyxl이 설치된 Python에서 실행합니다.

```powershell
python -m src.sif_rag.profile_sif_xlsx "C:\Users\Lee\Downloads\한국산업안전보건공단_산업재해 고위험요인(SIF) 아카이브_20260401.xlsx"
```

이 프로파일은 시트·필드·행 수와 결측/중복 통계만 저장합니다. 사고 서술 본문은 출력하지 않습니다.

## 용어사전 질의 확장

용어사전은 사고 근거 문서가 아니라 검색 보조자료로만 사용합니다. 질문에 표제어 또는 유의어가 정확히 나타날 때 확장어를 덧붙이며, 원래 질문과 추가된 용어를 함께 반환합니다. 한 글자 약어는 기본적으로 제외합니다. 이 단계는 로컬에서 실행되며 API를 호출하지 않습니다.

```powershell
python -m src.sif_rag.query_expansion "리프트 작업 중 추락을 막는 대책은?"
```

현재 API 코퍼스에 대해 동일 평가 질문으로 기본 검색과 확장 검색의 Hit@k·MRR을 비교할 수 있습니다. 평가 지표를 계산하기 전에 사람이 관련 사례 ID를 검토해야 합니다.

SIF API는 로컬 `.env`의 `DATA_GO_KR_SERVICE_KEY`로 연결합니다. 기본 수집은 10개 seed 검색어 × 검색어당 최대 3페이지(페이지당 최대 100건)이며 검색 중복을 제거합니다. `data/raw/sif_openapi_cases.jsonl`에 현재 1,048건이 수집되어 있습니다. API 라이선스·트래픽 조건은 [공식 서비스 페이지](https://www.data.go.kr/data/15161362/openapi.do)를 확인합니다.

```powershell
python -m src.sif_rag.collect
```

이 수집은 키워드 표본이며 전체 아카이브 덤프가 아닙니다. 이미 수집한 코퍼스에 중복을 제거해 추가합니다.

평가 후보 검토 CSV는 BM25 상위 10개를 질문별로 내보냅니다. `relevance_label`은 자동 지정하지 않습니다. 후보는 판단 보조자료이므로 관련 사례가 후보에 없으면 코퍼스에서 찾아 추가 검토합니다.

```powershell
python -m src.sif_rag.prepare_eval_candidates
```

기본 산출물은 `data/evaluation/rag_candidate_review.csv`입니다. 각 행을 `relevant`, `not_relevant`, `uncertain`으로 판정한 뒤 검토 완료 사례만 평가 질문의 `expected_case_ids`에 반영합니다.

API 코퍼스 품질 프로파일은 다음 명령으로 재생성합니다.

```powershell
python -m src.sif_rag.profile_sif_api_corpus
```

현재 프로파일은 `data/processed/sif_api_corpus_profile.md`에 있습니다. API 결과에서는 `disasterType`이 비어 있고 `cateSeNm`이 `전업종`으로만 나와 이 두 필드는 hard filter로 쓰지 않습니다.

임베딩 전에 사례별 검색 문서 JSONL을 재생성할 수 있습니다. 현재 사례당 검색 본문 최대 길이가 488자라 분할하지 않고 사례 1건을 문서 1개로 유지합니다. 원본 API 필드와 출처는 문서의 `fields`·`metadata`에 보존하며 임베딩은 생성하지 않습니다.

```powershell
python -m src.sif_rag.prepare_sif_documents
```

기본 산출물은 `data/processed/sif_rag_documents.jsonl`입니다.

평가 코퍼스와 평가 질문별 관련 사례 ID 라벨을 준비한 뒤 다음 옵션으로 두 검색 결과를 나란히 산출합니다.

```powershell
python -m src.sif_rag.evaluate --compare-expansion
```

## 전처리 데이터 PostgreSQL 적재

프로젝트 가상환경과 로컬 DB를 준비한 뒤 실행합니다. 적재 스크립트는 통계·장기 추세·용어사전을 별도 정형 테이블에 멱등 방식으로 upsert하며 SIF 본문이나 임베딩은 다루지 않습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.sif_rag.load_analytics
```

현재 DB 적재량은 산업중분류별 통계 1,200행, 장기 추세 220행, 용어사전 7,169행입니다. 재실행 시 동일 키를 갱신합니다.

## 데이터별 사용 구분

- **SIF 아카이브 XLSX:** 유사사고 RAG의 주 사례 데이터입니다. 공식 페이지의 변경금지·2차 저작물 작성 금지 조건을 확인하고, 임베딩·정제본·벡터 DB의 외부 배포 가능 범위를 확인한 뒤 색인합니다.
- **업종·규모별 재해자·사망자·사업장 수·사망만인율:** 대시보드 및 SQL 분석용입니다. 사고사례 벡터 문서와 합치지 않습니다.
- **규모별 2004–2025 사고사망자:** 업종 분류가 없는 장기 추세 보조자료입니다.
- **산업안전 용어사전:** 유의어 기반 검색 확장 실험용이며 사고 근거로 답변하지 않습니다.
- **AI친화 학습데이터 CSV:** 공개 사고자료로 연결되는 URL 목록입니다. 사고보고서 본문 코퍼스가 아닙니다.

## 주요 산출물

- `data/processed/*_tidy.csv`: 정형 통계 long 형식
- `data/processed/15161288_safety_glossary_pairs.csv`: 표제어-유의어 쌍
- `data/processed/15162988_accident_prevention_source_index_clean.csv`: 공개 자료 URL 목록
- `data/processed/sif_api_corpus_profile.md`: SIF API 표본 필드·결측·분포 프로파일
- `data/processed/sif_rag_documents.jsonl`: 사례 ID·원본 필드·출처를 보존한 임베딩 전 문서
- `data/processed/rag_corpus_source_audit.md`: RAG 원문 후보별 이용조건 점검 및 색인 상태
- `data/processed/rag_corpus_permission_request.md`: 제공기관 이용범위 문의 문안(미발송 초안)
- `data/processed/preprocessing_report.md`: 행 수·결측·중복 및 사용상 주의사항
- `data/processed/preprocessing_report.json`: 기계 판독용 요약

## pgvector 의미 검색 준비 및 적재

임베딩 모델은 기본 `text-embedding-3-small`이며 1,536차원 pgvector 스키마와 맞습니다. 작은 표본으로 연결을 확인한 뒤 전체 API 표본을 적재할 수 있습니다. 사례 텍스트를 임베딩 API로 전송하며, `--limit 5`는 5개 사례만 요청합니다.

```powershell
.\.venv\Scripts\python.exe -m src.sif_rag.vector_store --limit 5
```

전체 1,048건을 적재할 때는 `--limit`을 생략합니다. 동일 case ID와 임베딩 모델은 기본적으로 다시 처리하지 않으며, `--force`는 벡터를 재생성합니다. OpenAI 임베딩 API의 Python 사용 예와 기본 차원은 [공식 문서](https://developers.openai.com/api/docs/guides/embeddings)를 참고합니다.

Streamlit 화면의 `의미 검색 (pgvector)`를 선택하면 저장된 임베딩으로 검색합니다. 빈 DB에서는 안내 메시지를 표시하며, BM25 키워드 검색은 계속 독립적으로 사용할 수 있습니다. 이후 같은 라벨 질문으로 BM25·pgvector 결과를 비교하고 검색 오류를 분석합니다.

## 로컬 RAG 테스트 (임베딩 키 없이 실행)

현재 구현은 BM25 사례 검색 후 원문 필드와 출처를 표시하는 로컬 추출형 RAG 프로토타입입니다. 외부 LLM을 호출하거나 답변을 생성하지 않아 OpenAI 키 없이 검색·근거·출처 표시 흐름을 시험할 수 있습니다. 인용 사례가 없으면 근거를 찾지 못했다고 응답합니다.

```powershell
python -m src.sif_rag.rag_cli "지게차 작업 중 보행자 충돌을 예방하려면?"
python -m src.sif_rag.rag_cli "사다리 작업 추락 원인과 감소대책" --expand-query
python -m src.sif_rag.rag_cli "건설 현장의 추락 위험은?" --industry 건설 -k 5
```

For Agent/tool integrations, request structured JSON output:

```powershell
python -m src.sif_rag.rag_cli "지게차 작업 중 보행자 충돌을 예방하려면?" --format json
```

`src/sif_rag.retrieval_tool.search_sif_cases()` accepts `query`, optional `industry`, and `top_k` (1-5). It returns status, ranked case IDs, BM25 scores, evidence fields, and source URLs. Candidates without a case ID or a valid HTTP(S) URL on `data.go.kr` or a subdomain are excluded and reported in `warnings`. Validation checks the official domain and URL structure only; it does not contact the page or confirm that the URL identifies the returned case. Scores are not probabilities, and the corpus is a collected API sample. `tool_schema()` exposes the registration schema.

기본 코퍼스는 `data/processed/sif_rag_documents.jsonl`입니다. 기존 키워드 검색 프로토타입은 API 키 없이 계속 실행할 수 있습니다.

## 생성형 RAG 빠른 실행

`--generate`를 지정하면 BM25 검색 결과를 OpenAI Responses API에 근거로 전달해 한국어 답변을 생성합니다. API 키는 프로젝트 `.env`를 먼저 확인하고, 없으면 `C:\study-with-ai\.env`에서 읽습니다. 키 값은 출력하거나 저장소에 복사하지 않습니다. 기본 모델은 `gpt-6-luna`이며 `OPENAI_MODEL` 또는 `--model`로 바꿀 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.sif_rag.rag_cli "지게차 작업 중 보행자 충돌을 예방하려면?" --generate
```

검색 결과가 없으면 생성 API를 호출하지 않습니다. 모델에는 검색된 사례 필드만 전달하고, 답변 끝에 사례 ID와 원 출처 URL을 함께 표시합니다. 생성 답변은 참고용 초안이며 현장 판단이나 안전관리자 검토를 대체하지 않습니다.

## Streamlit 데모 실행

대화식 화면을 실행합니다. 제출 때마다 선택한 응답 방식에 따라 API를 호출하거나 검색 근거만 표시합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run apps/streamlit/app.py
```

기본 화면은 검색 방식(BM25/pgvector), 업종 대분류 필터, 사례 수, 선택적 용어사전 확장, 생성형 답변/검색 결과 표시를 제공합니다. 화면은 `data/processed/sif_rag_documents.jsonl`을 읽고, 수정 시 로컬 캐시를 갱신합니다.

## 협업 흐름

기능 브랜치에서 작업하고 검토를 위한 Pull Request를 연 뒤 `main`에 반영합니다. 실제 API 키, 비밀번호, 공개 허가가 확인되지 않은 데이터 파일은 커밋하지 않습니다.
