# Preventra UI

독립 진입점은 `Preventra.py`입니다. 기존 `app.py`, `services/`, 공용 Streamlit 테마와 의존성 파일은 변경하지 않습니다.

## 실행

`src/Project_1`에서 앱 의존성이 설치된 환경으로 실행합니다.

```bash
uv run streamlit run Preventra.py
```

현재 팀 저장소의 루트 `pyproject.toml`은 Python 3.14를 요구하지만, 기존 Project_1 검증 환경은 Python 3.12입니다. 이 환경을 그대로 사용한 실제 실행 명령은 다음과 같습니다. 동기화를 생략하므로 기존 환경의 패키지를 변경하지 않습니다. 다른 PC에서는 해당 PC의 환경 경로를 사용하세요.

```bash
cd /home/playdata/workspace/mle-02-p1-team2/src/Project_1
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT=/home/playdata/workspace/rag-project-1/.venv
export UV_NO_SYNC=1
uv run streamlit run Preventra.py --server.headless true --server.address 127.0.0.1 --server.port 8511 --browser.gatherUsageStats false
```

Python 요구 버전 차이에 대한 uv 경고는 예상됩니다. 이 작업은 프로젝트 Python 버전이나 기존 의존성을 바꾸지 않습니다. 통계는 기존 설정대로 Private Storage 또는 로컬 CSV에서 읽습니다. 원격 오류를 로컬 데이터로 숨기지 않고 화면에 안내하며 메뉴와 질문 전달은 계속 사용할 수 있습니다.

## 파일 역할과 재사용

- `Preventra.py`: 앱 설정, 화면 분기, 하단 질문 입력창.
- `preventra_ui/state.py`: `preventra_` 접두사를 가진 세션 상태, 화면 이동, 질문 이벤트 소비. 홈 이동은 대화를 유지하며 새 대화는 현재 세션의 질문을 비웁니다.
- `preventra_ui/gateway.py`: 다음 Single Agent 연결 위치인 `dispatch(AssistantRequest) -> AssistantResult`. 현재는 `not_connected`만 반환하고 외부 모델·DB·대화 저장을 호출하지 않습니다.
- `preventra_ui/views.py`: 홈·어시스턴트·데이터 출처, 선택적으로 표시하는 사고사례/가이드/통계 영역.
- `preventra_ui/statistics_view.py`: 기존 함수 호출과 표시. `load_statistics`, `filter_statistics`, `kpi_value`, `industry_trend`, `plot_six_year_line`을 재사용합니다.
- `preventra_ui/style.py`: 이 진입점에서만 삽입되는 네이비·청록 CSS. `.streamlit/config.toml`을 만들거나 수정하지 않습니다.
- `tests/test_preventra_ui.py`: 화면 흐름, 중복 전달, 빈 데이터, 오류, 선택적 응답 영역을 검증하는 오프라인 테스트.

## 세션 및 다음 연결 계약

홈 입력과 예시 버튼은 UUID를 가진 대기 질문을 생성합니다. 다음 실행에서 대기 상태를 먼저 비우고 소비한 이벤트 ID를 기록한 후 `dispatch`를 한 번 호출합니다. 같은 문장을 사용자가 다시 제출하면 새 질문이며, 단순 화면 재실행은 새 질문이 아닙니다. 영구 멱등성을 제공하는 구조는 아니므로 실제 Agent/저장을 붙일 때는 서버 측에서도 `request_id`로 중복 호출을 제어해야 합니다.

요청에는 `request_id`, `session_id`, `question`, `previous_questions`가 들어갑니다. 다음 단계에서 필요하면 선택된 과거 답변·근거를 포함하도록 계약을 확장합니다. 응답에는 답변, 실제 채택한 사고사례, GUIDE 근거, 그래프와 집계 범위·출처 설명을 선택적으로 채웁니다. 빈 항목은 화면에 표시하지 않습니다. 검색 후보 점수를 최종 채택 근거로 오인하지 않도록 어댑터가 구분해야 합니다.

새로고침·브라우저 세션 종료 시 질문이 사라질 수 있습니다. 최근 대화는 빈 상태만 제공하며 저장·복원·제목 생성은 구현하지 않습니다. Agent·MCP·Langfuse도 이번 범위에 포함하지 않습니다.

## 통계와 출처

홈의 대표 수치는 실제 값이 있는 최신 연도의 확보된 산업중분류·규모 전체 건수 합계입니다. 유효 셀 수와 집계 범위를 함께 표시합니다. 추세는 해당 영역의 산업중분류 선택에만 반응하며 어시스턴트의 전역 필터가 아닙니다. 누락 연도는 연결하지 않고, 사망만인율을 합산하거나 평균하지 않습니다.

출처 설명은 Project_1 README, Day 13 점검 기록, 로컬 KOSHA GUIDE 수집 목록, 기존 statistics 파일 매핑, 저장소 `docs/data-sources.md`에 근거합니다. SIF 24건·GUIDE 18건·813개 청크는 기록된 수량이며 현재 DB 수량을 새로 확인한 값이 아닙니다. 원본 데이터나 비밀 설정은 변경·커밋하지 않습니다.

## 검증

```bash
cd /home/playdata/workspace/mle-02-p1-team2
PYTHONPATH=src/Project_1 /home/playdata/workspace/rag-project-1/.venv/bin/python -m unittest discover -s src/Project_1/tests -v
```

UI 검사는 가짜 데이터/응답을 테스트 내부에만 주입합니다. 실행 앱은 예시 답변이나 가짜 근거를 표시하지 않습니다. 실제 OpenAI 답변 및 DB 대화 저장·복원은 이번 검증 대상이 아닙니다.
