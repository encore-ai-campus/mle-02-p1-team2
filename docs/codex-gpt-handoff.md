# GPT와 Codex 순차 협업

## 동작 방식

`scripts/agent_pair.py`는 다음 단계를 한 번에 실행한다.

1. 선택한 Git 기준 커밋에서 격리 worktree와 `feature/agent-pair-*` 브랜치를 만든다.
2. GPT API에 작업 요청과 허용된 텍스트 문맥을 보내 최소 패치를 요청한다.
3. `git apply --check`가 통과한 GPT 패치만 새 worktree에 적용한다.
4. WSL의 Codex CLI가 같은 worktree에서 구현을 이어간다.
5. GPT API가 변경 diff를 검토한다. `REQUEST_CHANGES`이면 Codex가 한 번 수정하고 GPT가 다시 검토한다.
6. 수정 사항, 검토 결과, 로그는 새 브랜치에 남긴다. 스크립트는 커밋·푸시·병합·배포하지 않는다.

GPT 편집과 Codex 편집은 한 worktree에서 순차 실행된다. 두 에이전트가 동시에 같은 파일을 덮어쓰지 않는다. GPT 검토는 판단 보조이며 사람이 diff와 결과를 확인해야 한다.

## Windows 앱과 같은 파일을 보는 방법

Codex Windows 앱에서 Agent environment를 WSL로 설정하고 재시작한 다음, 프로젝트를 연다. Windows 앱의 Add project에서 아래 WSL 폴더를 선택할 수 있다.

```text
\\wsl.localhost\Ubuntu-24.04\home\lee\workspace\accident-project\mle-02-p1-team2\RAG-project
```

ChatGPT 데스크톱 앱에서 GPT 대화를 사용할 때는 같은 폴더를 Local project로 연결한다. 일반 ChatGPT 대화의 문맥이 Codex 기록으로 자동 복사되는 것은 아니다. 이 자동화 스크립트는 ChatGPT 화면 대화를 조작하지 않고 GPT 모델을 Responses API로 호출한다.

자동화 실행 중에는 별도 worktree에서 파일이 바뀐다. GPT 데스크톱 UI로 그 diff를 추가 검토하려면 실행 출력의 worktree 경로를 Local project로 열거나 추가한다. 완료 후 원본 폴더에는 자동 반영되지 않으며, 검토 후 Git으로 선택적으로 반영한다.

## 준비

