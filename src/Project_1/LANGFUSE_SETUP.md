# Preventra Conversation History & Langfuse (3차)

> Cloud 배포 설정과 최신 검증은 [STREAMLIT_CLOUD_SETUP.md](STREAMLIT_CLOUD_SETUP.md)를
> 확인하세요. 아래 저장 구조는 유지하며, 운영 데이터는 Supabase만 허용합니다.

## 환경 설정과 실행

검증 환경: Python 3.12, Streamlit 1.64.0, LangChain 1.4.2,
langchain-core 1.6.4, langchain-openai 1.6.3, Langfuse 4.16.0.
Project_1의 `requirements.txt`에 기존 실행 패키지와 Langfuse 버전을 명시합니다.

저장소 루트 `.env`에 설정합니다. `.env`와 실제 키는 Git에 추가하지 않습니다.

```dotenv
LANGFUSE_PUBLIC_KEY=your-project-public-key
LANGFUSE_SECRET_KEY=your-project-secret-key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
# 선택: 추적을 명시적으로 끄려면 false
LANGFUSE_TRACING_ENABLED=true
# 선택: 동일 DB 안에서 구분할 로컬 작업공간 이름
PREVENTRA_HISTORY_SCOPE=preventra-local
```

Base URL은 키를 발급받은 Langfuse Cloud 프로젝트의 리전과 일치해야 합니다.
기본값은 EU Cloud입니다. US는 `https://us.cloud.langfuse.com`, Japan은
`https://jp.cloud.langfuse.com`입니다. 키 변경 후 실행 프로세스를 다시 시작하세요.
기존 `services.safety_rag.setting()`의 Streamlit Secrets 우선순위를 유지합니다.
키가 하나라도 없거나 SDK 초기화가 실패하면 tracing만 꺼집니다.

DB·모델은 기존 `SUPABASE_DB_URL`/`DATABASE_URL`, `OPENAI_API_KEY` 설정을 사용합니다.
DB 계정에는 기존 `chat_history` 읽기·쓰기와 메타데이터 테이블 최초 생성 권한이 필요합니다.
초기화에 실패하면 UI는 저장소 안내를 표시하고 저장되지 않은 대화를 저장된 것처럼 처리하지 않습니다.

```bash
# 저장소 루트, Python 3.12 가상환경
python -m pip install -r src/Project_1/requirements.txt
python -m streamlit run src/Project_1/Preventra.py
```

## 저장 구조

- `preventra_conversations`: `conversation_id UUID`, `scope`, `title`, `created_at`, `updated_at`.
- `chat_history`: 기존 `PostgresChatMessageHistory`의 `session_id = conversation_id`.
  `HumanMessage`와 `AIMessage` 쌍을 기존 JSONB 형식으로 저장합니다.
- AI 메시지의 `additional_kwargs.preventra_result`에는 표시한 답변·사례·가이드·출처와
  Plotly JSON을 저장합니다. 복원 시 모델이나 검색을 재실행하지 않습니다.
- 요청 UUID는 두 메시지의 `preventra_request_id`에 들어갑니다. 대화 행 잠금 후
  중복 확인·제목/시간 갱신·메시지 쌍을 같은 트랜잭션에서 커밋합니다.
- 기존 `SafetyRAGService.save_turn()`은 전용 `SafetyAnalysis` 형식을 요구하므로
  변경하지 않고, 그 서비스가 사용하는 `PostgresChatMessageHistory`와 DB 설정을 재사용합니다.
- 첫 질문의 공백을 정리한 최대 32자 제목을 사용합니다. 제목용 LLM 호출은 없습니다.
- 홈 이동은 선택한 대화와 목록을 유지합니다. 새 대화는 DB UUID를 생성합니다.
  선택/저장 시 최근 사용시간을 갱신하며 목록은 최신 50개를 보여줍니다.
- `st.session_state`는 선택 ID와 화면 캐시만 유지합니다. 새 질문의 맥락은 DB에서
  다시 읽고, Agent에는 기존 방식대로 최근 8턴을 제공합니다.
- 저장 실패 시 현재 답변을 메모리에 유지하고 저장 재시도를 제공합니다. 저장 전에는
  새 질문·대화 전환을 막아 미저장 답변의 유실을 줄입니다. 재시도는 모델을 다시 호출하지 않습니다.
  영구 저장이 끝나기 전에 브라우저를 종료하면 미저장 답변은 잃을 수 있습니다.

현재 앱에는 사용자 로그인/권한 체계가 없습니다. 목록은 `scope`별 작업공간 목록이며
개인 계정별 비공개 대화함이 아닙니다. 인증이 필요한 다중 사용자 배포 전에는 서버에서
검증한 사용자 ID로 범위를 나누고 접근권한 검사를 연결해야 합니다. scope는 인증 수단이 아닙니다.
기존 앱의 대화는 별도 메타데이터가 없으므로 Preventra 목록에 자동 노출하지 않습니다.

## Langfuse 연결

`preventra_agent/observability.py`가 공식 v4 API를 사용합니다.

