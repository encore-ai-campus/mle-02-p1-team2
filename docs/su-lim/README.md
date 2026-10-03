# su-lim 작업 폴더 (M1~M4)

| 단계 | 파일 | 내용 |
|---|---|---|
| M1 | notebooks/su-lim/01_data_check.ipynb | 원본 6개 파일 구조·결측·중복·기준연도 확인 |
| M2 | notebooks/su-lim/02_m2_raw_점검.ipynb, docs/su-lim/M2_전처리_명세서.md | 전처리 기준과 처리 결과 |
| M3 | notebooks/su-lim/03_m3_기술통계분석.ipynb | 기술통계 분석 |
| M4 | notebooks/su-lim/04_m4_벡터DB적재.py | 사례 6,032건 임베딩 후 ChromaDB 적재 |

## 환경
- Python 3.12, uv, ChromaDB, OpenAI text-embedding-3-small
- API 키와 원본 데이터는 저장소에 포함하지 않았습니다. (.env, data/ 제외)

## 진행 상황
- M5 이후(RAG 체인, 평가, 개선 실험, 대시보드)는 진행 중입니다.
