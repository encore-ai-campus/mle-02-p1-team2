# Streamlit Cloud·Supabase 준비 상태

확인일: 2026-10-03

## 현재 개인 앱과 팀 Cloud 앱

팀 가이드는 `encore-ai-campus/mle-02-p1-team2` 저장소의 `feature/cloud-statistics` 브랜치와 `src/Project_1/app.py`를 기준으로 한다. 현재 `C:\SANUP-P`는 `feature/sanup-p-rag-evaluation`에서 작업 중인 개인 프로젝트이며, `app_personal.py`는 개인 parquet 파일과 로컬 Chroma 색인을 읽는다. 그래서 팀 Cloud 앱을 개인 앱과 분리한 `src/Project_1/`에 가져왔다. Streamlit Cloud 진입 파일은 가이드와 같은 `src/Project_1/app.py`다.

가져온 코드 기준 커밋은 `61d64ea718fb20e1ea1c8efe4cf3e0816259008b`이다. 팀 앱 코드, 서비스 모듈, 고정 requirements, README, 제공 테스트를 복사했다. 로컬 Git 명령은 Windows Git 인증 오류가 났지만, 연결된 GitHub 저장소 읽기 권한으로 해당 브랜치 파일을 확보했다. 개인 앱과 공용 DB 스키마는 변경하지 않았다.

## 연결 설정 확인

`.env`에서 아래 변수는 모두 값이 설정된 상태임을 확인했다. 값 자체는 출력하거나 이 문서에 기록하지 않았다.

- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `OPENAI_API_KEY`

`DATABASE_URL`로 읽기 전용 연결을 확인했다. 데이터베이스는 PostgreSQL 17이고 `vector` 확장 0.8.2가 활성화돼 있다. `industrial-statistics` 버킷은 비공개로 존재하며 필요한 통계 CSV 18개 경로도 객체 메타데이터에서 확인했다. 파일 내용은 내려받지 않았다.

## 공유 DB에서 확인한 RAG 자료

테이블 행 수와 메타데이터만 조회했다. 원문 내용을 읽거나 변경하지 않았다.

| 자료 | 행 수 | 확인한 정보 |
| --- | ---: | --- |
| `public.rag_day1_documents` | 6,152 | `sif_case` 6,032행, `industry_stat` 120행. `text-embedding-3-small`, 1,536차원 벡터 |
| `public.langchain_pg_embedding` | 813 | `kosha_guides` 컬렉션, 1,536차원 벡터 |

개인 로컬 색인의 코퍼스 구성과 테이블 이름이 다르므로 개인 앱의 `PersonalRetriever`가 이 DB를 자동으로 읽지는 않는다. Cloud 브랜치에서 사용하도록 만든 검색·통계 로더를 따라야 한다. ⑥ 사고조사보고서가 공유 DB에 포함되는지는 이 메타데이터 점검만으로 확인되지 않았다.

## 팀 제공 코드 최초 검사에서 발견한 문제와 수정 범위

팀 제공 단위 테스트는 Cloud 전용 가상환경에서 16개 모두 통과했다. 하지만 앱 첫 화면을 실제 설정으로 실행하면 Storage CSV 로딩이 `HTTP 400`으로 중단된다. Storage API가 `authorization` 헤더를 요구했는데 팀의 `statistics_storage.py`는 `apikey` 헤더만 보낸다. `SUPABASE_SECRET_KEY`가 `sb_secret_` 형식인 것도 확인했다. 이 새 형식은 JWT가 아니므로 `Authorization: Bearer <sb_secret_...>`를 임의로 추가하면 Storage가 `Invalid Compact JWS`로 거부한다.

