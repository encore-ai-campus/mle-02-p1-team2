<div align="center">

# 🛡️ Preventra

### 현장의 질문에, 근거로 답하다.

**산업재해 사례 · 안전보건 지침 · 산업재해 통계 · 작업계획서를 한곳에서**

작업자는 필요한 안전 정보를 질문하고,<br>
관리자는 계획서를 연결해 오늘의 작업과 확인할 사항을 살펴봅니다.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.64-FF4B4B?logo=streamlit&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL%20%2B%20Storage-3ECF8E?logo=supabase&logoColor=white)
![RAG](https://img.shields.io/badge/RAG-SIF%20%2B%20KOSHA-2563EB)
![Langfuse](https://img.shields.io/badge/Observability-Langfuse-334155)

**[🔗 데모 바로가기](https://preventra-final-v2.streamlit.app/)** · **[📊 검색 품질 평가](#9-검색-품질-평가)** · **[🚀 로컬 실행](#7-실행-방법)**

📊 발표자료: 추가 예정 · 📓 팀 노션: 추가 예정

</div>

---

## 1. 프로젝트 소개

> 산업안전 공공데이터를 수집·분석하고, 출처를 함께 확인하는 **RAG 챗봇**과 **작업계획 분석 보고서**를 하나의 Streamlit 앱으로 제공합니다.

### 우리가 해결하고 싶은 문제

작업 전 확인해야 할 정보는 사고사례, 안전지침, 통계, 현장 계획서에 흩어져 있습니다. 자료가 많아도 **지금 하는 작업에 어떤 내용이 필요한지**, **그 답변의 근거가 무엇인지**를 확인하는 데 시간이 걸립니다.

Preventra는 사용자의 질문과 작업 맥락에 맞는 자료를 찾아 간결하게 답하고, 원문 출처로 이어줍니다. 관리자는 Excel 작업계획서에서 날짜별 일정과 확인 사항을 살펴본 뒤 같은 맥락으로 질문을 이어갈 수 있습니다.

| 항목 | 내용 |
| --- | --- |
| 프로젝트 기간 | **2026.10.02–2026.10.07** |
| 팀 | **이현근 · 주승우 · 김수연 · 송수림** / 4명 |
| 대상 사용자 | 현장 작업자, 안전관리자, 작업 전 교육 담당자 |
| 핵심 방향 | 사용자가 궁금한 정보를 간결하게 제공하고, 답변에 사용한 근거를 확인할 수 있게 하기 |
| 이 문서의 앱 기준 | **Preventra Plus v3** · `src_v3/Project_1/preventra_plus.py` · 커밋 `63e6250` |

> 안전 정보 검토를 돕는 도구입니다. 현장 위험성평가와 안전관리자의 판단을 대신하지 않습니다.

## 2. 데모

[![Preventra 배포 홈 화면](docs/images/home.png)](https://preventra-final-v2.streamlit.app/)

**하나의 홈, 두 가지 사용 흐름**

| 작업자 | 관리자 |
| --- | --- |
| 작업 상황을 입력하고 사고사례·점검사항·통계를 질문합니다. | Excel 작업계획서를 연결하고 날짜·작업을 선택합니다. |
| 답변에 사용된 근거와 출처를 확인합니다. | 작업 요약·일정·확인 후보·사고사례 보고서를 확인합니다. |
| 사이드바에서 이전 대화를 이어갑니다. | 사이드바의 **현장명 → 날짜**에서 작업 기록과 상담을 이어갑니다. |

| 관리자 · 작업별 사고사례 보고서 | 관리자 · 계획서 후속 질문 UI |
| --- | --- |
| <img src="docs/images/dashboard.png" alt="작업별 사고 유형 도넛 그래프와 사례 출처" width="620"> | <img src="docs/images/chat.png" alt="계획서 맥락을 연결한 질문과 답변 화면" width="390"> |

<sub>홈은 2026-10-07 배포 화면입니다. 보고서는 최신 v3 로컬 검증 화면으로, 가상 현장 계획서와 연결된 SIF 자료를 사용했습니다. 대화 이미지는 화면 검증용 예시 응답이며, 검색 성능을 증명하는 결과는 아닙니다. 배포 URL의 실행 버전과 이 문서의 코드 기준은 다를 수 있습니다.</sub>

### 이렇게 질문해 보세요

- **사고사례:** “지게차 작업 중 보행자 충돌 사고사례를 알려줘.”
- **작업 전 점검:** “비계 해체 작업 전에 확인할 사항은?”
- **통계:** “2025년 건설업 사고사망자 수를 알려줘.”
- **계획서 연결 후:** “오늘 오전 작업에서 계획서에 적힌 안전조치를 정리해 줘.”
- **후속 질문:** “그중 창호 자재 반입은 몇 시부터 몇 시까지야?”

관리자 상담에서 ‘오늘·오전·내일’은 기본적으로 **화면에서 선택한 계획 날짜**를 기준으로 해석합니다.

## 3. 주요 기능

| 기능 | 무엇을 할 수 있나요? | 구현 포인트 |
| --- | --- | --- |
| 💬 근거 기반 안전 상담 | 사고사례, 작업 전 확인 사항, 통계에 대한 자연어 질문 | 단일 Agent가 요청에 필요한 도구를 선택 |
| 🔎 SIF 사고사례 검색 | 실제 유사 사고의 경위·원인과 원본 출처 확인 | 키워드 검색 + 벡터 검색 + LLM 재정렬 |
| 📚 KOSHA GUIDE 검색 | 작업방법·점검·예방조치의 문서·페이지·절 확인 | 질문 맥락과 문서 메타데이터를 함께 반영 |
| 📈 질문에 맞춘 통계 | 연도·업종·규모 조건의 수치와 추세 그래프 확인 | 정형 CSV 조회, 결측과 실제 0 구분 |
| 📋 작업계획서 연결 | Excel 업로드 후 날짜별 작업·장비·안전조치 확인 | 팀원 작성 파서 재사용, 원본 시트·행 보존 |
| 🍩 자동 사고사례 보고서 | 작업별 사례 수·사고 유형 그래프·전체 일치 사례 탐색 | 건설업 SIF 키워드 집계, 비동기 조회·캐시 |
| 🗂️ 대화·계획 이력 | 작업자 대화와 관리자 현장·날짜별 기록 복원 | Supabase PostgreSQL에 대화와 계획 스냅샷 저장 |
| 🔗 출처 확인·실행 추적 | 답변 근거 확인, 도구 호출과 오류 흐름 점검 | 출처 ID 검증, 선택적 Langfuse Cloud 추적 |

### 자동 보고서와 대화 검색의 역할

**계획 보고서**는 업로드한 내용으로 먼저 구성합니다. 작업 일정, 계획된 안전조치, 누락 항목과 겹치는 작업의 확인 후보를 보여주고, 사고 자료가 준비되면 그래프를 자동으로 연결합니다.

**사고사례 보고서**는 팀원의 집계 규칙을 재사용합니다. 작업명·단위작업 키워드를 먼저 확인하고, 해당 후보가 없으면 장비 키워드를 확인합니다. 5건 이상 일치하는 키워드 중 가장 적게 일치하는 것을 선택하며, 사례는 10건씩 넘겨 전체를 볼 수 있습니다.

**대화 검색**은 질문에 맞는 후보를 재정렬해 도구 호출당 최대 3건을 반환합니다. 최종 답변에는 Agent가 인용한 근거를 표시합니다. 보고서의 사례 수는 **키워드 일치 빈도**이며, 현장의 사고 확률이나 개별 사례의 적합성 순위로 해석하지 않습니다.

<details>
<summary><strong>데이터와 답변을 다루는 원칙</strong></summary>

- 사고 경위는 SIF, 점검·예방조치는 KOSHA GUIDE, 수치는 통계 도구에서 확인합니다.
- 근거 부족, 조회 실패, 통계의 실제 0을 구분하도록 구성했습니다.
- 원자료에 없는 수치나 누락 연도를 임의로 채우지 않습니다.
- 사망만인율은 분모 없이 단순 합산·평균하지 않습니다.
- 계획서에 기재된 안전조치와 외부 자료에서 확인한 기준을 구분합니다.
- 출처 식별자를 검증하더라도 내용의 관련성까지 보장되는 것은 아니므로, 별도의 검색·답변 평가를 수행합니다.

</details>

## 4. 아키텍처

아래는 최신 **Preventra Plus v3**의 실행 흐름입니다. 보고서 집계와 대화 검색은 목적에 맞는 경로를 각각 사용합니다.

```mermaid
flowchart TB
    APP["Streamlit · preventra_plus.py"] --> WORKER["작업자 질문"]
    APP --> MANAGER["관리자 · 계획서 연결"]
    MANAGER -->|"날짜·작업 맥락"| AGENT["SafetyAgent<br/>답변 · 근거 · 그래프"]
    WORKER --> AGENT
    AGENT --> TOOLS["SIF · GUIDE · 통계 Tool<br/>관리자 get_work_plan"]
    TOOLS --> DB[("Supabase PostgreSQL<br/>pgvector · 검색 데이터")]
    TOOLS --> STORAGE[("Supabase Storage<br/>통계 CSV")]
    AGENT <--> LLM["OpenAI<br/>모델·도구 연동"]
    AGENT -. "선택적 추적" .-> TRACE["Langfuse Cloud"]
    MANAGER --> REPORT["계획 보고서 먼저 표시<br/>요약 · 일정 · 확인 후보"]
    REPORT --> CASES["비동기 사고사례 집계<br/>작업별 도넛 · 전체 사례"]
    CASES -->|"건설업 메타데이터"| DB
    APP <--> HISTORY[("Supabase PostgreSQL<br/>대화 · 계획 이력")]
    classDef entry fill:#eaf2ff,stroke:#3b82f6,color:#16365d;
    classDef data fill:#eafaf3,stroke:#20a779,color:#14543d;
    classDef report fill:#fff7e8,stroke:#dca344,color:#714d19;
    class APP,AGENT entry;
    class DB,STORAGE,HISTORY data;
    class REPORT,CASES report;
```

| 기능 | 담당 파일·모듈 |
| --- | --- |
| 화면·상태·대화 연결 | `preventra_ui_v2/`, `preventra_ui/state.py`, `gateway.py` |
| Agent·도구·추적 | `preventra_agent/agent.py`, `tools.py`, `observability.py` |
| 검색·통계 | `services/safety_rag.py`, `sif_retrieval.py`, `statistics.py` |
| 계획 파싱·후속 질문 | `preventra_plan/vendor/work_plan.py`, `domain.py`, `agent.py` |
| 계획·사고사례 보고서 | `preventra_plan/report.py`, `case_catalog.py`, `case_report.py`, `vendor/case_summary.py`, `vendor/briefing_report.py` |
| 대화·계획 저장 | `preventra_ui/history.py`, `preventra_plan/storage.py` |

관리자 Agent에는 계획 내용을 조회하는 `get_work_plan`이 추가됩니다. OpenAI는 답변 생성·임베딩·SIF 재정렬에 사용하고, Langfuse는 설정했을 때 모델·도구 호출을 추적합니다. 통계는 Storage를 우선 조회하며, 실패 시 같은 DB의 기존 2025 통계를 대체 경로로 사용합니다.

### 검색 경로

| 경로 | 후보 생성·선택 | 반환 |
| --- | --- | --- |
| **SIF** | IDF 가중 키워드 후보 10건 + 벡터 후보 10건 → 중복 제거·RRF 순위 결합 → LLM 재정렬 | 관련성 기준을 적용해 최대 3건. 재정렬 실패 시 통합 순위 사용 |
| **KOSHA GUIDE** | 벡터 후보 최대 40건 → 카테고리·장비·작업·위험·절 기반 점수 조정 → 절 다양성 반영 | 최대 3건 |
| **산업재해 통계** | 지표·연도·산업중분류·규모 조건으로 정형 데이터 조회 | 수치·집계 조건·출처·Plotly 그래프 |
| **계획서 보고서** | 건설업 SIF 메타데이터에 작업·장비 키워드 적용 | 일치 집합의 유형 분포와 전체 사례 목록 |

SIF의 키워드 점수는 **IDF 가중 문자열 일치**이며 BM25 구현으로 표기하지 않습니다. v3의 공용 서비스는 `src_v3/Project_1/services/` 안에 있어 이전 앱 폴더를 실행 경로에 추가하지 않습니다.

## 5. 기술 스택

| 구분 | 사용 기술 | 프로젝트에서의 역할 |
| --- | --- | --- |
| 언어 / 환경 | Python **3.12**, uv | 환경·의존성 관리 |
| 데이터 처리 | pandas, NumPy, openpyxl | 통계 정규화, 작업계획서 파싱, 집계 |
| 앱 / 시각화 | Streamlit **1.64.0**, Plotly, HTML·CSS·SVG | 역할별 화면, 대화 UI, 일정·사고 유형 그래프 |
| Agent | LangChain, Pydantic | 도구 선택, 입력·최종 응답 구조 검증 |
| LLM | OpenAI **`gpt-6-luna`** — 코드 기본값 | Agent 답변, SIF 후보 재정렬 |
| 임베딩 | OpenAI **`text-embedding-3-small`**, **1,536차원** | SIF·KOSHA 의미 검색 |
| 검색 / 저장 | PostgreSQL, pgvector, psycopg, Supabase | 검색 데이터와 대화·계획 스냅샷 저장 |
| 통계 파일 | Supabase Private Storage | 연도별 CSV 읽기 |
| 관찰 | Langfuse Cloud | 모델·도구 실행 추적과 오류 분석 |
| 협업 / 배포 | GitHub, Notion, Streamlit Community Cloud | 브랜치 기반 협업, 평가 기록, 앱 제공 |

앱의 정확한 패키지 버전은 [`src_v3/Project_1/requirements.txt`](src_v3/Project_1/requirements.txt)에 고정되어 있습니다. `PREVENTRA_CHAT_MODEL`은 Agent 모델을 변경하는 선택 설정이며, SIF 재정렬 모델은 `services/safety_rag.py`의 기본값을 사용합니다.

## 6. 데이터

### 출처와 범위

| 데이터 | 확인한 규모·범위 | 사용 목적 | 출처 |
| --- | --- | --- | --- |
| **SIF 고위험요인 아카이브** | 제조업 등 **2,573건** + 건설업 **3,459건** = **6,032건** | 사고사례 검색, 관리자 작업별 집계 | [공공데이터포털](https://www.data.go.kr/data/15140383/fileData.do) |
| **KOSHA GUIDE** | 수집 기록 기준 **18개 PDF**. 실제 검색 가능 범위는 적재·OCR 상태에 따름 | 작업방법·점검·예방조치 근거 | [수집·출처 기록](docs/personal_project/source_registry.md) |
| **사고재해자수** | 앱 파일 매핑 기준 **2020–2025년** | 업종·규모별 수치와 추세 | [공공데이터포털](https://www.data.go.kr/data/15084672/fileData.do) |
| **사고사망자수** | 앱 파일 매핑 기준 **2020–2025년** | 업종·규모별 수치와 추세 | [공공데이터포털](https://www.data.go.kr/data/15084674/fileData.do) |
| **사업장수** | **2025년**, 30개 업종 × 10개 규모 | 정형 통계 자료 | [공공데이터포털](https://www.data.go.kr/data/15064487/fileData.do) |
| **사망만인율** | **2020·2022–2025년**, 2021년 파일 미제공 | 단일 업종·규모의 원자료율 조회 | [공공데이터포털](https://www.data.go.kr/data/15064491/fileData.do) |
| **사용자 작업계획서** | 업로드한 Excel의 날짜·작업별 행 | 일정·안전조치·후속 질문 연결 | 사용자 제공 자료 |

통계는 **18개 CSV**를 연결하도록 구성했습니다. SIF 6,032건은 사례 행의 수이며, 통계 CSV의 전국 사고 건수와 같은 모집단을 뜻하지 않습니다. 관리자 자동 보고서는 이 중 건설업 3,459건을 대상으로 합니다.

### 주요 컬럼과 타입

| 데이터 | 컬럼 | 논리 타입 | 의미 |
| --- | --- | --- | --- |
| SIF | 시트명 + 연번 | `string` + `int` | 원본 사례 식별·추적 |
| SIF | 공종·작업명·단위작업명 / 업종 대·중·소분류 | `string` | 건설업 / 제조업 등 각 시트의 분류 |
| SIF | 재해개요·기인물·재해유발요인 | `string` | 사고 경위, 관련 물체·장비, 요인 |
| 통계 | 연도·산업중분류·규모·지표 | `int` / `string` / 순서형 범주 | 수치를 해석하는 조회 조건 |
| 통계 | 값 | 정수 또는 결측 허용 실수 | 인원·사업장 수 또는 만인율 |
| 계획서 | 작업일·시작·종료·작업 내용·주요 장비 | `date` / `time` / `string` | 일정과 상담의 작업 맥락 |

### 전처리 요약

- **SIF 스키마 구분:** 제조업 등은 단일 헤더, 건설업은 2단 헤더로 읽고 파일·시트·연번을 보존합니다. 두 시트의 연번만으로 전역 고유 ID를 만들지 않습니다.
- **결측과 분류 불가 구분:** SIF 주요 원본 컬럼의 물리적 빈칸은 0%로 확인됐지만, 제조업 등 기인물의 **‘분류 불가’ 398건**(15.47%)은 원본 범주로 남깁니다.
- **통계 형태 통일:** 인코딩과 규모 열 이름을 확인한 뒤 가로형 표를 `연도 × 산업중분류 × 규모 × 지표 × 값`의 세로형으로 변환합니다.
- **결측 보존:** 2025 사망만인율의 빈칸 **14/300개**(4.67%)를 `NaN`으로 유지합니다. 실제 0인 98개와 구분하며, 평균이나 0으로 채우지 않습니다.
- **중복·이상치 점검:** 통계의 빈 업종 키·중복 업종 키·해석 불가능한 숫자는 오류로 확인합니다. SIF 보고서 조회는 `source_id` 기준 중복을 제거합니다. 일괄적인 이상치 삭제나 근거 없는 사고 분류 보정은 하지 않습니다.
- **누락 기간 표시:** 제공되지 않은 2021년 사망만인율은 누락 상태로 남깁니다. 사망만인율을 다른 지표로 임의 재계산하지 않습니다.

**상세 명세:** [데이터 명세서 + 전처리 명세서](https://www.notion.so/3f223bb2243780cdb759f964165154d1) · [데이터 출처 기록](docs/personal_project/source_registry.md)

<sub>결측률은 확인한 원본 스냅샷 기준이며 파일이 바뀌면 다시 계산해야 합니다. Notion 문서는 공유 권한이 필요할 수 있습니다. 원본 문서·임베딩·자격 증명은 이 README 배포물에 포함하지 않습니다.</sub>

## 7. 실행 방법

### 사전 준비

- Python **3.12**, [uv](https://docs.astral.sh/uv/)
- OpenAI API Key와 코드에 설정된 모델에 대한 이용 권한
- 기존 검색 데이터가 적재된 **Supabase PostgreSQL + pgvector**
- 통계 CSV가 있는 **Supabase Private Storage**
- 선택 사항: Langfuse Cloud 프로젝트

### 설치

아래는 이 README의 기준 커밋이 올라간 fork 브랜치로 실행하는 방법입니다.

```bash
git clone --branch fix/plan-case-summary https://github.com/fun5307/mle-02-p1-team2.git
cd mle-02-p1-team2

uv venv --python 3.12
uv pip install --python .venv/bin/python -r src_v3/Project_1/requirements.txt
```

<sub>명령은 Linux / WSL 기준입니다. Windows에서는 Python 실행 경로를 `.venv\Scripts\python.exe`로 바꿉니다.</sub>

### 설정 파일

```bash
cp src_v3/Project_1/.streamlit/secrets.toml.example \
   src_v3/Project_1/.streamlit/secrets.toml
```

복사한 파일에 같은 Supabase 프로젝트의 연결 정보를 입력합니다.

```toml
[preventra]
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_DB_URL = "postgresql://postgres.YOUR_PROJECT_REF:URL_ENCODED_PASSWORD@YOUR_SESSION_POOLER_HOST:5432/postgres?sslmode=require"
SUPABASE_SECRET_KEY = "sb_secret_REPLACE_ME"
SUPABASE_STORAGE_BUCKET = "YOUR_PRIVATE_STATISTICS_BUCKET"
OPENAI_API_KEY = "REPLACE_ME"
PREVENTRA_HISTORY_SCOPE = "preventra-local"

# 선택: Langfuse 추적을 사용할 때 true로 변경하고 키를 설정
LANGFUSE_TRACING_ENABLED = "false"
# LANGFUSE_PUBLIC_KEY = "REPLACE_ME"
# LANGFUSE_SECRET_KEY = "REPLACE_ME"
# LANGFUSE_BASE_URL = "https://cloud.langfuse.com"
```

실제 `secrets.toml`과 `.env`는 Git에 올리지 않습니다. 기존 `.env` 방식을 사용하려면 `PREVENTRA_LOAD_DOTENV=true`를 명시해야 합니다. `PREVENTRA_HISTORY_SCOPE`는 기록을 나누는 작업공간 값이며 로그인·사용자 인증 기능은 아닙니다.

### 데이터 연결 → 실행

이 앱은 이미 적재된 검색 데이터에 연결합니다. 저장소를 복제하고 실행하는 것만으로 원본 수집이나 임베딩 적재가 자동 완료되지는 않습니다.

| 연결 대상 | 준비할 내용 |
| --- | --- |
| `rag_day1_documents` | SIF 검색 문서·메타데이터·임베딩, 기존 2025 통계 문서 |
| `langchain_pg_collection` / `langchain_pg_embedding` | `kosha_guides` 컬렉션, `text-embedding-3-small` 1,536차원 임베딩 |
| Private Storage | 매핑된 통계 CSV 18개 |
| 대화·계획 저장 | 앱 초기화에 필요한 테이블 생성·조회·쓰기 권한 |

```bash
.venv/bin/python -m streamlit run src_v3/Project_1/preventra_plus.py
```

브라우저에서 **http://localhost:8501**에 접속합니다. 관리자 화면의 **빈 작업계획서 양식**을 내려받아 작성한 뒤 업로드할 수 있습니다. 필수 정보는 작업일, 시작·종료, 동/구역, 작업 내용입니다.

대화·계획 테이블은 앱에서 초기화합니다. Storage 조회가 실패하면 같은 DB의 검증된 2025 통계를 대체 경로로 사용하고, 없는 연도는 안내합니다. 처음 사고 자료를 읽을 때는 대기가 발생할 수 있으며, 계획 내용을 먼저 보여준 후 사고 그래프를 자동으로 연결합니다.

**상세 연결·배포 안내:** [`STREAMLIT_CLOUD_SETUP.md`](src_v3/Project_1/STREAMLIT_CLOUD_SETUP.md)

## 8. 프로젝트 구조

최신 앱의 주요 실행 경로를 중심으로 정리했습니다.

```text
mle-02-p1-team2/
├── src_v3/Project_1/                  # 최신 Preventra Plus 앱
│   ├── preventra_plus.py             # Streamlit 진입점
│   ├── preventra_settings.py         # Secrets·환경변수 통합
│   ├── preventra_runtime.py          # Supabase 설정 확인
│   ├── preventra_ui_v2/              # 홈·사이드바·대화 화면과 스타일
│   ├── preventra_ui/                 # 상태·대화 저장·Agent 응답 연결
│   ├── preventra_agent/              # 단일 Agent·검색/통계 도구·Langfuse
│   ├── preventra_plan/               # 관리자 계획서 기능
│   │   ├── ui.py                     # 업로드·선택·관리자 화면
│   │   ├── domain.py                 # 작업계획 도메인·스냅샷
│   │   ├── agent.py                  # get_work_plan·계획서 후속 질문
│   │   ├── storage.py                # 계획 저장·revision 충돌 확인
│   │   ├── report.py                 # 요약·일정·확인 후보
│   │   ├── case_catalog.py           # SIF 비동기 조회·캐시
│   │   ├── case_report.py            # 그래프·사례 페이지·원문 출처
│   │   └── vendor/                   # 팀원 파서·집계·렌더러 재사용
│   ├── services/                     # 검색·질문 분석·통계·시각화
│   ├── tests/                        # 보고서·관리자/작업자 UI 검사
│   ├── .streamlit/secrets.toml.example
│   └── requirements.txt              # 앱 실행 의존성
├── src/                              # 기존 앱·수집·검색 실험 코드
├── notebooks/                        # 데이터 분석 작업 공간
├── docs/                             # 설계·출처·평가 절차 문서
├── data/                             # 데이터 안내 / 원본·가공물은 별도 관리
└── README.md
```

**함께 읽기:** [Agent 구조](src_v3/Project_1/PREVENTRA_AGENT.md) · [자동 사고사례 보고서](src_v3/Project_1/PLAN_CASE_REPORT.md) · [UI 수정 기록](src_v3/Project_1/UI_REPORT_FIX.md)

## 9. 검색 품질 평가

**평가 출처:** [Notion — 골든셋 평가](https://www.notion.so/3f123bb2243781d18876fd6b5fb5a125)

### 무엇을 평가했나요?

| 항목 | 범위 |
| --- | --- |
| 평가 문항 | G7 **TBM·안전교육 30문항**, G8 **산업재해 통계 30문항** |
| 검색 평가 대상 | G7 중 검색이 필요한 **28문항의 첫 실제 도구 호출** |
| 검색 순위 | 첫 호출의 **상위 3개**. 앱 화면의 최종 인용 순서를 검색 순위로 사용하지 않음 |
| 실행 기록 | **2026-10-06 Preventra v2**, 개인 fork `feature/preventra-integrated-ui` |
| 전체 호출 | G7 검색 **37회** — 첫 호출 28회 + 추가 호출 9회 |
| 통계 평가 | G8 답변의 수치·연도·업종·규모·분모를 별도 확인 |

### 첫 검색 평가 결과

| 판정 기준 | Hit@3 | MRR@3 | 해석 |
| --- | ---: | ---: | --- |
| **골든 출처 엄격 일치** | **9/28 = 32.1%** | **0.2619** | 정답의 SIF 사례 ID 또는 GUIDE 문서 ID·PDF 쪽·절과 일치 |
| **관련성 판정 초안** | **13/28 = 46.4%** | **0.3631** | 질문에 직접 관련되는 후보를 평가. **사용자 확인 전 AI 초안 포함** |

- **Hit@3:** 상위 3개 안에 ‘관련’ 후보가 하나 이상 있는 질문의 비율입니다.
- **MRR@3:** 첫 ‘관련’ 후보 순위의 역수를 평균합니다. 관련 후보가 없으면 0점입니다.
- ‘부분관련’은 기본 점수에 포함하지 않습니다. 관련성 초안의 후보 83개 중 기존 사람 판정과 일치하는 **6개만 이월**, 나머지 **77개는 AI 초안**입니다.
- 두 행은 **같은 실행에 서로 다른 판정 기준을 적용한 결과**입니다. 개선 전·후 비교가 아닙니다. Precision@5와 최신 v3의 확정 점수는 이 기록에서 확인되지 않아 기재하지 않습니다.

> 이 수치는 **이전 v2의 저장된 실행 기록**에 대한 평가입니다. 추적 기록에 배포 당시 커밋 ID가 없어 최신 v3 커밋 `63e6250`의 성능으로 해석할 수 없습니다.

<details>
<summary><strong>보조 지표: 기대한 근거 채널을 확보했는가?</strong></summary>

질문별 첫 검색과 별도로, 골든셋이 기대한 SIF·GUIDE 근거 채널 **32개**를 평가했습니다. 기대한 도구가 호출되지 않으면 0점입니다.

| 기준 | Hit@3 | MRR@3 |
| --- | ---: | ---: |
| 골든 출처 엄격 일치 | 9/32 = 28.1% | 0.2292 |
| 관련성 초안 | 10/32 = 31.3% | 0.2604 |

기대 SIF 23개 중 18개는 도구가 호출되지 않았고, 기대 GUIDE 9개는 모두 호출됐습니다. 이는 첫 검색의 관련성과 함께 **도구 선택 단계**도 검토해야 함을 보여줍니다.

</details>

### 평가에서 발견한 문제와 다음 실험

| 관찰 | 다음 확인·개선 방향 |
| --- | --- |
| 기대한 SIF 도구가 호출되지 않은 문항 존재 | 질문 의도·도구 설명을 검토하고, 도구 선택과 검색 순위를 나눠 평가 |
| 질문의 장비·작업과 다른 GUIDE가 인용됨 | 후보 관련성, 메타데이터, 최종 인용 채택을 각각 점검 |
| 제조업 전체·50인 미만 등의 통계 집계 범위 해석 실패 | 업종 합계·규모 구간 해석을 명시하고 정형 조회 결과로 검증 |
| 요구한 사고유형별 공식 통계가 조회 자료에 없음 | 데이터 범위를 보강하거나 제공할 수 없는 항목을 명확히 안내 |
| 버전·판정 기준이 섞이면 비교가 어려움 | 커밋·모델·코퍼스·질문·사람 판정을 고정한 v3 재평가 |

G8은 검색 순위 지표 대신 수치 정확성을 검토합니다. 예를 들어 건설업 사고사망자 361명과 연도별 328→361명 응답은 기준과 일치했지만, 다른 문항에서는 자료 부족·재질문·조회 반복 중단이 확인됐습니다. 전체 정답률은 확정 집계가 없어 제시하지 않습니다.

**재현 범위:** 이번 평가는 저장된 실제 앱 호출을 복원한 결과입니다. 동일 실행을 재현하는 단일 공개 명령은 확인되지 않았습니다. 기존 [`골든셋 검토 절차`](docs/golden-set-78-review.md)와 Notion의 문항·호출별 기록을 참고합니다.

최신 v3에서는 별도로 **집계·UI·Agent·추적·저장 계약 관련 28개 검사**와 실제 브라우저의 그래프 표시를 확인했습니다. 이 검사는 기능 회귀 검사이며 검색 성능 평가를 대체하지 않습니다.

## 10. 팀 소개

| 이름 | 역할·담당 | GitHub |
| --- | --- | --- |
| **이현근** | 추가 예정 | [@dihusrms-max](https://github.com/dihusrms-max) |
| **주승우** | 추가 예정 | [@fun5307](https://github.com/fun5307) |
| **김수연** | 추가 예정 | [@kimgomja](https://github.com/kimgomja) |
| **송수림** | 추가 예정 | [@slsSong](https://github.com/slsSong) |

기능별 브랜치에서 작업하고, 변경 내용을 확인한 뒤 통합하는 방식으로 협업합니다. 기존 앱과 팀원 앱은 필요한 함수·인터페이스를 골라 연결하고, 재사용 이력은 [`vendor/PROVENANCE.md`](src_v3/Project_1/preventra_plan/vendor/PROVENANCE.md)에 남겼습니다.

## 11. 회고 (KPT)

<sub>아래는 개발·평가 기록을 바탕으로 정리한 회고 초안입니다. 팀 공동 회고는 추후 반영합니다.</sub>

### Keep · 계속 가져갈 것

- **출처를 데이터와 함께 보존하기:** 답변에서 원본 문서·시트·페이지로 돌아갈 수 있는 구조를 유지합니다.
- **기존 기능을 작은 단위로 재사용하기:** 계획서 파서·집계·렌더러를 연결하면서 기존 검색과 대화 이력을 보존했습니다.
- **자료 종류별 처리 경로 유지하기:** 사고사례, 공식 지침, 정형 통계, 사용자 계획서를 구분해 다룹니다.

### Problem · 막혔던 지점

- **맥락 전달의 누락:** 계획서가 화면에 보여도 Agent가 그 내용을 조회하지 못하면 후속 질문이 끊겼습니다.
- **검색 개수와 보고서 집계의 혼용:** 챗봇의 Top 3 반환값을 보고서에 재사용해 전체 작업별 사례가 3건으로 제한됐습니다.
- **외부 조회 대기와 UI 차이:** 초기 조회 지연, Streamlit의 SVG 처리·상단바·사이드바 동작을 실제 화면에서 확인해야 했습니다.
- **평가 기준과 실행 버전의 불일치:** 정답 출처 일치, 내용 관련성, 도구 선택을 한 점수로 설명하기 어려웠습니다.

### Try · 다음에 시도할 것

- 최신 v3의 커밋·모델·데이터 버전을 기록하고 동일 골든셋으로 다시 평가하기
- SIF·GUIDE 도구 선택 정확도와 최종 인용의 관련성을 각각 개선하기
- 통계의 업종 합계·규모 구간 해석과 미확보 자료 안내를 보강하기
- 보고서의 첫 로딩 시간과 캐시 이후 응답 시간을 나눠 측정하기

**기록 더 보기:** [개발일지](https://www.notion.so/3e623bb22437807e8c40e28292d558ea) · [골든셋 평가](https://www.notion.so/3f123bb2243781d18876fd6b5fb5a125) · 팀 공동 회고 링크 추가 예정

---

<div align="center">

**Preventra · 필요한 안전 정보, 확인할 수 있는 근거.**

[데모 열기](https://preventra-final-v2.streamlit.app/) · [팀 저장소](https://github.com/encore-ai-campus/mle-02-p1-team2) · [최신 작업 브랜치](https://github.com/fun5307/mle-02-p1-team2/tree/fix/plan-case-summary)

</div>
