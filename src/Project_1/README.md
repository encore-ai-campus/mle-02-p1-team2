# Project_1 학습 앱

기존 팀 앱 streamlit_app.py와 별도로 최신 개인 작업을 보존한 SIF/KOSHA Dual RAG 앱입니다.

## 로컬 실행

저장소 루트 /home/playdata/workspace/mle-02-p1-team2에서 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/Project_1/requirements.txt
.venv/bin/python -m streamlit run src/Project_1/app.py
```

저장소 루트의 로컬 .env 또는 Streamlit Secrets에 DATABASE_URL(또는 SUPABASE_DB_URL)과 OPENAI_API_KEY를 설정합니다. Supabase에서는 Session pooler의 PostgreSQL URI(5432 포트)를 사용합니다. 비밀값은 커밋하지 않습니다.

통계 CSV는 로컬 src/Project_1/data/에 별도로 준비합니다. 사고 검색에는 rag_day1_documents, KOSHA 검색에는 langchain_pg_collection/langchain_pg_embedding의 kosha_guides 컬렉션이 필요합니다. 대화 이력은 chat_history를 사용합니다. 팀 앱의 DB 구조와 같다고 가정하지 않습니다.

## 오프라인 대화 흐름 검사

```bash
PYTHONPATH=src/Project_1 .venv/bin/python -m unittest discover -s src/Project_1/tests -v
```

이 검사는 DB 및 OpenAI 호출을 mock으로 대체합니다. 실제 API/DB 통합 검증은 별도입니다.

## Streamlit Cloud

Main file path는 src/Project_1/app.py입니다. 이 폴더의 requirements.txt를 사용하며 Python 3.12에서 검증했습니다. 연결 정보는 Cloud Secrets에 넣습니다. 로컬 통계 CSV는 Git에서 제외되므로 Cloud용 데이터 공급은 별도로 준비해야 합니다.

노트북은 코드와 설명을 보존하고 실행 출력과 실행 번호를 비운 상태로 옮겼습니다. 개인 원본 저장소는 수정하지 않았습니다.
