# 팀원 PC 설정 및 확인

이 문서는 Windows PC에서 산업재해 RAG 프로젝트를 새로 실행하는 표준 절차입니다. Python 앱은 Windows에서 실행하고 PostgreSQL 컨테이너는 WSL 2의 Ubuntu에서 실행합니다. 프로젝트 `.venv`, `.env`, PostgreSQL 볼륨은 팀원별 로컬 자원이며 공유하지 않습니다.

## PC 준비

- Windows 11 64비트 권장
- RAM 16GB 이상 권장
- Git for Windows
- Python 3.14.x 64비트
- Visual Studio Code와 Microsoft Python 확장
- WSL 2와 Ubuntu 24.04
- Docker Desktop, WSL 2 백엔드 활성화 및 Ubuntu 통합

현재 저장소는 Python 3.14.7에서 핵심 의존성 설치 해석과 로컬 RAG 검색을 확인했습니다. Docker는 Windows 터미널이 아니라 Ubuntu WSL의 Docker CLI로 실행합니다. Docker Desktop은 조직의 인원·매출 조건에 따라 유료 구독이 필요할 수 있으니 회사 PC 사용 전 라이선스를 확인합니다.

## 프로젝트 준비

저장소를 팀에서 정한 경로에 clone하고, VS Code에서 프로젝트 루트를 엽니다. PowerShell에서 프로젝트 루트로 이동한 다음 가상환경과 의존성을 준비합니다.

```powershell
py -3.14 --version
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`.venv`는 각 PC에서 새로 만듭니다. 다른 팀원의 `.venv`를 복사하지 않습니다.

## 개인 환경변수

프로젝트 루트에서 예시 파일을 복사합니다.

```powershell
Copy-Item .env.example .env
```

`.env`의 `POSTGRES_PASSWORD`를 로컬 비밀번호로 바꾸고, `DATABASE_URL`에도 같은 비밀번호를 입력합니다. 각자 필요한 경우 `DATA_GO_KR_SERVICE_KEY`와 `OPENAI_API_KEY`를 설정합니다. `.env`는 Git에 커밋하거나 팀 채팅·스크린샷에 올리지 않습니다. API 기능을 사용하지 않는 팀원은 해당 API 키를 비워 둘 수 있습니다.

## DB 포트 확인 및 시작

프로젝트 기본 포트는 `5433`입니다. 기존 PostgreSQL 등 다른 프로그램이 이 포트를 사용하면 `.env`의 `POSTGRES_PORT`와 `DATABASE_URL` 포트를 같은 값으로 바꿉니다. 예를 들어 `5434`를 쓰면 두 항목 모두 `5434`로 맞춥니다.

Ubuntu WSL이 설치되지 않았다면 관리자 PowerShell에서 한 번 설치하고 재부팅합니다.

```powershell
wsl --install -d Ubuntu-24.04
```

Docker Desktop 설정에서 WSL 2 엔진과 Ubuntu-24.04 통합을 켜고, PowerShell에서 아래 명령을 실행합니다.

```powershell
.\scripts\setup.ps1 -StartDatabase
```

스크립트는 Python 가상환경, `.env`, 비밀값이 아닌 필수 환경변수, Docker Compose 설정을 확인합니다. `-StartDatabase`를 지정하면 WSL에서 PostgreSQL을 시작합니다. 의존성까지 설치하려면 `-InstallDependencies`도 함께 지정합니다.

```powershell
.\scripts\setup.ps1 -InstallDependencies -StartDatabase
```

## 앱과 검색 확인

먼저 로컬 사례 검색을 확인합니다. 이 경로는 OpenAI API를 호출하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m src.sif_rag.rag_cli "지게차 작업 중 보행자 충돌을 예방하려면?" -k 2
```

화면을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r src/Project_1/requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

사이드바에서 작업 안전 상담과 사례 직접 검색을 선택할 수 있습니다. 검색 결과의 사례 ID와 출처를 확인하면 로컬 RAG 경로가 실행된 것입니다. 생성형 답변과 임베딩은 유료 API 사용량이 발생할 수 있으므로 별도 키와 팀 사용 기준이 준비된 경우에만 실행합니다.

## 완료 기준

- [ ] `py -3.14 --version`이 성공한다.
- [ ] 프로젝트 `.venv`에 `requirements.txt` 설치가 끝나고 `pip check`가 통과한다.
- [ ] `.env`가 존재하고 Git 변경 목록에 나타나지 않는다.
- [ ] `setup.ps1 -StartDatabase`가 Docker Compose 설정을 읽고 DB를 시작한다.
- [ ] 로컬 RAG CLI가 검색 결과와 출처를 표시한다.
- [ ] Streamlit 화면에서 검색할 수 있다.

## 문제 보고 양식

설치가 멈추면 아래 정보만 공유합니다. `.env` 내용, 키, 비밀번호는 공유하지 않습니다.

```text
Windows 버전:
Python 버전:
Docker Desktop 버전:
WSL 배포판 및 버전:
실패한 명령:
오류 메시지(비밀값 제거):
```
