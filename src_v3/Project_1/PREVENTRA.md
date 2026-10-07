# Preventra Plus v3

## 실행

이 버전의 진입점은 `preventra_plus.py`다. 저장소 루트에서 실행한다.

```bash
python -m pip install -r src_v3/Project_1/requirements.txt
python -m streamlit run src_v3/Project_1/preventra_plus.py
```

Python 3.12와 [Cloud 배포 안내](STREAMLIT_CLOUD_SETUP.md)를 기준으로 설정한다.

## 구성

- `preventra_plus.py`: 앱 진입점, 설정 확인, 관리자·작업자 화면 연결
- `preventra_settings.py`: Cloud Secrets·환경변수·로컬 Secrets 공통 설정
- `preventra_runtime.py`: 동일 Supabase 프로젝트 확인, SSL DB 및 통계 연결
- `preventra_ui`: 대화 상태·요청·Supabase 이력 저장
- `preventra_ui_v2`: 화면과 CSS
- `preventra_plan`: 관리자 Excel 계획서·작업 기록·보고서·계획 조회 Tool
- `preventra_agent`: 필요한 Tool을 선택하고 근거를 확인하는 단일 Agent
- `services`: SIF·KOSHA 검색, Supabase 통계, 시각화

화면과 CSS 경로는 이 앱 폴더를 기준으로 찾는다. 의존성·공통 서비스·관리자 계획서 코드는 같은 폴더 안에 있다.

## 저장과 설정

대화와 작업계획은 Supabase PostgreSQL에 저장한다. Streamlit 세션 상태는 현재 선택·표시·캐시를 관리한다. 업로드 Excel 원본은 저장하지 않는다.

Cloud는 Secrets에서 실제 설정을 읽는다. 로컬은 앱의 `.streamlit/secrets.toml`을 사용할 수 있다. .env는 PREVENTRA_LOAD_DOTENV=true를 명시한 경우에만 읽는다.

이 버전의 변경 범위와 실행 확인 범위는 [배포 안내](STREAMLIT_CLOUD_SETUP.md#이번-변경의-확인-범위)에 기록했다.
