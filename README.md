# Accident-project
RAG 기반 산업재해 유사사고 검색 및 예방대책 추천 시스템
# Accident Project

산업재해 데이터를 기반으로 사용자의 작업 상황과 유사한 실제 사고 사례를 검색하고,  
재해개요·위험요인·위험성 감소대책 및 출처를 제공하는 RAG 기반 안전관리 지원 프로젝트입니다.

## 목표

사용자가 현장에서 수행할 작업을 자연어로 입력하면 관련 산업재해 사례를 검색하고,  
검색된 실제 사례를 근거로 작업 전 안전 확인과 TBM 준비를 지원합니다.

## MVP

- 작업 상황 자연어 입력
- 산업재해 유사사례 검색
- 관련 사례 최대 3건 반환
- 재해개요 제공
- 기인물 및 위험요인 제공
- 위험성 감소대책 제공
- 사례 ID와 원본 출처 표시
- 검색 근거 기반 RAG 답변 생성

## Tech Stack

- Python
- Pandas
- PostgreSQL
- pgvector
- OpenAI API
- Streamlit
- Docker / Docker Compose

## Project Structure

```text
Accident-project/
├─ src/
│  ├─ preprocessing/
│  ├─ database/
│  ├─ retrieval/
│  ├─ rag/
│  └─ ui/
├─ tests/
├─ data/
│  ├─ raw/
│  ├─ processed/
│  └─ eval/
├─ docs/
├─ scripts/
├─ .env.example
├─ .gitignore
├─ .python-version
├─ pyproject.toml
├─ PROJECT_BRIEF.md
└─ README.md
```

## Git Branch Strategy

```text
main
├─ feature/data-preprocessing
├─ feature/database
├─ feature/vector-search
├─ feature/rag-answer
├─ feature/streamlit-ui
├─ fix/*
└─ docs/*
```

### 협업 규칙

1. `main`에서는 직접 개발하지 않습니다.
2. 새로운 작업은 최신 `main`에서 시작합니다.
3. 기능 단위로 `feature/*` 브랜치를 생성합니다.
4. 작업 후 Commit 및 Push합니다.
5. GitHub에서 Pull Request를 생성합니다.
6. 팀원 Review 후 `main`에 Merge합니다.
7. Merge 완료된 feature 브랜치는 삭제합니다.

## Commit Convention

```text
feat: 기능 추가
fix: 버그 수정
docs: 문서 수정
refactor: 코드 구조 개선
test: 테스트 추가 또는 수정
chore: 환경설정 및 기타 작업
```

## Data & Secret Policy

- `.env` 파일은 GitHub에 업로드하지 않습니다.
- 원본 데이터는 `data/raw/`에서 관리합니다.
- 원본 데이터와 가공 데이터를 분리합니다.
- API Key와 DB 비밀번호는 환경변수로 관리합니다.
- 데이터 이용조건 확인 전 원문 데이터 및 임베딩 결과를 공개하지 않습니다.

## Development Flow

```text
Issue / 작업 결정
      ↓
main 최신화
      ↓
feature 브랜치 생성
      ↓
개발
      ↓
테스트
      ↓
Commit
      ↓
Push
      ↓
Pull Request
      ↓
Review
      ↓
Merge
      ↓
main
```

## MVP 완료 기준

사용자가 실제 작업 내용을 입력했을 때:

1. 관련 산업재해 사례를 찾고
2. 최대 3건을 반환하며
3. 사고 개요와 위험요인을 제공하고
4. 위험성 감소대책을 보여주며
5. 사례 ID와 출처를 확인할 수 있고
6. 검색된 근거만을 이용해 답변할 수 있어야 합니다.