1. 질문 하나를 `start_as_current_observation(as_type="agent")`로 감쌉니다.
2. `request_id`에서 trace ID를 만들고 `propagate_attributes()`로
   `session_id=conversation_id`, `preventra`/`safety-agent` 태그를 전달합니다.
3. 요청별 `langfuse.langchain.CallbackHandler`를 생성해 기존 모델과 StructuredTool
   `invoke(config=...)`에 전달합니다. 실제 Tool만 해당 Agent trace의 자식으로 표시됩니다.
4. 모델 generation에는 integration이 제공하는 latency와 token usage가 기록됩니다.
   Agent root output에는 검증된 최종 답변, 호출 Tool 목록, 완료 상태가 기록됩니다.
5. Tool output은 구조화된 content만 기록합니다. UI용 Plotly artifact는 전송하지 않습니다.
   callback은 요청별로 생성해 동시 대화가 같은 callback 상태를 공유하지 않습니다.

Dashboard에서 **Traces** → 이름 `Preventra Safety Agent` 또는 태그 `preventra`로
찾으세요. trace를 열면 Agent 아래 generation과 SIF/KOSHA/통계 Tool의 입력·출력과
시간을 볼 수 있습니다. **Sessions**에서 conversation UUID를 선택하면 같은 대화의
질문 trace를 모아볼 수 있습니다. 일반 Streamlit 화면에는 trace ID·링크·디버그 로그를 표시하지 않습니다.

장기 실행 서버는 SDK의 비동기 배치 전송을 사용합니다. 별도 검증 스크립트 종료 전에는
`get_tracing_client().flush()`로 전송을 기다립니다. 키 존재만으로 수집 성공을 간주하지 말고
해당 프로젝트 Dashboard 또는 읽기 API에서 실제 trace/session을 확인해야 합니다.

## 개인정보와 secret 처리

metadata는 요청·대화 UUID와 고정 태그만 직접 추가합니다. DB URL, API 키, 사용자 프로필을
metadata에 넣지 않습니다. v4 `mask_otel_spans`가 exporter 직전에 환경설정의 secret 값,
비밀번호·인증 필드, DB 접속 문자열, 이메일·전화·주민번호·카드번호 패턴을 제거합니다.
Tool artifact 및 원본 예외 메시지를 의도적으로 기록하지 않습니다.
자유 입력의 모든 개인정보를 정규식으로 완벽하게 식별할 수는 없으므로 개인정보가 포함된
운영 입력은 별도 조직 정책과 추가 탐지/비식별 처리가 필요합니다. 그런 입력을 취급해야 하는
환경에서는 검토 전까지 `LANGFUSE_TRACING_ENABLED=false`로 기록을 끌 수 있습니다.

## 검증

```bash
PYTHONPATH=src/Project_1 python -m unittest discover -s src/Project_1/tests -v
```

오프라인 테스트는 DB와 모델을 대체합니다. Observability 검사는 실제 Langfuse SDK와
공식 CallbackHandler를 로컬 메모리 exporter로 실행해 trace 계층·session·토큰·마스킹을
검사하며 외부 Langfuse 프로젝트를 호출하지 않습니다. 실제 DB/모델 검증은 별도 수행하고,
대화 원문과 키를 공개 저장소에 커밋하지 않습니다.

### 3차 당시 결과 (Cloud 연결 전)

- 오프라인 47개 통과. 실제 Langfuse 4.16.0 SDK의 로컬 exporter로 한 질문당 Agent root,
  Tool 자식, generation 사용량, 동일 대화 session 연결, 개인정보/secret 패턴 제거 확인.
- 실제 `Preventra.py` AppTest에서 PostgreSQL과 기존 모델·자료로 다음을 확인:
  첫 대화 생성 → 지게차 SIF 답변 → 두 번째 대화 생성 → 건설업 통계 답변 → 홈 이동 시
  목록 유지 → 첫 대화 복원 → 지게차 맥락의 KOSHA 후속 답변을 같은 대화에 저장.
- 새 Streamlit 세션에서 메시지·사례·가이드·Plotly 그래프 복원, 재실행 및 동일 request_id
  재저장 시 중복 없음. 실제 DB에서 저장 실패 시 메타데이터/메시지 롤백과 scope 구분 확인.
- 실제 SIF/KOSHA/통계 요청의 로컬 SDK trace에 선택된 Tool과 generation token usage 기록.
  SIF에는 기존 rerank 모델 호출도 포함. 한 대화의 SIF→KOSHA 두 trace가 동일 session 사용.
- Langfuse 키가 없는 설정에서도 실제 모델의 감사 인사 답변과 DB 저장 성공.
- 외부 Langfuse 키가 제공되지 않은 환경이므로 Dashboard 수집·외부 session 조회는 미검증.
  키 설정 후 위 3개 질문을 실행하고 해당 프로젝트에서 확인해야 최종 외부 검증이 완료됩니다.

공식 문서:
- [LangChain integration](https://langfuse.com/integrations/frameworks/langchain)
- [Session 연결](https://langfuse.com/docs/observability/features/sessions)
- [v4 export masking](https://langfuse.com/docs/observability/features/masking)
