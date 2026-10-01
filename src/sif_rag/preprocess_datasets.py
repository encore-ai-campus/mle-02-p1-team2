"""Prepare downloaded occupational-safety datasets with pandas.

The original files under data/raw are treated as immutable inputs. This script
creates tidy, UTF-8-SIG CSVs and a Markdown quality report under data/processed.
"""

from __future__ import annotations

import argparse
import io
import re
import unicodedata
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd


STAT_FILES = {
    "15084672_industry_size_accident_injured_2025.csv": "accident_injured_count",
    "15084674_industry_size_fatalities_2025.csv": "accident_fatality_count",
    "15064487_industry_size_workplaces_2025.csv": "workplace_count",
    "15064491_industry_size_fatality_rate_2025.csv": "fatality_rate_per_10000",
}
AGG_FATALITIES_FILE = "15084663_accident_fatalities_by_size_2004_2025.csv"
AI_INDEX_FILE = "15162988_accident_prevention_ai_dataset_20260917.csv"
GLOSSARY_ZIP = "15161288_industrial_safety_terms_20251231.zip"


def read_csv_smart(path: Path) -> tuple[pd.DataFrame, str]:
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"지원 인코딩으로 읽을 수 없습니다: {path}")


def clean_label(value: object) -> str:
    if pd.isna(value):
        return ""
    # These source exports contain visual spacing inside some category names.
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value)))


def clean_size(value: object) -> str:
    label = clean_label(value)
    label = label.replace("~", "-").replace("～", "-")
    return label


def find_size_columns(columns: list[str], metric: str) -> list[tuple[str, str]]:
    pairs = []
    suffixes = ("근로자수", "사업장수")
    for column in columns:
        raw = str(column).strip()
        if raw in {"대업종", "구분"}:
            continue
        label = raw
        for suffix in suffixes:
            if label.endswith(suffix):
                label = label[: -len(suffix)].strip()
                break
        label = clean_size(label)
        if re.search(r"\d+인", label):
            pairs.append((raw, label))
    if len(pairs) != 10:
        raise ValueError(f"사업장 규모 컬럼 10개를 찾지 못했습니다 ({metric}): {pairs}")
    return pairs


def prepare_industry_metric(path: Path, metric: str) -> tuple[pd.DataFrame, dict[str, object]]:
    source, encoding = read_csv_smart(path)
    source_rows = len(source)
    source = source.dropna(how="all").copy()
    source["_source_row"] = source.index + 2
    source["industry_major_raw"] = source["대업종"].astype("string")
    source["industry_mid_raw"] = source["구분"].astype("string")
    source["industry_major"] = source["대업종"].map(clean_label)
    source["industry_mid"] = source["구분"].map(clean_label)
    size_columns = find_size_columns(list(source.columns), metric)
    value_columns = [column for column, _ in size_columns]
    long = source.melt(
        id_vars=["_source_row", "industry_major_raw", "industry_mid_raw", "industry_major", "industry_mid"],
        value_vars=value_columns,
        var_name="source_size_column",
        value_name="value",
    )
    size_map = dict(size_columns)
    long["business_size"] = long["source_size_column"].map(size_map)
    long["metric"] = metric
    long["reference_date"] = "2025-12-31"
    long = long.rename(columns={"_source_row": "source_row"})
    long = long[[
        "reference_date", "industry_major", "industry_mid", "business_size", "metric", "value",
        "industry_major_raw", "industry_mid_raw", "source_size_column", "source_row",
    ]]
    report = {
        "file": path.name,
        "encoding": encoding,
        "source_rows": source_rows,
        "blank_rows_removed": source_rows - len(source),
        "output_rows": len(long),
        "industry_groups": int(source["industry_major"].nunique()),
        "industry_categories": int(source["industry_mid"].nunique()),
        "size_bands": int(long["business_size"].nunique()),
        "null_values": int(long["value"].isna().sum()),
        "duplicate_industry_keys": int(source.duplicated(["industry_major", "industry_mid"]).sum()),
        "zero_values": int(long["value"].eq(0).sum()),
    }
    return long, report


