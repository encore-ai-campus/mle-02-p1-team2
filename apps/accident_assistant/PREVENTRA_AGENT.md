# Preventra Single Agent (2차)

## 구현 범위

`Preventra.py`의 현재 세션 질문을 하나의 Tool-calling 모델이 처리합니다. 인사와 조건 확인은 Tool 없이, 근거가 필요한 요청은 관련 Tool만 선택합니다. 기존 `app.py`, Notebook, 데이터 파일, 기존 `services/` 인터페이스는 변경하지 않습니다. LangGraph / MCP / Langfuse / 과거 대화 목록·복원·제목 생성은 구현하지 않습니다.

확인한 설치 버전은 `langchain 1.4.2`, `langchain-core 1.6.4`, `langchain-openai 1.6.3`, `langchain-postgres 0.0.18`, Python 3.12입니다. 기존 요구 패키지로 동작하며 의존성을 추가하지 않았습니다.

## 실행 방식

`preventra_agent/agent.py`의 `SafetyAgent.run()`은 `ChatOpenAI.bind_tools()`에 Pydantic 입력 schema와 최종 `FinalAnswer` schema를 등록합니다. 모델이 반환한 `tool_calls`를 실행하고 `ToolMessage` 결과를 같은 대화에 추가합니다. 모델이 최종 답변을 반환할 때까지 최대 5회 모델 호출·6회 Tool 실행을 허용하며 동일 인자의 중복 실행을 막습니다. `create_agent`와 LangGraph는 사용하지 않습니다.

모델 설정은 기존 `OPENAI_API_KEY`와 `CHAT_MODEL`을 사용합니다. 선택적으로 `PREVENTRA_CHAT_MODEL`로 이 앱의 모델만 변경할 수 있습니다. 기본 모델은 기존 서비스와 같은 `gpt-6-luna`입니다. 임베딩도 기존 `text-embedding-3-small`을 사용합니다.

Agent 결과는 `final_answer / used_tools / evidence / tool_results / trace`로 나뉩니다. 최종 답변의 인용과 선택한 근거 ID가 실제 Tool 결과에 모두 존재하는지 검사합니다. 존재하지 않는 인용이 있으면 안전한 오류 안내로 대체합니다. 이것은 출처 ID의 일치 검사이며 모든 문장의 의미적 정확성을 보증하는 판정기는 아닙니다.

Tool과 문서 내용은 비신뢰 데이터로 취급하고, 검색되지 않은 사고 경위·기준·숫자 생성, OCR 조건의 임의 변경, GUIDE의 법적 의무 단정, 사망만인율 합산·평균을 금지하는 프롬프트를 사용합니다.

공식 참고: https://docs.langchain.com/oss/python/langchain/models — Tool calling loop 및 ToolMessage 설명. 설치된 `ChatOpenAI.bind_tools`와 `StructuredTool.from_function`의 실제 signature도 확인했습니다.

## Tool 구성

| Tool | 입력 | 반환 / 기존 서비스 재사용 |
|---|---|---|
| `search_sif_cases` | 맥락을 반영한 독립 검색문 `query` | 실제 사고 후보, 원문 발췌, doc_id·파일·시트·연번. `analyze_query`, `retrieve_sif`, `to_evidence`, 기존 임베딩·재정렬 재사용 |
| `search_kosha_guides` | `query` | GUIDE 후보, 발췌, guide_id·title·section·page·URL. `retrieve_kosha`의 메타데이터 필터·점수·OCR 절 보정 재사용 |
| `get_accident_statistics` | 지표, 산업중분류, 규모, 연도(null이면 해당 지표 최신 연도) | 값·유효 셀 수·범위·출처, 건수의 산업 비교 그래프. `load_statistics`, `filter_statistics`, `kpi_value`, `industry_totals`, `plot_industry_bar` |
| `get_accident_trend` | 지표, 산업중분류, 규모, 시작·종료연도(null이면 2020–2025) | 연도별 값, 결측, 실제 관측 시작·종료간 증감, 범위·출처와 추세 그래프. `industry_trend`, 전체 건수에는 `kpi_value`, `plot_six_year_line` |

Tool은 최종 문장을 작성하지 않습니다. 모델에는 구조화된 JSON을 전달하고, 그래프 객체는 `ToolMessage.artifact` 안에 별도로 보관합니다. 모델이 실제 인용한 근거만 UI의 사례 카드·가이드 expander·통계 그래프로 변환합니다.

