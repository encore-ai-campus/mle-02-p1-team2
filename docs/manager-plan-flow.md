# 관리자 모드 · 작업계획서 처리 흐름

기준: `feature/preventra-plus`의 `4808932` 커밋, 2026-10-07 확인. 관리자 화면에서 계획서를 연결한 이후의 실제 코드 흐름을 정리했다.

## 1. Excel 업로드 → 검토 → 적용

```mermaid
flowchart TD
    A["관리자 화면에서 작업계획서 연결"] --> B["xlsx 업로드 · 최대 10MB"]
    B --> C["파일 SHA-256 비교"]
    C --> D{"새 파일 내용인가?"}
    D -->|"예"| E["Excel을 읽고 작업표·필수 열 확인"]
    D -->|"아니오"| F["현재 미리보기 후보 재사용"]
    E --> G{"파일과 작업표를 읽을 수 있는가?"}
    G -->|"아니오"| ERR["오류 안내 · 양식과 날짜·시간 확인"]
    G -->|"예"| H["행별 날짜·시간·구역·작업·ID 검증"]
    H --> I["유효 작업을 WorkPlan으로 구성<br/>시트명·원본 행 번호 보존"]
    H --> J["잘못된 행·중복 작업은 제외<br/>제외 위치와 이유 기록"]
    I --> K{"사용 가능한 작업이 있는가?"}
    K -->|"아니오"| ERR
    K -->|"예"| P["현장명·작업 목록 미리보기"]
    F --> P
    J -.-> P
    P --> CMP["기존 적용 계획이 있으면<br/>작업 ID별 추가·변경·제외 비교"]
    CMP --> ACK{"제외된 행이 있는가?"}
    ACK -->|"예"| CONF["관리자가 제외된 행 확인 체크"]
    ACK -->|"아니오"| APPLY["이 계획서 적용 클릭"]
    CONF --> APPLY
    APPLY --> CHAT{"홈에서 적용하거나 대화가 없는가?"}
    CHAT -->|"예"| NEW["새 대화 생성"]
    CHAT -->|"아니오"| EXIST["현재 대화에 적용"]
    NEW --> DAY["초기 기준일 결정<br/>한국 오늘이 수록돼 있으면 오늘<br/>그 외에는 가장 이른 작업일"]
    EXIST --> DAY
    DAY --> SNAP["계획 전체·기준일·선택 작업을<br/>대화별 스냅샷으로 구성"]
    SNAP --> REV{"저장된 revision이 기대값과 같은가?"}
    REV -->|"아니오"| CONFLICT["다른 화면의 변경 안내<br/>최신 계획 다시 불러오기"]
    REV -->|"예"| DB["PostgreSQL에 스냅샷 저장<br/>revision 증가"]
    DB --> OK{"저장 성공?"}
    OK -->|"아니오"| SAVEERR["저장 실패 안내<br/>적용을 완료하지 않음"]
    OK -->|"예"| OPEN["미리보기 초기화<br/>관리자 작업계획 상담 화면 열기"]
```

- 필수 열은 작업일·시작·종료·동/구역·작업 내용이다. 작업 ID가 없으면 작업의 날짜·시간·구역·내용으로 자동 ID를 만든다.
- 파일 전체는 최대 10,000행, 유효 작업은 최대 500개다. 작업 행의 오류는 제외 목록으로 보여 주며, 유효 작업이 전혀 없으면 적용할 수 없다.
- 원본 Excel 파일은 저장하지 않는다. 파싱한 계획과 선택 상태를 저장한다. 미리보기만으로 계획이 적용되지는 않는다.

## 2. 적용된 계획 → 날짜별 작업 안전 보고서

```mermaid
flowchart TD
    A["적용된 계획 불러오기"] --> B["계획 기준일과 질문할 작업 선택<br/>해당 날짜 전체 또는 개별 작업"]
    B --> SAVE["선택 상태 저장<br/>날짜 변경 시 작업 선택 해제"]
    SAVE --> C{"선택 날짜에 작업이 있는가?"}
    C -->|"아니오"| EMPTY["등록 작업 없음 안내<br/>계획서 수록 날짜 표시"]
    C -->|"예"| REPORT["작업 안전 보고서 표시"]
    REPORT --> METRICS["예정 작업 수·조정 확인 조합 수<br/>미입력 항목이 있는 작업 수"]
    REPORT --> TIME["작업 시간대 타임라인"]
    REPORT --> AREA["구역별 계획 작업시간 합산"]
    REPORT --> CONTROLS["계획된 안전조치·추가 확인<br/>누락 항목·시트와 행 번호"]
    REPORT --> PAIRS["시간이 겹치는 작업 중<br/>같은 구역·장비 표기·책임자<br/>조정 확인 후보 표시"]
    REPORT --> QUERY["작업 내용과 장비로 사고사례 검색문 구성<br/>중복 제거 후 앞 8개 조합"]
    QUERY --> CACHE{"세션 캐시에 같은 검색문이 있는가?"}
    CACHE -->|"예"| RESULT["기존 조회 결과 사용"]
    CACHE -->|"아니오"| SIF["기존 search_sif_cases Tool 호출<br/>SIF 사고사례 후보 조회"]
    SIF --> STORE["조회 결과를 세션 캐시에 보관"]
    STORE --> RESULT
    RESULT --> STATUS{"조회 결과 상태"}
    STATUS -->|"실패"| FAIL["조회 실패 안내·재조회 버튼<br/>계획 보고서와 상담은 계속 제공"]
    FAIL -->|"재조회 클릭"| SIF
    STATUS -->|"후보 없음"| ZERO["해당 조건의 검색 후보 없음 안내"]
    STATUS -->|"후보 있음"| EVIDENCE["사례 제목·발췌·출처 표시"]
    EVIDENCE --> TYPES{"발췌에 명시된 사고유형이 있는가?"}
    TYPES -->|"예"| TYPECHART["조회 후보의 유형별 건수 표시"]
    TYPES -->|"아니오"| NOCLASS["유형 미기재 안내"]
    ZERO --> COUNT["작업별 조회 후보 건수 그래프"]
    TYPECHART --> COUNT
    NOCLASS --> COUNT
```

