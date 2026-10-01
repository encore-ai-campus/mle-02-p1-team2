"""Profile the collected SIF API JSONL without reproducing incident narratives."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import pandas as pd


FIELD_LABELS = {
    "cateSeNm": "업종 구분",
    "sifLclsfNm": "산재업종 대분류",
    "sifMclsfNm": "산재업종 중분류",
    "sifSclsfNm": "산재업종 소분류",
    "disasterType": "재해종류",
    "disasterOverview": "재해개요",
    "orgtNm": "기인물",
    "situation": "고위험작업·상황",
    "disasterFactor": "재해유발요인",
    "dcrsCntrplnCn": "위험성 감소대책",
}


def profile(path: Path, output: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"API 코퍼스가 없습니다: {path}")

    frame = pd.read_json(path, lines=True, encoding="utf-8")
    if frame.empty:
        raise ValueError(f"API 코퍼스가 비어 있습니다: {path}")

    nested = pd.json_normalize(frame["fields"].map(lambda value: value if isinstance(value, dict) else {}))
    for field in FIELD_LABELS:
        if field not in nested:
            nested[field] = pd.NA

    filled = lambda values: values.notna() & values.astype("string").str.strip().ne("")
    rows = len(frame)
    duplicate_ids = int(frame["case_id"].duplicated().sum()) if "case_id" in frame else rows
    empty_content = int((~filled(frame["page_content"])).sum()) if "page_content" in frame else rows
    char_lengths = frame.get("page_content", pd.Series(dtype="string")).fillna("").astype("string").str.len()

    field_lines = ["| 필드 | 입력 행 | 값 있음 | 결측/빈 값 | 고유값 |", "|---|---:|---:|---:|---:|"]
    for field, label in FIELD_LABELS.items():
        present = filled(nested[field])
        field_lines.append(
            f"| {label} (`{field}`) | {rows} | {int(present.sum())} | {int((~present).sum())} | {int(nested.loc[present, field].nunique())} |"
        )

    query_counts = frame.get("retrieved_query", pd.Series(dtype="string")).fillna("(없음)").value_counts()
    query_lines = ["| 검색어 | 수집 사례 수 |", "|---|---:|"]
    for query, count in query_counts.items():
        query_lines.append(f"| {query} | {int(count)} |")

    def top_counts(field: str, limit: int = 10) -> list[tuple[str, int]]:
        values = nested[field].astype("string").str.strip()
        values = values[values.notna() & values.ne("")]
        return [(str(value), int(count)) for value, count in values.value_counts().head(limit).items()]

    category_lines = ["| 구분 | 값 | 사례 수 |", "|---|---|---:|"]
    for field, label in (("cateSeNm", "업종 구분"), ("disasterType", "재해종류")):
        counts = top_counts(field)
        category_lines.extend(f"| {label} | {value} | {count} |" for value, count in counts)
        if not counts:
            category_lines.append(f"| {label} | (값 없음) | 0 |")

    report = [
        "# SIF API 코퍼스 품질 프로파일",
        "",
        f"- 점검일: {date.today().isoformat()}",
        f"- 입력 파일: `{path.as_posix()}` ({path.stat().st_size:,} bytes)",
        "- 처리: pandas JSONL 구조·품질 통계만 산출; 사고 서술 본문은 보고서에 복사하지 않음",
        "- 데이터 출처: [SIF 아카이브 조회 API](https://www.data.go.kr/data/15161362/openapi.do)",
        "",
        "## 전체 요약",
        "",
        f"- 레코드: {rows:,}",
        f"- 고유 사례 ID: {int(frame['case_id'].nunique()) if 'case_id' in frame else 0:,}; 중복 ID: {duplicate_ids:,}",
        f"- 빈 검색 본문: {empty_content:,}",
        f"- 검색 본문 길이(문자): 최소 {int(char_lengths.min())}, 중앙값 {int(char_lengths.median())}, 95백분위 {int(char_lengths.quantile(.95))}, 최대 {int(char_lengths.max())}",
        f"- 검색어 수: {int(frame['retrieved_query'].nunique()) if 'retrieved_query' in frame else 0}",
        "- 표본 한계: 재해개요 키워드 검색으로 수집한 결과이며 전체 아카이브를 대표한다고 볼 수 없음",
        "",
        "## API 필드 품질",
        "",
        *field_lines,
        "",
        "## 검색어별 수집량",
        "",
        *query_lines,
        "",
        "## 주요 범주 상위 10개",
        "",
        *category_lines,
        "",
        "## 색인 전 판단",
        "",
        "- case_id 중복·본문 누락이 있으면 해당 행을 색인 전 격리하고 원인을 확인합니다.",
        "- 검색어별 사례 수는 중복 제거 과정에서 사례를 처음 발견한 seed에만 귀속된 값이며, 검색어별 전체 일치량이 아닙니다.",
        "- `cateSeNm`이 단일 값이면 업종 필터에 사용하지 말고, 값이 있는 `sifLclsfNm`·`sifMclsfNm`·`sifSclsfNm`만 활용합니다.",
        "- `disasterType`이 전부 비어 있으면 필터·라벨로 쓰지 않으며 원본에 없는 재해종류를 추론해 채우지 않습니다.",
        "- 검색어별 수집 차이와 seed 순서에 따른 중복 제거가 표본 분포에 영향을 주므로 결과를 전체 아카이브 성능으로 해석하지 않습니다.",
        "- 이 프로파일은 구조 점검이며 평가 질문별 관련 사례 라벨링을 대체하지 않습니다.",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(report), encoding="utf-8")
    print(f"records={rows} duplicate_ids={duplicate_ids} empty_content={empty_content}")
    print(f"profile={output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile a collected SIF API JSONL without exporting narratives")
    parser.add_argument("--input", type=Path, default=Path("data/raw/sif_openapi_cases.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/sif_api_corpus_profile.md"))
    args = parser.parse_args()
    profile(args.input, args.output)


if __name__ == "__main__":
    main()
