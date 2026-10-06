# Preventra Streamlit Community Cloud

## 배포 설정

- Repository: `encore-ai-campus/mle-02-p1-team2`
- Branch: `chore/preventra-cloud`
- Main file path: `src/Project_1/Preventra.py`
- Advanced settings → Python: **3.12**
- 아래 설정을 Advanced settings → Secrets에 **root-level TOML**로 입력합니다.
  실제 값이 들어간 파일은 커밋하지 않습니다.

```toml
OPENAI_API_KEY = "<OpenAI key>"
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_SECRET_KEY = "<Supabase secret key>"
SUPABASE_STORAGE_BUCKET = "<existing bucket>"
DATABASE_URL = "postgresql://postgres.<project-ref>:<URL-encoded-password>@<session-pooler-host>:5432/postgres?sslmode=require"
LANGFUSE_SECRET_KEY = "<Cloud project secret key>"
LANGFUSE_PUBLIC_KEY = "<Cloud project public key>"
LANGFUSE_BASE_URL = "https://cloud.langfuse.com"
```

`DATABASE_URL`은 **추가 필수 secret**입니다. 기존 pgvector·SQL·Chat History 서비스는
PostgreSQL 연결이 필요하며 Supabase API key로 대신할 수 없습니다. Supabase의
Connect 메뉴에서 같은 프로젝트의 **Session pooler, port 5432** 문자열을 사용하세요.
`SUPABASE_DB_URL`도 지원하며 둘 다 있으면 이 값이 우선합니다. 사용자명에 프로젝트 ref가
포함되어야 합니다. 비밀번호의 특수문자는 URL 인코딩합니다. Transaction pooler 6543은
이 앱에서 허용하지 않습니다. IPv6 가능한 환경은 같은 프로젝트 direct connection도 지원합니다.

Langfuse URL은 키를 발급한 Cloud 리전과 일치해야 합니다. EU, US, Japan, HIPAA Cloud의
공식 HTTPS 주소를 허용합니다. 키가 없거나 초기화·추적에 실패해도 답변 기능은 유지합니다.
선택적으로 `LANGFUSE_TRACING_ENABLED = "false"`로 끌 수 있습니다.

엔트리 파일과 같은 폴더의 `requirements.txt`가 루트의 `uv.lock`보다 먼저 선택됩니다.
루트 연구 환경의 Python 3.14 설정과 별도로 Cloud에서 3.12를 선택해야 합니다.
LangChain 패키지는 공식 Langfuse CallbackHandler에 필요합니다. 설치 시 따라오는
LangGraph 패키지는 전이 의존성이며 Preventra 구현은 이를 import하거나 실행하지 않습니다.

## 데이터와 실행 경계

| 기능 | 실제 원본 | 기존 서비스 재사용 |
|---|---|---|
| SIF | Supabase PostgreSQL `rag_day1_documents`, `sif_case` | `SafetyRAGService.retrieve_sif` |
| KOSHA | 같은 DB의 `langchain_pg_embedding` / `langchain_pg_collection`, `kosha_guides` | `SafetyRAGService.retrieve_kosha` |
| 통계 | Supabase Storage CSV 18개 | `load_statistics`, 기존 집계·Plotly 함수 |
| 대화 | 같은 DB의 `chat_history`, `preventra_conversations` | 기존 LangChain 메시지 형식·Preventra 저장소 |

`preventra_runtime.py`는 설정 누락, 로컬 DB, 다른 Supabase 프로젝트의 DB를 거부합니다.
통계도 Storage 설정이 없으면 안내를 표시하며 로컬 CSV로 대체하지 않습니다.
데이터를 새 프로젝트로 자동 업로드하거나 기존 테이블을 복제하지 않습니다. 제공된
Supabase 프로젝트에 기존 데이터가 있어야 합니다. 2021 사망만인율은 기존 자료가 없어
추세에서 제외되며 보간하지 않습니다.

공유 서비스의 원본은 `apps/accident_assistant/services`입니다. Preventra의 `services`
패키지는 이 경로를 참조하므로 서비스 로직을 복사하지 않습니다. 기존 `app.py`와 서비스
인터페이스는 변경하지 않습니다. `.env`는 로컬 개발의 선택 설정이며 Cloud 실행에 필요 없습니다.

