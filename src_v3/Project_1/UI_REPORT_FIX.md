# Preventra Plus v3 UI / 보고서 수정

## 변경

- 진입점: `preventra_plus.py` 유지. 기존 `app.py`는 수정하지 않음.
- `preventra_ui_v2/styles.css`: 원래 Preventra v2 채팅 말풍선·본문·입력창 스타일 재사용. Streamlit 툴바와 사이드바를 강제로 숨기던 규칙 제거. 상단바 아래 여백 확보, 작업자/관리자 전환 복원.
- `preventra_ui_v2/views.py`, `preventra_ui/views.py`: 표시용 결과에서 내부 인용 토큰을 숨기되 저장 원문·근거·출처는 유지.
- `preventra_plan/ui.py`: Excel 업로드 즉시 로컬 보고서 미리보기. 사용자가 적용하면 Supabase 이력과 후속 질문에 연결.
- `preventra_plan/report.py`: 계획 요약·작업 안전조치·누락·시간표·겹치는 작업·출처를 외부 조회 없이 렌더링. 날씨와 SIF 검색은 각각 버튼으로 요청. 기존 SIF 검색 구현은 유지.
- `preventra_plan/vendor/briefing_report.py`: `src_v2/shining_chatbot/briefing_report.py`의 작업 카드와 SVG 도넛 렌더러 재사용. 오전 고정 문구를 선택 범위로 변경하고 원본 시트·행과 전체 내용을 추가. 별도 SANUP-P 환경이나 SQLite는 요구하지 않음.

사고 그래프는 이번 SIF 검색의 실제 반환 사례를 분류한다. 팀원 앱의 별도 로컬 parquet 전체 키워드 집계와 모집단이 다르며, 현장 발생률이나 전체 사고 통계로 표시하지 않는다. 보고서의 즉시 표시 대상은 계획서로 만들 수 있는 내용이다. 외부 검색과 예보에는 네트워크 대기시간이 발생한다.

## 검증

`src_v3/Project_1/tests/test_plus_report_ui.py`: 6개 통과. 업로드 미리보기의 외부 호출 0회, 적용·후속 질문·날짜별 복원, 작업자 질문의 계획 분리, 외부 조회 실패, SIF 그래프 캐시·출처, 저장 인용과 표시 인용 분리, HTML 이스케이프와 일정 시각 검증.

기존 Agent 11개, 관찰 3개, 저장 snapshot 계약 1개도 v3 모듈에 대해 별도 실행한다. 예전 Preventra.py 화면을 여는 전체 history UI suite의 사이드바 홈 버튼 테스트는 현재 화면과 다른 `preventra_sidebar_home` 키를 전제로 하므로 v3 복원 검사는 새 AppTest로 수행한다.

실제 Streamlit 1.64 브라우저에서 사이드바 접기→펼치기, 상단 홈·역할 선택 표시, 사용자 말풍선·답변 본문 배치를 확인했다. 브라우저와 AppTest는 가상 데이터를 사용했으며 실제 Supabase 쓰기·유료 모델 호출·Cloud 배포 검증은 수행하지 않았다.

## 실행

기존 환경과 Secrets를 사용하여 `streamlit run src_v3/Project_1/preventra_plus.py`로 실행한다. 새 의존성은 없다. 수정 브랜치는 `fix/plus-ui-report`다. main에 src_v3가 아직 없어, 기존 `fix/src-v3-cloud`의 v3 스냅샷을 별도 기준 커밋으로 가져온 뒤 수정 커밋을 분리했다.