Supabase 공식 안내는 새 publishable/secret 키를 `apikey` 헤더에만 보내고, 이를 Bearer 토큰으로 보내지 말라고 한다. 반면 Storage의 비공개 객체 접근은 Authorization 문맥을 요구한다. 따라서 사용자가 받은 네 설정값만으로는 현재 팀 코드의 Storage 요청이 성립하지 않는다. 앱 코드나 서버 측 Storage 인증 방식을 팀에서 보완해야 한다. `service_role` 같은 별도 JWT를 추가하라는 임시 조치는 권한이 더 넓으므로 팀 소유자가 승인하고 범위를 정하기 전에는 적용하지 않는다.

공식 Python 클라이언트(`supabase` 2.32.0)도 임시 가상환경에서 별도로 확인했다. 비공개 파일 다운로드는 `404 Bucket not found`, 버킷 목록 조회는 `403 Invalid Compact JWS`로 실패했다. 클라이언트가 새 `sb_secret_` 값을 Bearer 문맥에도 사용하면서 Storage가 유효한 JWT로 처리하지 못한 결과와 일치한다. SDK를 requirements에 추가해도 이 인증 문제는 해결되지 않아 프로젝트 의존성에는 넣지 않았다. Supabase 문서도 새 키를 `apikey`에만 두도록 안내하고, 비공개 객체 다운로드에는 사용자 JWT 또는 서버에서 만든 만료형 URL을 설명한다 ([API keys](https://supabase.com/docs/guides/getting-started/api-keys), [private downloads](https://supabase.com/docs/guides/storage/serving/downloads)).

처음 팀 제공 코드를 실행했을 때는 탭·통계 카드가 표시되지 않았다. 이때는 사용자 질문이나 OpenAI 호출도 실행하지 않았다. 이후 개인 Fork 후보에서 Storage 요청 실패 시 DB의 2025년 통계로 전환하도록 보완했다. 보완된 후보는 아래 재검증에서 화면 첫 실행에 성공했지만, 비공개 Storage 인증 자체가 해결된 것은 아니다.

## Cloud 배포 진행 상태

1. 개인 GitHub 계정 `kimgomja`의 공개 Fork `https://github.com/kimgomja/mle-02-p1-team2`를 사용한다. `Copy the main branch only`를 해제해 Fork에 17개 브랜치가 있다.
2. 개인 브랜치 `codex/cloud-statistics-db-fallback`을 만들고 `22790a4` 커밋을 푸시했다. 팀 저장소나 공용 브랜치는 수정하지 않았다.
3. Storage 인증이 실패하면 `public.rag_day1_documents`에서 2025년 `industry_stat`만 읽어 통계를 표시하는 대체 경로를 추가했다. 읽기 전용 트랜잭션을 사용하며 4개 지표·산업중분류 30개·규모 구간 10개를 확인한다. `자료 없음`은 결측으로 둔다.
4. 새 Fork 작업 트리에서 테스트 18개가 통과했다. 이후 로컬 원본 통계 CSV 네 종류를 로더에 넣어 확인했는데 UTF-8 전용이라 CP949 파일에서 `UnicodeDecodeError`가 나는 것을 발견했다. 로더를 UTF-8 BOM/CP949 양쪽을 읽도록 고치고, 업종 30개·숫자 값 검증을 추가했다. 수정 테스트는 20개 통과했고, 원본 CSV 4개는 각각 300행·업종 30개로 변환됐으며 사망만인율의 기존 결측 14개도 유지했다. 수정 사항은 개인 Fork 브랜치 `codex/cloud-statistics-db-fallback`에 코드 커밋 `388fa58`, 배포 Python 설정 안내 커밋 `63f29fc`로 반영했다.
5. 2026-10-03 로컬 실제 설정으로 Streamlit AppTest를 다시 실행했다. 예외 없이 상담·통계 탭과 통계 KPI 2개가 표시됐고, Storage 인증 실패 후 2025 DB 통계를 사용한다는 안내가 나왔다. DB 대체 경로가 첫 화면을 띄우는 것은 확인했지만 통계 범위는 2025년뿐이다.
6. 같은 날 평가 질문 `고소작업대 선정과 관리 방법`으로 실제 DB 검색과 OpenAI 답변 생성까지 한 번 실행했다. SIF 3건, KOSHA GUIDE 3건, 예방조치 2개와 출처 ID가 반환됐다. 한 질문의 통합 확인이며 21문항 전체 평가나 답변 사실성 검토 완료로 확대 해석하지 않는다.
7. 앱 안내문은 2025년 DB 통계 사용과 2020~2024년 자료 공백을 알린다. 6년 추세는 Storage가 정상화되기 전까지 완전하지 않다.
8. Streamlit 배포 폼은 개인 Fork, `codex/cloud-statistics-db-fallback`, `src/Project_1/app.py`로 설정했다. 2026-10-03 재확인에서 Advanced settings의 Python 버전을 3.12로 바꾸고 저장했다. 앱 생성과 Secrets 입력은 진행하지 않았다.
9. 공공데이터포털의 SIF 파일 데이터 이용조건은 `공공저작물: 출처표시, 변경금지(제3유형)`으로 표시돼 있다. 현재 RAG는 사례 문서를 검색하고 일부 발췌를 화면에 보여준다. 공개 Streamlit 앱으로 이 기능을 외부에 제공해도 되는지 확인되기 전에는 공개 배포를 진행하지 않는다. 출처: [SIF 아카이브 파일데이터](https://www.data.go.kr/data/15140383/fileData.do).
10. Streamlit 배포 화면은 `public app`을 만든다고 표시한다. 이 앱은 익명 방문자도 챗 입력으로 OpenAI 검색 재정렬·답변 생성을 반복할 수 있고 앱에 로그인·사용량 제한은 없다. 공개 실행 전에는 사용 권한 외에도 API 사용량 상한/알림과 접근 제어 방법을 정해야 한다.

현재 Streamlit 로그인과 GitHub Fork 연결은 확인했다. GitHub 앱 커넥터의 브랜치·파일 쓰기는 403으로 막혔지만, 로그인된 개인 GitHub Fork로 Git 작업 트리를 이용해 새 브랜치에 네 파일을 커밋·푸시했다. Streamlit 배포 폼의 저장소·브랜치·진입 파일·Python 3.12 설정은 준비됐지만 앱과 Secrets는 만들지 않았다. 실제 Secrets 값은 저장소나 이 문서에 기록하지 않는다.

## 알게 된 점과 유의사항

- Supabase 설정값이 있어도 앱 코드가 그 DB와 Storage를 사용하지 않으면 Cloud RAG는 동작하지 않는다.
- 공용 DB에는 SIF·통계와 KOSHA GUIDE 임베딩이 확인됐지만, 개인 코퍼스 전체가 그대로 올라간 것은 아니다.
- Storage 버킷은 비공개다. 앱이 어떤 방식으로 파일을 읽는지는 팀의 `statistics_storage.py`를 확인해야 한다.
- 이번 확인은 읽기 전용이다. 테이블·벡터·파일을 추가, 삭제, 재색인하지 않았다.
- 팀 제공 코드의 최초 실제 첫 화면 검사는 Storage 오류로 실패했다. 수정 후보는 뒤의 AppTest에서 탭·지표 카드까지 표시했지만, 모의 테스트 통과나 DB 대체 경로를 Storage 통합 성공으로 해석하면 안 된다.
- 팀에서 공유한 다섯 설정값은 로컬 `.env`에 확인됐지만, Storage 인증이 성공한 것은 아니다. Streamlit Cloud에 먼저 배포해도 같은 첫 화면 로딩에서 막힐 가능성이 높다.
- 팀 저장소의 제공 테스트 16개는 통과했지만, 실제 통계 파일 다운로드는 실패했다. 배포 완료 판정에는 실제 Storage 연결과 화면 검증이 남아 있다.
- 현재 Fork 후보 브랜치 `codex/cloud-statistics-db-fallback`은 테스트 20개가 통과했다. 이는 모의·로컬 테스트이며 실제 Cloud Supabase/OpenAI 통합 성공을 의미하지 않는다.
- Cloud CSV 로더는 실제 원본 CSV 4개를 사용해 인코딩과 행 구조를 점검했다. CP949 지원을 추가한 뒤 각 파일 300개 long 행/30개 업종이 만들어지고 사망만인율 14개 결측이 보존됐다. 동일 코드는 개인 Fork 브랜치에 반영했다. Storage 원격 파일 실제 다운로드는 아직 확인할 수 없다.
- SIF 파일데이터는 출처표시와 변경금지 조건이 명시된 공공저작물 제3유형이다. 공개 앱의 RAG 검색·발췌가 그 조건에 맞는지 담당 교사나 권리 보유 기관의 확인이 필요하다.
- 안전한 다음 단계는 SIF 공개 사용 범위를 확인하는 것이다. 허용이 확인되면 Streamlit 앱 생성과 Secrets 설정을 진행하고, 허용되지 않으면 공개 앱에서 SIF 검색·원문 발췌를 제외하는 구성이 필요하다.
- Streamlit의 공개 앱은 OpenAI 키를 앱 서버 Secrets에 두더라도 방문자가 채팅을 반복 실행할 수 있다. 배포 전에 OpenAI 계정의 사용량 한도·알림과 앱 접근 제어 여부를 확인한다.
- 현재 Fork의 앱 진입점은 `src/Project_1/app.py`이고 같은 폴더에 `requirements.txt`가 있다. Streamlit 공식 문서에 따라 진입점 옆 의존성 파일이 저장소 루트보다 우선한다. 그래도 배포 화면의 Python 버전은 별도로 3.12에 맞춰야 한다 ([파일 배치](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization), [의존성 탐색](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), [Python 버전 설정](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)).

## 2026-10-03 추가 재검증

- 앱 전용 임시 Python 3.12 환경에 `src/Project_1/requirements.txt`를 설치했다. 개인 노트북용 기본 가상환경에는 Cloud 앱 의존성이 없어서 테스트가 일부 import 단계에서 실패했으며, 두 환경을 분리해 해결했다. 재현할 때 쓸 `.venv-cloud` PowerShell 절차를 `src/Project_1/README.md`에 적고 `.gitignore`에도 추가했다.
- 전용 환경에서 `src/Project_1/tests` 전체 20개가 통과했다.
- 실제 설정을 읽는 첫 화면 AppTest는 예외 0건, 오류 0건으로 끝났다. 상담·통계 탭 2개, 통계 KPI 2개가 나왔고 Storage 인증 실패 후 2025년 DB 통계로 표시한다는 안내가 보였다. 질문은 제출하지 않아 이번 확인에서 LLM 호출은 발생하지 않았다.
- 상담 화면 상단에 참고용 답변임을 알리고, 현장 위험성평가·작업계획·안전관리자 지침 확인 및 위험 미통제 시 작업중지를 안내하는 문구를 추가했다. 재실행한 AppTest에서 문구 표시·탭·지표와 예외 0건을 확인했다. 이 화면 보완은 현재 로컬 작업본에만 있다.
- 이 결과는 공개 Streamlit Cloud 배포 검증이 아니다. Cloud 앱은 생성되지 않았으며, 실제 배포 환경에서 Supabase 연결·OpenAI 답변·익명 사용량 통제를 확인해야 한다.

## Git 이력 보안 점검

- 현재 `.env`는 작업 폴더에 있지만 `.gitignore` 대상이고 현재 추적 파일은 아니다. 다만 후보 Fork 브랜치의 Git 이력에 `DATABASE_URL` 한 줄을 추가한 `dc2778b`와 삭제한 `12c4b4b`가 모두 남아 있다. 추가 커밋의 값은 비어 있거나 예시가 아닌 PostgreSQL 접속 문자열 형식이며, 실제 값은 이 문서에 복사하지 않았다.
- 삭제 커밋은 비밀값을 Git 이력에서 지우지 않는다. 후보 원격 브랜치의 이력에서 해당 추가 커밋이 조상으로 확인됐으며, 2026-10-03 GitHub 화면에서 저장소가 `Public`임을 확인했다. 따라서 해당 접속정보는 공개된 것으로 간주한다.
- 현재 로컬 `.env`의 DB 주소·사용자·비밀번호 조합은 과거 커밋과 다르고, 현재 Supabase URL도 과거 DB 연결과 다른 프로젝트로 보인다. 따라서 지금 `.env`가 정상 연결된다는 것만으로 과거 프로젝트의 비밀번호가 폐기됐다고 확인할 수 없다. 어떤 프로젝트인지 비밀값을 공유하지 않는 방식으로 소유자와 대조한 뒤 그 프로젝트의 DB 비밀번호를 교체해야 한다.
- 간단한 이력 패턴 검사에서는 이 `.env`의 Supabase `DATABASE_URL` 외에 OpenAI 키·Supabase secret·GitHub token 형식은 발견되지 않았다. 노트북·예시 파일에서 찾은 나머지 DB URL은 로컬 주소나 예시 값이었다. 자동 패턴 검사는 모든 종류의 비밀정보를 보증해서 찾아내지는 못한다.
- 먼저 프로젝트 소유자와 조율해 Supabase Dashboard의 Database Settings에서 DB 비밀번호를 교체하고 로컬 `.env`와 사용하는 외부 서비스 연결정보를 새 값으로 갱신한다. Supabase 문서에 따르면 관리형 서비스에는 별도 중단이 없지만, 고정 연결정보를 가진 외부 앱은 수동 갱신이 필요하다 ([Postgres Roles·비밀번호 변경](https://supabase.com/docs/guides/database/postgres/roles)). 다음으로 개인 Fork 후보 브랜치에서 민감한 파일을 제거한 이력으로 바꿀지 결정한다. GitHub는 이력 재작성 전에 자격증명을 먼저 폐기·교체하고, 포크·기존 복제본·PR 기록과 협업자 작업을 함께 정리해야 한다고 안내한다 ([민감정보 제거 안내](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)).
- 이번 작업에서는 공유 DB 연결을 끊거나 비밀번호를 바꾸지 않았고, 원격 브랜치 이력을 강제 갱신하지 않았다. 배포 Secrets도 입력하지 않았다. 교체 뒤에만 새 DB 연결 문자열을 안전한 저장소에 설정한다.

## 이번 추가 점검에서 알게 된 점

- Cloud 앱의 테스트는 개인 프로젝트 기본 환경과 분리한 Python 3.12에서 실행해야 한다. 기본 환경에 의존성을 섞으면 개인 노트북 작업에 영향을 줄 수 있다.
- 첫 화면은 대체 통계 경로로 표시되지만 2020~2024 통계는 여전히 비어 있고, 비공개 Storage 인증 문제도 남아 있다.
- 공개 배포 폼의 Python 버전은 3.12로 저장했다. 앱 게시와 Secrets 입력은 SIF·KOSHA 공개 이용 범위 및 익명 OpenAI 사용량 보호가 확인될 때까지 보류한다.
- 상담 첫 화면에서 AI 답변의 사용 범위와 위험 통제 실패 시 대응을 미리 읽을 수 있게 했다. 답변 안의 면책 문구만 기대하는 것보다 사용자가 질문하기 전 기준을 알려 주는 것이 명확하다.
- Git 커밋에서 `DATABASE_URL`이 한 번 추가됐다가 삭제된 이력을 찾았다. 연결 문자열은 폐기·교체하고 후보 브랜치 이력도 정리하기 전까지 배포에 사용하지 않는다.