DB 계정에는 RAG 테이블 읽기, 대화 테이블 읽기·쓰기, 최초 metadata 테이블 생성 권한이
필요합니다. 최근 대화는 현재 작업공간 공유 목록입니다. 사용자별 로그인·권한 기능은 없으므로
개인별 비공개 대화 서비스가 필요하면 공개 배포 전 별도 접근제어가 필요합니다.
기존 대화를 이어 쓰려면 `PREVENTRA_HISTORY_SCOPE`를 유지하세요(기본 `preventra-local`).

## Agent와 Langfuse

Single Agent는 모델의 `tool_calls`를 실행하고 결과를 `ToolMessage`로 돌려준 뒤 모델을
다시 호출합니다. 병렬 호출을 끄고 필요한 Tool을 순차 선택합니다. 키워드 조건분기 router나
LangGraph는 없습니다. 최종 답변과 검증된 근거만 Streamlit에 표시합니다.

Langfuse **Traces**에서 `Preventra Safety Agent` / 태그 `preventra`, `safety-agent`를 찾습니다.
한 질문의 Agent 아래 LLM generation과 실제 Tool의 argument/result, latency, usage가
표시됩니다. **Sessions**의 ID는 `conversation_id`입니다. 내부 Thought는 UI에 표시하지 않습니다.
export 직전 secret·연결문자열·일반 개인정보 패턴을 마스킹합니다.

프로그램으로 검증할 때는 `client.api.observations.get_many()`에 `trace_id` 또는
`session_id`, `from_start_time`/`to_start_time`, `fields="core,basic,time,io,usage,trace_context"`를
전달합니다. 새 Cloud 조직은 구형 `api.trace.get` / `api.sessions.get`에 410을 반환합니다.
v2의 input/output은 문자열이므로 JSON 해석이 필요하면 클라이언트에서 처리합니다.
`parse_io_as_json=True`는 사용하지 않습니다.

## 배포 전 실제 검증 (2026-10-04)

- Python 3.12의 새 가상환경에 이 requirements로 설치 성공. 기존 서비스 16개,
  Preventra 38개 검사 통과(합계 54개).
- `.env`와 데이터 폴더가 없는 임시 코드 checkout에서 실제 `Preventra.py` AppTest 실행.
  root-level `st.secrets`만으로 Supabase·OpenAI·Langfuse Cloud 연결 성공.
- SIF 3건, 고소작업 GUIDE 2건, 복합 질문 SIF 3건/GUIDE 3건의 표시 발췌를
  Supabase DB 원문과 대조. 로컬 PostgreSQL 접속 및 로컬 CSV 읽기를 허용하지 않는
  검증 훅으로 실행. 통계는 Storage 18개 CSV, 5,470행, 2020–2025년을 실제 조회.
- 인사: Tool 없음. 사고사례: SIF만. 작업 전 확인: KOSHA만. 건설업 추세: 통계만.
  복합 질문은 `LLM → SIF → LLM → KOSHA → LLM` 순서로 실제 관찰.
- 새 Cloud 프로젝트의 Observations API v2에서 질문별 5개 Agent trace를 읽어
  Tool argument/result, 최종 답변, latency, token usage, 동일 conversation session 연결 확인.
  SIF에는 기존 rerank 모델의 generation도 포함됨.
- 새 Streamlit 세션에서 Supabase의 메시지 10개 및 Plotly 그래프 복원. 재실행 중복 없음.
- Langfuse key를 모두 제거한 root-level Secrets로 실제 감사 인사 답변·DB 저장 정상.
  잘못된 endpoint/SDK 초기화 실패 시 추적만 비활성화되는 자동 검사도 통과.
- 기존 `app.py` 및 공유 services는 최신 `origin/main` 대비 변경 없음.
  Streamlit Community Cloud 배포 자체는 사용자가 실행하는 단계이며 이 검증에 포함하지 않음.

## 로컬 재현

저장소 루트에서 Python 3.12 가상환경을 활성화하고 실행합니다.

```bash
python -m pip install -r src/Project_1/requirements.txt
python -m streamlit run src/Project_1/Preventra.py
PYTHONPATH=src/Project_1 python -m unittest discover -s src/Project_1/tests -v
PYTHONPATH=apps/accident_assistant python -m unittest discover -s apps/accident_assistant/tests -v
```

공식 문서: [Streamlit 의존성 선택](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies),
[Supabase 연결](https://supabase.com/docs/guides/database/connecting-to-postgres),
[Langfuse LangChain integration](https://langfuse.com/integrations/frameworks/langchain).