- WSL2에서 Python 환경과 프로젝트 의존성을 준비한다. 프로젝트 의존성에 OpenAI Python SDK가 포함되어 있다.
- WSL에서 Codex CLI에 로그인하고 `codex exec`가 실행되는지 확인한다.
- GPT 단계는 ChatGPT 화면 대화가 아니라 Responses API를 호출하므로 API 키와 API 토큰 사용 비용이 필요하다. 현재 모델별 가격은 [OpenAI API 가격표](https://developers.openai.com/api/docs/pricing)를 확인한다.
- WSL 셸 환경에 `OPENAI_API_KEY`와 계정에서 사용할 수 있는 `OPENAI_MODEL`을 설정한다. 키를 저장소 파일에 넣지 않는다.
- GPT API에는 작업 요청, 선택 문맥, 최종 diff가 전송된다. `.env`, `.aws`, `.codex`, `.ssh`, `data/`, 바이너리 파일은 기본 전송 대상에서 제외한다. 민감정보가 포함된 저장소에는 실행하지 말고, 검토 diff도 실행 전 확인한다.

API 키는 현재 셸에서만 설정하려면 셸의 안전한 비밀정보 관리 방법을 사용한다. `.env.example` 값을 복사해 실제 키를 저장소에 커밋하지 않는다. API 요청은 모델과 토큰 사용량에 따라 API 과금 대상이다.

## 실행 예시

상위 프로젝트 저장소에서 스크립트를 실행하고, 대상 Git 저장소를 `--repo`로 지정한다. `--base-ref`는 대상 저장소 안에 있는 커밋 또는 브랜치여야 한다.

```bash
read -rsp 'OpenAI API key: ' OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY
codex login
export OPENAI_MODEL=gpt-6-luna
python scripts/agent_pair.py \
  --repo /home/lee/workspace/accident-project/mle-02-p1-team2/RAG-project \
  --base-ref RAG_적재단계 \
  --task "요청한 작은 변경을 구현하고 변경 이유를 요약해줘"
```

또는 UTF-8 작업 파일을 전달한다.

```bash
python scripts/agent_pair.py \
  --repo /home/lee/workspace/accident-project/mle-02-p1-team2/RAG-project \
  --base-ref RAG_적재단계 \
  --task-file /tmp/agent-task.md
```

추가 문맥 파일은 `--context docs/architecture.md`처럼 반복 지정할 수 있다. 기본 문맥은 `AGENTS.md`, `README.md`, `PROJECT_BRIEF.md`, `pyproject.toml`이며, 존재하지 않거나 필터에 걸린 파일은 생략한다. GPT가 만든 패치가 적용되지 않으면 Codex는 실행하지 않고 패치 파일을 보존한다.

원본 체크아웃의 미커밋 변경은 새 worktree에 복사하지 않는다. 스크립트는 이 사실을 경고한다. 기준 브랜치에 들어 있지 않은 설계도·코드는 자동화 결과에 포함되지 않으므로, 실행 전에 올바른 `--base-ref`를 고른다.

## 검토 기준

- GPT 결과가 `APPROVE`여도 커밋 전 사람 검토를 한다.
- `REQUEST_CHANGES`는 Codex 수정 1회 후 재검토한다. 해결되지 않으면 브랜치에서 직접 판단한다.
- diff가 너무 크거나 민감 경로가 제외되어 검토가 불완전하면 `HOLD`로 취급한다.
- API 전송 대상, GPT 패치, Codex 명령 로그를 확인한 후에만 변경을 다른 브랜치에 반영한다.

## 민감 자료와 PR 인계 기준

### 노출된 키

- 저장소·노트북·로그에서 발견한 키나 토큰의 유효성을 확인하려고 호출하거나 시험하지 않는다. 값은 응답, 로그, 이슈, GPT 문맥에 복사하지 않는다.
- 키는 노출된 것으로 간주한다. 사용자가 발급 서비스에서 직접 폐기·교체하도록 안내하고, 교체 완료를 확인할 때까지 해당 PR과 관련 변경의 병합을 보류한다.
- 파일에서 키를 지우는 것만으로 회전을 완료했다고 간주하지 않는다. 새 키의 발급·저장·테스트는 사용자가 서비스에서 진행한다.
- 사례 기준: PR #8 변경 파일에 .env가 포함되어 있다. 키 유효성 테스트를 하지 않고 사용자의 폐기·교체 전까지 PR #8의 병합을 보류한다.

### 노트북 출력과 평가 자료

- GPT로 자료를 보내거나 PR을 정리하기 전에 노트북 코드 셀, 출력(표·이미지·로그), CSV 헤더와 행을 확인한다. 흔한 키·토큰·이메일·전화번호·정부 식별자 패턴을 점검하되, 원본 값은 로그나 보고서에 남기지 않는다.
- 자동 패턴 검사는 놓치는 항목이 있을 수 있다. 탐지 결과가 없더라도 전체 자료가 안전하다고 단정하지 않는다. 개인·비공개 정보가 의심되면 해당 값은 전달하지 말고 PR을 보류해 소유자에게 검토를 요청한다.
- 출력 정리가 승인되고 코드·CSV에 민감정보가 확인되지 않으면 노트북의 code-cell outputs와 execution_count만 비운다. 코드와 승인된 CSV는 보존한다. 소스나 CSV에서 민감정보가 발견되면 보존 방침을 임의로 바꾸지 말고 영향 파일만 특정해 검토를 요청한다.

#### PR #14 확인 기록

- PR #14의 노트북 7개에서 코드 셀 62개가 실행된 상태였고 출력 항목 113개(표·차트 포함)가 있었다. 출력은 산업재해 사례 설명, 통계 표·차트, RAG·평가 결과를 포함했다.
- 노트북 소스와 출력, CSV 2개에서 흔한 API 키·JWT·이메일·전화번호·주민등록번호 패턴은 발견되지 않았다. 확인한 표 머리글에서 개인 식별 필드는 보이지 않았다. 이는 정규식 기반 점검 결과이며 간접 식별 가능성까지 배제하지 않는다.
- golden_set_100.csv는 100개 평가 항목(ID, 분야, 질문, 원본 정답 ID, 정답 확인 문구)으로 확인했다. 두 CSV는 수정하지 않았다.
- 처리 기준에 따라 노트북 소스 코드는 보존하고 7개 파일의 출력과 실행 횟수만 제거했다. CSV 두 개는 원본과 동일하다.

## 실행 제한과 결과 코드

- API 제한 시간은 요청마다 기본 300초이고, Codex 작업 제한 시간은 실행마다 기본 1800초입니다. 각각 api-timeout, codex-timeout 옵션으로 조정할 수 있습니다.
- Codex가 시간 초과되면 로그를 저장하고 worktree를 보존합니다.
- GPT 패치는 최대 200,000자이며 텍스트 확장자와 민감 경로 필터를 통과해야 적용됩니다. 지원하지 않는 경로나 바이너리 패치는 적용 전에 중단됩니다.
- 최종 검토가 APPROVE이면 종료 코드 0, HOLD 또는 해결되지 않은 REQUEST_CHANGES이면 종료 코드 3입니다. API, Git, Codex 실행 오류는 종료 코드 2입니다.
- Codex는 workspace-write sandbox 안에서 동작합니다. 승인 프롬프트를 사용하지 않아도 sandbox 경계는 유지되며, 경계 밖 파일 수정이나 네트워크 접근이 필요하면 작업이 차단될 수 있습니다. 정책은 https://learn.chatgpt.com/docs/agent-approvals-security 에서 확인할 수 있습니다.

Responses 호출에는 store=false를 적용해 응답 객체의 기본 30일 application-state 저장을 끕니다. 이것만으로 Zero Data Retention이 켜지는 것은 아니며, 계정 설정에 따라 abuse-monitoring 로그 보관 정책은 별도로 적용됩니다. 민감한 코드라면 전달 전에 context 파일과 최종 diff를 확인하고, 조직 데이터 보존 설정을 확인하세요. 세부 내용은 https://developers.openai.com/api/docs/guides/your-data 에서 확인할 수 있습니다.
자동 전송 전에 task, context 파일, GPT 패치, 최종 diff에서 흔한 API 키·토큰·개인키 형태를 추가로 차단합니다. 이 탐지는 모든 비밀정보를 판별하지 못하므로 저장소 내용과 작업 내용을 사람이 먼저 확인해야 합니다.
