# 산업안전 사고예방 도우미 앱

루트 `streamlit_app.py`의 BM25·pgvector 시연과 별도로 실행하는 SIF/KOSHA 통합 RAG 앱입니다.

## 로컬 실행

저장소 루트에서 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/accident_assistant/requirements.txt
.venv/bin/python -m streamlit run apps/accident_assistant/app.py
```

저장소 루트의 로컬 .env 또는 Streamlit Secrets에 DATABASE_URL(또는 SUPABASE_DB_URL)과 OPENAI_API_KEY를 설정합니다. Supabase에서는 Session pooler의 PostgreSQL URI(5432 포트)를 사용합니다. 비밀값은 커밋하지 않습니다.

통계 CSV는 Supabase Private Storage에서 읽을 수 있습니다. Storage 설정이 없는 로컬 환경은 `apps/accident_assistant/data/`를 사용합니다. 기존 체크아웃에 `src/Project_1/data/`가 있으면 이동 전환 중 자동으로 그 경로를 사용합니다. 사고 검색에는 rag_day1_documents, KOSHA 검색에는 langchain_pg_collection/langchain_pg_embedding의 kosha_guides 컬렉션이 필요합니다. 대화 이력은 chat_history를 사용합니다. 팀 앱의 DB 구조와 같다고 가정하지 않습니다.

## 오프라인 대화 흐름 검사

```bash
PYTHONPATH=apps/accident_assistant .venv/bin/python -m unittest discover -s apps/accident_assistant/tests -v
```

이 검사는 DB 및 OpenAI 호출을 mock으로 대체합니다. 실제 API/DB 통합 검증은 별도입니다.

## Streamlit Cloud

Main file path는 apps/accident_assistant/app.py입니다. 이 폴더의 requirements.txt를 사용하며 Python 3.12에서 검증했습니다. 연결 정보는 Cloud Secrets에 넣습니다. Private Storage 설정을 함께 넣으면 로컬 통계 CSV 없이 실행할 수 있습니다.

노트북은 코드와 설명을 보존하고 실행 출력과 실행 번호를 비운 상태로 옮겼습니다. 개인 원본 저장소는 수정하지 않았습니다.

## 공유 Supabase와 통계 Storage 사용

프로젝트 관리자가 Supabase 대시보드에서 팀원의 접근 권한을 부여합니다. 팀원은 본인 계정으로 접근하며, 비밀값은 이 문서나 GitHub에 적지 않습니다. 실행에 필요한 키는 비밀번호 관리 도구 등 별도 안전한 경로로 전달합니다.

로컬에서는 저장소 루트의 .env에, Cloud에서는 앱의 Settings → Secrets에 다음 항목을 설정합니다. 아래는 Cloud Secrets의 TOML 예시이며 실제 값은 각자 설정합니다.

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/postgres?sslmode=require"
OPENAI_API_KEY = "본인의 키"
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_본인의서버키"
SUPABASE_STORAGE_BUCKET = "industrial-statistics"
```

SUPABASE_SECRET_KEY는 서버에서만 사용하며 읽기 전용 키가 아닙니다. 브라우저·채팅·커밋에 포함하지 않습니다. Storage 설정 세 항목은 함께 설정하고, Cloud Secrets가 로컬 환경변수보다 우선합니다.

버킷은 Private로 유지합니다. 최상위에는 accident_death_2025.csv, accident_injured_2025.csv, fatality_rate_2025.csv, business_count_2025.csv를 올립니다. history/에는 2020~2024년 accident_death와 accident_injured 각 5개, fatality_rate는 2020·2022·2023·2024년 4개를 올립니다. 총 18개이며, 제공되지 않은 2021년 사망만인율은 기존 통계·차트 로직에서 NaN으로 유지합니다.

Storage 설정이 있으면 로컬 CSV가 없어도 통계를 로딩합니다. CSV는 다운로드 후 메모리에서 처리하고 통계 결과는 1시간 캐시합니다. 파일을 갱신한 직후 반영하려면 Streamlit 메뉴의 Clear cache 또는 앱 재시작을 사용합니다. 인증 실패·필수 파일 누락은 빈 통계나 로컬 파일로 숨기지 않고 오류로 처리합니다. Storage 설정이 전혀 없는 로컬 환경은 기존 data/ CSV를 사용합니다.

## Cloud 배포 및 시연 확인

- Repository: encore-ai-campus/mle-02-p1-team2
- Branch: 이 앱 변경사항이 push된 브랜치 (검토·병합 후 main 사용)
- Main file path: apps/accident_assistant/app.py
- Python: 3.12
- Dependencies: app.py 옆 requirements.txt (기존 패키지로 Storage를 읽으므로 추가 SDK 불필요)

Cloud에는 .env나 원본 데이터를 업로드하지 않습니다. GitHub에 코드를 push한 뒤 Cloud Secrets를 설정합니다. 다른 PC 또는 시크릿 창에서 통계·규모 필터·6년 추세(2021 사망만인율 공백), SIF/KOSHA 검색, 출처, 후속 질문, 새 대화를 확인합니다. 마지막으로 로컬 Streamlit과 Docker를 종료한 뒤 같은 Cloud URL에서 재확인합니다. 실제 질문은 OpenAI API를 사용합니다.

공유 DB에 연결하더라도 앱은 대화별 UUID를 사용합니다. 현재 화면은 같은 DB의 모든 대화를 조회하는 팀 공유 대화 목록이나 로그인 기능을 제공하지 않습니다.
