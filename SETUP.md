# 팀원 PC 설정 및 확인

이 프로젝트의 표준 개발환경은 Windows 11 호스트와 WSL2 Ubuntu입니다. Git, Python, uv, 가상환경, 앱, Docker CLI는 WSL에서 실행합니다. 저장소는 WSL Linux 파일시스템의 /home/<사용자>/workspace/ 아래에 clone하고 VS Code에서 WSL: Ubuntu로 엽니다.

## uv 및 Python 3.12.15 준비

.python-version은 Python 3.12.15를 고정하고, pyproject.toml은 Python 3.12 계열(>=3.12,<3.13)을 허용합니다. Python 3.12.15는 소스 전용 보안 릴리스입니다. 공식 [Python 3.12.15 릴리스 페이지](https://www.python.org/downloads/release/python-31215/)에서 소스 배포본을 받아 ~/.local/python/3.12.15 아래에 빌드합니다.

먼저 빌드 도구와 라이브러리를 설치한 뒤 uv를 설치하고 버전을 확인합니다.

```bash
sudo apt-get update
sudo apt-get install -y curl build-essential pkg-config libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev libncurses-dev libgdbm-dev uuid-dev xz-utils
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv --version
```

CPython은 ~/src에서 빌드합니다. 컴파일하기 전에 공식 소스 아카이브의 체크섬을 확인합니다.

```bash
mkdir -p ~/src
cd ~/src
curl -LO https://www.python.org/ftp/python/3.12.15/Python-3.12.15.tar.xz
echo 'c2c4321961fab0fb999d66e0cecf521c2ab3994c7992873ea99e306c1094fd5a  Python-3.12.15.tar.xz' | sha256sum -c -
tar -xf Python-3.12.15.tar.xz
cd Python-3.12.15
./configure --prefix="$HOME/.local/python/3.12.15" --with-ensurepip=install
make -j4
make altinstall
"$HOME/.local/python/3.12.15/bin/python3.12" --version
```

소스 트리와 아카이브는 ~/src에 보관하고 Git checkout에는 넣지 않습니다.

## 프로젝트 가상환경 준비

저장소 루트에서 실행합니다. uv가 사용자 로컬 소스 빌드를 자동 탐색하지 않으므로 인터프리터의 절대 경로를 지정합니다.

```bash
cd ~/workspace/your-checkout
"$HOME/.local/python/3.12.15/bin/python3.12" --version
uv sync --python "$HOME/.local/python/3.12.15/bin/python3.12"
```

uv는 Python 3.12.15와 프로젝트 lockfile로 .venv를 만듭니다. VS Code에서 .venv/bin/python을 선택합니다. 최신 main의 루트 데모는 앱 의존성을 설치한 뒤 streamlit_app.py를 실행합니다.

```bash
uv pip install --python .venv/bin/python -r src/Project_1/requirements.txt
.venv/bin/python -m streamlit run streamlit_app.py
```

## 로컬 환경변수 및 데이터베이스

WSL에서 예시 환경변수 파일을 복사합니다. .env와 인증정보는 커밋하지 않습니다.

```bash
cp .env.example .env
```

PostgreSQL이 필요할 때 Ubuntu WSL에서 Docker를 사용합니다. 서비스를 시작하기 전에 Compose 설정을 확인합니다.

```bash
docker compose config --quiet
docker compose up -d
docker compose ps
```

The Dev Container requests Python 3.12.15 through the official Python feature and checks python --version before installing requirements and starting the app. The container has not been built in this change, so runtime parity is not yet verified.

scripts/setup.ps1 is retained for legacy Windows workflows; it is not the WSL setup procedure.
