# Preventra v2 통합 UI

기존 `Preventra.py`와 `app.py`를 보존한 독립 진입점이다. 시안용 가짜 데이터나 A/B 전환은 없다. 기존 `preventra_ui.state`, `history`, `gateway`, 통계 화면과 출처·근거 렌더러를 실제로 사용한다.

## 화면 구성

1. 로고 + `홈 / 데이터·출처` 텍스트 메뉴. 중복 `안전 질문하기` 메뉴는 제거.
2. `Preventra Safety Intelligence`, 크게 표시되는 `Learn from incidents. Prevent accidents.`, 하단 한글 설명 + 질문창.
3. A안의 `HOW WE HELP` 소개. `Data Perspective`는 포함하지 않음.
4. 기존 `데이터로 살펴보는 산업안전` 전체: 실제 수치, 집계 범위, 산업 선택, 추세 Plotly, 출처·결측 안내.
5. 기존 `Our Principles` 문구와 가상 기업·교육 프로젝트 안내.

`데이터·출처`는 기존 SIF/KOSHA/통계 설명과 실제 통계 수록 범위를 재사용한다. 자료 수량에 대한 과거 프로젝트 기록과 현재 로드한 통계 범위를 구분한다.

## 실행

기존 의존성과 Secrets를 그대로 사용한다. 작업 경로에서:

```bash
uv run streamlit run Preventra_v2.py
```

독립된 공식 테마까지 적용하려면 같은 경로에서:

```bash
uv run python preventra_ui_v2/run_app.py
```

두 번째 명령은 localhost:8515에서 실행한다. 공식 테마 파일은 `preventra_ui_v2/theme/.streamlit/config.toml`에만 두어 기존 앱의 전역 설정을 변경하지 않는다. 본문 스타일은 v2 진입점에 한정된다. Noto Sans KR은 테마에서 Google Fonts를 통해 불러오며, 직접 실행 시에는 설치된 한글 지원 글꼴을 사용한다.

Cloud entry point: `src/Project_1/Preventra_v2.py`. 환경변수·의존성은 기존 `STREAMLIT_CLOUD_SETUP.md`와 동일하며 **Supabase DATABASE_URL**도 필요하다. 이 작업은 Cloud 배포를 실행하지 않는다.

## 대화 동작

- 홈 이동: 현재 conversation과 저장된 메시지를 유지한다.
- 홈 질문·예시 버튼: 새 conversation을 생성한 뒤 첫 질문을 보낸다.
- 상담 입력창: 선택한 conversation의 후속 질문을 보낸다.
- 사이드바 새 대화: 기존 로직대로 빈 상담을 시작한다.
- 최근 대화: 기존 PostgreSQL 저장 자료·근거·Plotly를 복원한다.
- 저장 실패 시 기존 재시도·전환 방지 규칙을 유지한다.

새로운 비즈니스 로직은 만들지 않는다. `preventra_ui_v2/actions.py`는 홈 진입 의미만 조합하고, Agent 실행·중복 방지·DB 저장은 기존 함수가 처리한다. 사용자/모델 문자열을 커스텀 HTML에 넣지 않는다.

## 검증

```bash
PYTHONPATH=src/Project_1 uv run python -m unittest discover -s src/Project_1/tests -v
PYTHONPATH=apps/accident_assistant uv run python -m unittest discover -s apps/accident_assistant/tests -v
```

2026-10-06: Preventra 검사 46개(새 UI 8개 포함), 기존 서비스 검사 16개 통과. 실제 `Preventra_v2.py` AppTest에서 인사, SIF, KOSHA 후속 질문, SIF+KOSHA 복합 질문, 새 대화·DB 복원·복원 후 후속 질문·중복 방지를 검증했다. Langfuse Cloud Observations API에서 Agent/Tool/Generation, 최종 응답, token usage, 같은 conversation의 session 연결을 확인했다.

통계 첫 점검은 교체 전 키가 남아 있어 실패했다. 사용자가 `.env`를 갱신한 후 새 프로세스에서 Supabase 통계 5,470행(2020–2025년)을 읽었다. 기존 인증 코드와 서비스 인터페이스는 변경하지 않았다. 로컬 검증용 실제 대화는 별도의 history scope에 보관하며 자동 검사에는 메모리 대체 저장소를 사용한다.

갱신 후 실제 통계 질문에서 `get_accident_trend`만 호출되었고 Plotly 그래프 1개가 표시되었다. 별도 Streamlit 세션에서 DB에 저장된 그래프 복원과 중복 저장 방지를 통과했다. 해당 질문의 Langfuse Cloud Agent/Tool/Generation 4개 observation, session 연결, 최종 응답과 token usage도 확인했다.

추가 파일: `Preventra_v2.py`, `preventra_ui_v2/{views,actions,run_app}.py`, `styles.css`, 독립 테마, `tests/test_preventra_v2.py`, 이 문서.