def prepare_historical_fatalities(path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    source, encoding = read_csv_smart(path)
    source_rows = len(source)
    source = source.dropna(how="all").copy()
    source["source_row"] = source.index + 2
    year_columns = [c for c in source.columns if re.fullmatch(r"\d{4}년 사고사망자수", str(c).strip())]
    if not year_columns:
        raise ValueError(f"연도별 사고사망자 컬럼을 찾을 수 없습니다: {path}")
    long = source.melt(id_vars=["구분", "source_row"], value_vars=year_columns,
                       var_name="source_year_column", value_name="value")
    long["business_size"] = long["구분"].map(clean_size)
    long["year"] = long["source_year_column"].str.extract(r"(\d{4})").astype(int)
    long["metric"] = "accident_fatality_count"
    long = long[["year", "business_size", "metric", "value", "구분", "source_year_column", "source_row"]]
    report = {
        "file": path.name, "encoding": encoding, "source_rows": source_rows,
        "output_rows": len(long), "year_min": int(long["year"].min()),
        "year_max": int(long["year"].max()), "size_bands": int(long["business_size"].nunique()),
        "null_values": int(long["value"].isna().sum()),
        "duplicate_size_year_keys": int(long.duplicated(["business_size", "year"]).sum()),
    }
    return long, report


def prepare_ai_index(path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    source, encoding = read_csv_smart(path)
    rename = {"구분": "document_type", "개방url": "source_url", "데이터규모": "published_scope", "주요설명": "description"}
    missing = set(rename) - set(source.columns)
    if missing:
        raise ValueError(f"AI 자료 목록 필수 컬럼 누락: {sorted(missing)}")
    result = source.rename(columns=rename)[list(rename.values())].copy()
    for column in result.columns:
        result[column] = result[column].astype("string").str.strip()
    source_rows = len(result)
    result = result.dropna(how="all").drop_duplicates(subset=["source_url"], keep="first").reset_index(drop=True)
    result.insert(0, "source_id", [f"ai-index-{i:03d}" for i in range(1, len(result) + 1)])
    report = {"file": path.name, "encoding": encoding, "source_rows": source_rows,
              "output_rows": len(result), "duplicate_urls_removed": source_rows - len(result),
              "null_cells": int(result.isna().sum().sum()),
              "is_document_index_not_corpus": True}
    return result, report


def prepare_glossaries(path: Path) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    reports: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".csv"):
                continue
            frame = pd.read_csv(io.BytesIO(archive.read(member)), encoding="utf-8-sig")
            source_rows = len(frame)
            if "용어1" in frame.columns:
                canonical_col = "용어1"
                variant_cols = [c for c in frame.columns if re.fullmatch(r"용어\d+", str(c))]
                dictionary_type = "industry_safety_synonyms"
            elif "표제어" in frame.columns:
                canonical_col = "표제어"
                variant_cols = [c for c in frame.columns if re.fullmatch(r"검색어\d+", str(c))]
                dictionary_type = "portal_search_terms"
            else:
                reports.append({"member": member, "source_rows": source_rows,
                                "output_pairs": 0, "status": "unrecognized columns"})
                continue
            before = len(records)
            for _, row in frame.iterrows():
                canonical = str(row.get(canonical_col, "")).strip()
                if not canonical or canonical.lower() == "nan":
                    continue
                canonical_norm = unicodedata.normalize("NFKC", canonical).casefold().strip()
                for position, column in enumerate(variant_cols, start=1):
                    value = row.get(column)
                    if pd.isna(value):
                        continue
                    variant = str(value).strip()
                    if not variant:
                        continue
                    variant_norm = unicodedata.normalize("NFKC", variant).casefold().strip()
                    if canonical_norm == variant_norm:
                        continue
                    records.append({
                        "dictionary_type": dictionary_type,
                        "canonical_term": canonical,
                        "variant": variant,
                        "variant_position": position,
                        "canonical_norm": canonical_norm,
                        "variant_norm": variant_norm,
                        "source_member": member,
                    })
            reports.append({"member": member, "source_rows": source_rows,
                            "source_columns": len(frame.columns),
                            "pairs_before_dedup": len(records) - before,
                            "status": "processed"})
    pairs = pd.DataFrame(records)
    if not pairs.empty:
        before = len(pairs)
        pairs = pairs.drop_duplicates(["dictionary_type", "canonical_norm", "variant_norm"], keep="first")
        pairs = pairs.drop(columns=["canonical_norm", "variant_norm"]).reset_index(drop=True)
        deduplicated = before - len(pairs)
    else:
        deduplicated = 0
    for item in reports:
        item["pairs_after_dedup"] = int((pairs["source_member"] == item["member"]).sum()) if not pairs.empty else 0
    reports.append({"zip_file": path.name, "total_pairs_after_dedup": len(pairs),
                    "duplicate_pairs_removed": deduplicated,
                    "note": "query-expansion support only; not accident evidence"})
    return pairs, reports


def write_report(path: Path, stats: list[dict[str, object]], historical: dict[str, object],
                 ai: dict[str, object], glossary: list[dict[str, object]]) -> None:
    lines = [
        "# 산업재해 데이터 전처리 결과",
        "",
        f"- 실행일: {date.today().isoformat()}",
        "- 도구: Python pandas 기반 CSV 정규화 및 검증",
        "- 원본 파일: `data/raw/`에서 읽기 전용으로 사용",
        "- 산출물: `data/processed/`의 UTF-8-SIG CSV",
        "",
        "## 처리 기준",
        "",
        "- 통계 자료는 업종·규모별 wide 형식을 업종·규모·지표·값의 long 형식으로 변환했습니다.",
        "- 업종명과 사업장 규모의 표기 공백만 정리하고 원본 표기 컬럼을 함께 보존했습니다.",
        "- 결측 통계값은 0으로 치환하지 않았습니다. 사망만인율의 NaN은 원자료에서 값이 비어 있음을 뜻합니다.",
        "- 연도별 규모별 사망자 자료는 연도·규모 long 형식으로 변환했습니다.",
        "- 용어 사전은 표제어-유의어 쌍으로 펼쳤습니다. 사고 근거자료로 사용하지 않습니다.",
        "- AI친화 학습데이터는 원문 사고보고서가 아니라 공개 자료 경로 목록으로 정리했습니다.",
        "",
        "## 업종·규모별 통계",
        "",
        "| 지표 | 원본 행 | 결과 행 | 대업종 수 | 중분류 수 | 규모 구간 수 | 값 결측 | 중복 업종 키 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in stats:
        lines.append(f"| `{item['file']}` | {item['source_rows']} | {item['output_rows']} | {item['industry_groups']} | {item['industry_categories']} | {item['size_bands']} | {item['null_values']} | {item['duplicate_industry_keys']} |")
    lines += ["", "### 장기 사고사망자 추이 데이터", "",
              f"- 원본 행: {historical['source_rows']}; 결과 행: {historical['output_rows']}.",
              f"- 연도 범위: {historical['year_min']}–{historical['year_max']}; 규모 구간: {historical['size_bands']}.",
              f"- 값 결측: {historical['null_values']}; 규모×연도 중복키: {historical['duplicate_size_year_keys']}.",
              "- 이 자료에는 산업중분류가 없으므로 장기 추세용 보조 자료로 분리했습니다.",
              "", "## RAG 보조자료", "",
              f"### 공개자료 경로 목록: 원본 {ai['source_rows']}행 → 결과 {ai['output_rows']}행",
              "", "각 행은 문서 유형·URL·공개 범위·설명으로 정리했습니다. 이 CSV 자체는 보고서 본문이 아니므로 임베딩 코퍼스에 넣지 않습니다.",
              "", "### 용어 사전 ZIP", ""]
    for item in glossary:
        if "member" in item:
            lines.append(f"- `{item['member']}`: {item.get('source_rows', 0)}행, 용어쌍 {item.get('pairs_after_dedup', 0)}건")
        else:
            lines.append(f"- 전체: 중복 제거 후 {item['total_pairs_after_dedup']}쌍, 중복쌍 {item['duplicate_pairs_removed']}건 제거")
    lines += ["", "유의어 쌍은 검색어 확장 실험에만 사용합니다. 원문·정규화 용어를 함께 저장해 변환 내역을 추적할 수 있게 했습니다.",
              "", "## 통합 분석 시 주의점", "",
              "1. 네 업종별 통계는 같은 2025-12-31 기준, 30개 업종 행과 10개 규모 구간 구조입니다.",
              "2. 지표값 비교·비율 계산은 업종과 규모 키를 맞춘 뒤 수행해야 합니다. 원자료의 사망만인율은 계산으로 다시 만들지 않았습니다.",
              "3. 산업중분류별 사고사망자수 파일을 주 지표로 사용하고, 규모별 장기 사망자 자료는 산업 분류가 없는 별도 추세 차트에 사용합니다.",
              "4. 결측 사망만인율은 분모·자료 미제공 여부를 확인하기 전까지 그대로 유지합니다.",
              "5. 산업재해 통계는 Dashboard/SQL용이고, SIF 사고 사례와 용어사전은 각각 사례 RAG와 검색 보조 용도입니다.",
              "", "## 산출 파일", "",
              "- `15084672_industry_size_accident_injured_2025_tidy.csv`",
              "- `15084674_industry_size_fatalities_2025_tidy.csv`",
              "- `15064487_industry_size_workplaces_2025_tidy.csv`",
              "- `15064491_industry_size_fatality_rate_2025_tidy.csv`",
              "- `15084663_accident_fatalities_by_size_2004_2025_tidy.csv`",
              "- `15162988_accident_prevention_source_index_clean.csv`",
              "- `15161288_safety_glossary_pairs.csv`",
              "- `preprocessing_report.json`", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess local occupational-safety datasets with pandas")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"tool": f"pandas {pd.__version__}", "datasets": []}

    stats_reports = []
    for filename, metric in STAT_FILES.items():
        source = args.input_dir / filename
        tidy, report = prepare_industry_metric(source, metric)
        out = args.output_dir / filename.replace(".csv", "_tidy.csv")
        tidy.to_csv(out, index=False, encoding="utf-8-sig")
        report["metric"] = metric
        report["output"] = out.as_posix()
        stats_reports.append(report)

    historical, historical_report = prepare_historical_fatalities(args.input_dir / AGG_FATALITIES_FILE)
    hist_out = args.output_dir / AGG_FATALITIES_FILE.replace(".csv", "_tidy.csv")
    historical.to_csv(hist_out, index=False, encoding="utf-8-sig")
    historical_report["output"] = hist_out.as_posix()

    ai, ai_report = prepare_ai_index(args.input_dir / AI_INDEX_FILE)
    ai_out = args.output_dir / "15162988_accident_prevention_source_index_clean.csv"
    ai.to_csv(ai_out, index=False, encoding="utf-8-sig")
    ai_report["output"] = ai_out.as_posix()

    glossary, glossary_report = prepare_glossaries(args.input_dir / GLOSSARY_ZIP)
    glossary_out = args.output_dir / "15161288_safety_glossary_pairs.csv"
    glossary.to_csv(glossary_out, index=False, encoding="utf-8-sig")
    summary["datasets"] = stats_reports
    summary["historical_fatalities"] = historical_report
    summary["ai_source_index"] = ai_report
    summary["glossary"] = glossary_report
    summary["outputs"] = [p.name for p in sorted(args.output_dir.glob("*.csv"))]
    report_json = args.output_dir / "preprocessing_report.json"
    report_json.write_text(pd.Series(summary).to_json(force_ascii=False, indent=2), encoding="utf-8")
    report_md = args.output_dir / "preprocessing_report.md"
    write_report(report_md, stats_reports, historical_report, ai_report, glossary_report)
    print(f"완료: 통계 5종, 공개자료 경로목록 1종, 용어사전 1종")
    print(f"보고서: {report_md}")
    print(f"요약 JSON: {report_json}")
    for item in stats_reports:
        print(f"{item['metric']}: {item['source_rows']} -> {item['output_rows']}; null={item['null_values']}; duplicate_keys={item['duplicate_industry_keys']}")
    print(f"historical fatalities: {historical_report['source_rows']} -> {historical_report['output_rows']}; years={historical_report['year_min']}-{historical_report['year_max']}")
    print(f"AI index: {ai_report['source_rows']} -> {ai_report['output_rows']}")
    print(f"glossary pairs: {len(glossary)}")


if __name__ == "__main__":
    main()