- 보고서의 SIF 조회는 보고서를 표시할 때 자동으로 실행된다. 별도의 상담 질문을 보낼 필요가 없다. 동일 검색문은 세션 캐시를 재사용하며 최대 64개를 보관한다.
- 시간대가 겹치고 구역·장비 표기·책임자 중 하나가 일치하면 조정 확인 후보가 된다. 최대 250개 조합을 표시하며, 개별 작업 선택 시 그 작업이 포함된 조합을 보여 준다.
- 구역별 시간은 작업별 예정 시간을 합산한다. 동시 작업도 각각 포함하고 인원수는 반영하지 않는다.
- 사고사례 그래프는 조회된 후보 건수다. 작업별 중복 사례와 검색 상한의 영향을 받는다. 전국 재해 통계·발생 확률·작업 위험도 점수로 해석하지 않는다.
- 선택 날짜에 작업이 없다는 안내는 계획서에 기재된 작업이 없다는 뜻이다. 실제 현장의 무작업을 확정하지 않는다.

## 3. 관리자 질문 → 계획 조회 → 근거 답변

```mermaid
flowchart TD
    A["관리자가 질문 입력<br/>또는 선택한 작업의 주의점 질문 클릭"] --> B["질문 제출 시의 계획·기준일·작업 선택을 복사"]
    B --> C["요청 ID 생성·처리 대기 등록"]
    C --> LOAD["현재 대화의 이전 질문과 답변 불러오기"]
    LOAD --> LC{"이력 조회 성공?"}
    LC -->|"아니오"| LOADERR["질문 실행 중단·이력 조회 실패 안내"]
    LC -->|"예"| DUP{"이미 처리한 요청 ID인가?"}
    DUP -->|"예"| STOP["재실행하지 않음"]
    DUP -->|"아니오"| AGENT["계획 문맥을 가진 관리자 Agent 구성<br/>최근 최대 8턴을 대화 문맥으로 사용"]
    AGENT --> INTENT{"계획에 관한 질문인가?"}
    INTENT -->|"예"| PLAN["get_work_plan으로 현재 계획 조회<br/>모델 지침에서 먼저 조회하도록 요구"]
    INTENT -->|"일반 질문"| OTHER["질문 목적에 필요한 Tool 선택"]
    PLAN --> DATE["조회 날짜·작업·오전 또는 오후 결정"]
    DATE --> ROWS["해당 조건의 작업·기재된 안전조치<br/>추가 확인·누락·조정 후보 반환"]
    ROWS --> EXISTS{"조회 조건에 작업이 있는가?"}
    EXISTS -->|"아니오"| CLARIFY["조회 날짜와 조건 설명<br/>작업 조건 확인 요청"]
    EXISTS -->|"예"| FACT["계획서 사실을 PLAN 근거로 사용"]
    FACT --> NEED{"추가 근거가 필요한가?"}
    NEED -->|"사고사례"| SIF["SIF Tool 조회"]
    NEED -->|"예방조치·작업 전 점검"| GUIDE["KOSHA Tool 조회"]
    NEED -->|"통계·추세"| STATS["통계 또는 추세 Tool 조회"]
    NEED -->|"계획 내용만 필요"| DRAFT["답변 구성"]
    OTHER --> DRAFT
    SIF --> DRAFT
    GUIDE --> DRAFT
    STATS --> DRAFT
    CLARIFY --> DRAFT
    DRAFT --> CHECK["답변 인용과 evidence_ids 비교<br/>이번 요청의 성공한 Tool 근거인지 확인"]
    CHECK --> VALID{"형식과 인용 검증 통과?"}
    VALID -->|"아니오"| ERROR["답변·출처 확인 실패 안내"]
    VALID -->|"예"| DISPLAY["답변과 사용한 계획·사고·가이드·통계 근거 표시"]
    DISPLAY --> HISTORY["질문·답변·제출 당시 계획 문맥 저장"]
    ERROR --> HISTORY
    HISTORY --> HOK{"대화 저장 성공?"}
    HOK -->|"예"| DONE["후속 질문 가능"]
    HOK -->|"아니오"| RETRY["화면 답변 유지·미저장 상태 표시<br/>저장 다시 시도"]
    RETRY --> HISTORY
```