사망만인율은 단일 산업·규모를 모두 지정해야 합니다. 누락 연도는 null로 유지합니다. '제조업'처럼 원자료의 정확한 산업중분류와 일치하지 않는 입력은 사용 가능한 목록을 반환해 세부 업종을 확인합니다. 사용자에게서 확인되지 않은 '우리 업종'을 임의로 선택하지 않습니다.

## UI 및 3차 Conversation History 연결 지점

- `preventra_ui/gateway.py`: `dispatch(AssistantRequest) -> AssistantResult`가 Agent와 화면을 연결합니다.
- `preventra_ui/state.py`: 현재 세션의 사용자 질문과 Assistant 답변을 `ConversationTurn`으로 전달합니다. 실패한 답변의 사용자 작업 맥락도 보존합니다. 새 대화는 UUID와 현재 턴을 초기화하고 홈 이동은 대화를 유지합니다.
- `preventra_agent/agent.py`: 최근 8턴을 모델 맥락으로 전달합니다. 과거 답변은 원문 근거를 대신하지 않으며 구체 후속 질문은 해당 Tool로 다시 확인합니다.
- 3차에는 `session_id`를 소유자와 연결하고 `request_id` 기준으로 저장·중복 방지한 뒤, `AssistantRequest.history`를 저장소에서 채우면 됩니다. 저장은 성공/실패 결과를 가진 턴이 완성되는 경계에 연결하세요. 현재는 세션 메모리만 사용하고 기존 `ask()`, `recent_history()`, `save_turn()`을 호출하지 않습니다.
- `used_tools`와 `trace`는 개발 검사에서 세션 결과로 확인합니다. 일반 화면에는 내부 Tool 이름·raw Document를 표시하지 않습니다. 서버 로그에는 request_id, Tool 이름, 상태만 남깁니다.

## 실행과 검사

실행 환경 및 `uv` 명령은 `PREVENTRA.md`를 참고하세요. 저장소 Python 3.14 요구사항과 기존 3.12 환경의 차이는 그대로이며, 기존 환경을 동기화 없이 사용합니다.

```bash
PYTHONPATH=apps/accident_assistant uv run --no-project --python 3.14 --with-requirements apps/accident_assistant/requirements.txt python -m unittest discover -s apps/accident_assistant/tests -v
```

기본 검사는 DB·모델 호출을 mock으로 대체합니다. 실제 모델 검증은 별도 명시적으로 실행하며 원자료·응답 본문을 공개 저장소에 커밋하지 않습니다.

### 2026-10-04 검증 결과

- 오프라인 39개 통과: 기존 대화 9개, Storage 7개, Preventra UI 12개, Single Agent 11개.
- 사용자의 명시적 승인 후 실제 gpt-6-luna, 기존 임베딩·DB·통계로 `Preventra.py`의 Streamlit AppTest 실행. 아래 모든 입력에서 실제 답변, 선택적 근거 표시, 화면 재실행 시 중복 방지를 확인했습니다.

| 질문 | 실제 호출 Tool | UI 결과 |
|---|---|---|
| 안녕 | 없음 | 일반 답변 |
| 지게차 충돌 사고사례 알려줘 | search_sif_cases | 사고사례 3개 |
| 고소작업 전에 확인할 건 뭐야? | search_kosha_guides | GUIDE 2개, 검색 자료의 장비 범위 명시 |
| 지게차 작업의 실제 사고와 예방방법을 같이 알려줘 | search_sif_cases + search_kosha_guides | 사례 3개 + GUIDE 3개 |
| 건설업 사고사망자는 최근 어떻게 변했어? | get_accident_trend | 답변 + 그래프 1개 + 집계 범위·출처 |
| 지게차로 자재를 운반 중이야 | 없음 | 필요한 정보 확인 |
| 그럼 작업 전에는 뭘 확인해야 해? | search_kosha_guides | 직전 지게차 맥락을 유지한 GUIDE 3개 |

- 브라우저에서 홈 질문 → 어시스턴트 실제 통계 답변·Plotly 그래프·출처를 확인했습니다. 메뉴·홈 복귀·새 대화·빈 데이터·오류 처리는 AppTest로 검증했습니다.
- 실제 호출 중 확인한 Responses API 호환 문제를 수정했습니다. `parsed_arguments` 같은 응답 전용 필드를 재전송하지 않도록 LangChain의 표준 tool_calls로 AIMessage를 구성하며 회귀 검사를 추가했습니다.
- 출처 검사는 인용 ID의 존재·일치를 검증합니다. 모든 문장의 의미를 자동으로 검증하는 기능은 아니므로 현장 적용 시 원문의 조건과 범위를 확인해야 합니다.