- 계획서 질문의 오늘·당일·오전·오후는 화면에서 선택한 계획 기준일을 뜻한다. 내일·어제도 그 기준일의 다음 날·전날이다. 실제 오늘을 명시하면 한국 달력의 오늘을 조회한다.
- 다른 날짜를 명시하면 이전 날짜의 작업 선택을 이어받지 않는다. 전체 작업 요청은 선택을 해제해 해당 날짜 전체를 조회한다. 오전·오후는 정오 기준이며 정오를 걸치는 작업은 양쪽에 포함된다.
- 계획 Tool의 작업 내용과 조정 후보는 각각 앞 20개까지 모델에 전달된다. 작업이 20개를 넘으면 잘림 상태를 전달하고 작업 선택을 요청하도록 지시한다.
- 계획 조회 결과에는 이름·협력업체·현장 주소를 위한 필드를 포함하지 않으며, 책임자 이름이 포함된 조정 이유도 제외한다. 자유 입력 내용 전체의 익명화를 보장하는 처리라는 뜻은 아니다.
- 계획 먼저 조회, 자료 없음 시 조건 확인, 기재된 조치와 외부 예방조치 구분은 Agent 프롬프트 지침이다. 실제 Tool 선택은 모델이 수행한다.
- Agent는 최대 5라운드·6회 Tool 실행으로 제한한다. 답변의 인용 목록과 근거 ID의 일치 여부를 코드에서 확인한다.

## 4. 계획과 대화의 저장 → 다시 열기 → 변경·해제

```mermaid
flowchart TD
    A["적용된 계획"] --> PDB[("preventra_work_plans<br/>대화 ID·revision·계획 스냅샷")]
    B["관리자 질문과 답변"] --> HDB[("대화 이력<br/>요청 당시 계획 문맥·답변·사용 근거")]
    PDB --> LIST["관리자 사이드바<br/>현장별 저장된 계획과 수록 날짜"]
    LIST --> CLICK["현장과 날짜 선택"]
    CLICK --> OPEN["해당 대화와 최신 적용 계획 불러오기"]
    OPEN --> DAY["선택 날짜 저장·작업 선택 해제"]
    DAY --> REPORT["날짜별 보고서 다시 표시"]
    HDB --> OLD["이전 답변 다시 표시"]
    OLD --> SNAP["이 답변 당시의 작업계획서 펼치기<br/>당시 기준일·선택 작업·기재 내용 확인"]
    PDB --> UPDATE["날짜·작업 변경 또는 새 계획 적용"]
    UPDATE --> REV["기대 revision 확인 후 저장<br/>다른 화면의 변경이면 재조회 안내"]
    PDB --> DETACH["이 대화에서 계획 연결 해제"]
    DETACH --> CLEAR["스냅샷을 null로 저장<br/>revision 증가"]
    CLEAR --> KEEP["기존 대화와 답변 당시 계획 문맥 유지"]
```

질문 처리 대기, 답변 미저장 또는 계획 불러오기 실패 상태에서는 계획 적용·선택 변경·질문 제출 등의 조작을 막는다. 대화를 바꿀 때는 이전 계획 문맥을 먼저 초기화해 다른 대화의 계획이 섞이지 않게 한다.

## 코드 근거

아래 링크는 문서 작성에 사용한 구현 커밋을 가리킨다. 문서는 최신 main에서 분리해 작성했으며, 관리자 기능 분석 기준은 위에 명시한 feature 브랜치 커밋이다.

| 처리 | 구현 |
| --- | --- |
| 관리자 화면 진입 | [preventra_plus.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_plus.py) |
| 업로드·적용·선택·계획 이력 | [preventra_plan/ui.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_plan/ui.py) |
| Excel 검증·누락·계획 비교·조정 후보 | [vendor/work_plan.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_plan/vendor/work_plan.py) |
| 보고서·자동 사고사례 조회 | [preventra_plan/report.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_plan/report.py) |
| 스냅샷·모델 전달 작업 구성 | [preventra_plan/domain.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_plan/domain.py) |
| 계획 조회 Tool·관리자 Agent | [preventra_plan/agent.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_plan/agent.py) |
| 대화별 계획 저장·revision 충돌 | [preventra_plan/storage.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_plan/storage.py) |
| 요청 중복 방지·대화 저장 재시도 | [preventra_ui/state.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_ui/state.py) |
| 답변·계획 문맥 복원 | [preventra_ui/history.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_ui/history.py) |
| Tool 반복 제한·최종 인용 검증 | [preventra_agent/agent.py](https://github.com/fun5307/mle-02-p1-team2/blob/4808932fa97c1ac852b8c25ad8ec593f513dac9e/src/Project_1/preventra_agent/agent.py) |
