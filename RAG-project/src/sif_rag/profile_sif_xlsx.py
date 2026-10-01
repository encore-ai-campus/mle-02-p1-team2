"""Read-only pandas profile of the SIF workbook; does not export case text."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd


SHEETS = {
    "아카이브(제조업등)": {
        "data_start_zero_based": 3,
        "columns": {
            1: "연번", 2: "산재업종(대분류)", 3: "산재업종(중분류)", 4: "산재업종(소분류)",
            5: "재해개요", 6: "기인물", 7: "고위험작업·상황", 8: "재해유발요인",
            9: "위험성 감소대책(예시)",
        },
    },
    "아카이브(건설업)": {
        "data_start_zero_based": 4,
        "columns": {
            1: "연번", 2: "공종", 3: "작업명", 4: "단위작업명", 5: "재해종류",
            6: "재해개요", 7: "기인물", 8: "재해유발요인", 9: "위험성 감소대책(예시)",
        },
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile SIF workbook without exporting case content")
    parser.add_argument("workbook", type=Path, help="Path to the original SIF XLSX")
    parser.add_argument("--output", type=Path, default=Path("data/processed/sif_source_profile.md"))
    args = parser.parse_args()

    workbook = pd.ExcelFile(args.workbook, engine="openpyxl")
    summaries: list[dict[str, object]] = []
    for sheet, spec in SHEETS.items():
        raw = pd.read_excel(args.workbook, sheet_name=sheet, header=None, dtype="string", engine="openpyxl")
        start = int(spec["data_start_zero_based"])
        data = raw.iloc[start:].copy()
        serial = data.iloc[:, 1].astype("string").str.strip()
        valid = serial.notna() & serial.ne("")
        cases = data.loc[valid]
        serial_numeric = pd.to_numeric(serial.loc[valid], errors="coerce")
        field_lines = []
        for index, field in spec["columns"].items():
            values = cases.iloc[:, index].astype("string").str.strip()
            missing = int((values.isna() | values.eq("")).sum())
            field_lines.append((field, missing, int(values.nunique(dropna=True))))
        summaries.append({
            "sheet": sheet,
            "raw_rows": len(raw),
            "data_rows_after_header": len(data),
            "valid_serial_rows": len(cases),
            "rows_without_serial": int((~valid).sum()),
            "serial_min": int(serial_numeric.min()) if serial_numeric.notna().any() else None,
            "serial_max": int(serial_numeric.max()) if serial_numeric.notna().any() else None,
            "unique_serials": int(serial_numeric.nunique()),
            "duplicate_serials": int(serial_numeric.duplicated().sum()),
            "duplicate_full_rows": int(cases.iloc[:, 1:10].duplicated().sum()),
            "first_excel_row": int(cases.index[0]) + 1 if len(cases) else None,
            "last_excel_row": int(cases.index[-1]) + 1 if len(cases) else None,
            "fields": field_lines,
        })

    output = [
        "# SIF 원본 XLSX 구조 점검",
        "",
        f"- 점검일: {date.today().isoformat()}",
        f"- 원본 파일: `{args.workbook.name}`",
        "- 방식: pandas로 읽기 전용 점검; 사고 서술 본문은 이 보고서에 복사하지 않음",
        "- 목적: RAG 적재 전 시트 구조·행 식별자·결측·중복 검토",
        "",
        "## 시트별 결과",
        "",
    ]
    for item in summaries:
        output += [
            f"### {item['sheet']}",
            "",
            f"- XLSX 전체 행: {item['raw_rows']}; 헤더 다음 데이터 후보 행: {item['data_rows_after_header']}",
            f"- 연번이 있는 사례: {item['valid_serial_rows']}; 연번 누락 행: {item['rows_without_serial']}",
            f"- 연번 범위/고유값: {item['serial_min']}–{item['serial_max']} / {item['unique_serials']}; 중복 연번: {item['duplicate_serials']}",
            f"- 전체 사례 행 중복: {item['duplicate_full_rows']}; 사례 시작/끝 Excel 행: {item['first_excel_row']}–{item['last_excel_row']}",
            "",
            "| 필드 | 결측 사례 수 | 고유값 수 |",
            "|---|---:|---:|",
        ]
        for field, missing, unique in item["fields"]:
            output.append(f"| {field} | {missing} | {unique} |")
        output.append("")
    output += [
        "## RAG 설계에 미치는 점",
        "",
        "- 제조업 등 시트는 업종 대·중·소분류와 사례 본문 필드를 가진다.",
        "- 건설업 시트는 헤더가 두 행이며, 공종·작업명·단위작업명을 별도 metadata로 읽어야 한다.",
        "- 두 시트 모두 원본 연번이 고유하므로 시트 접두사를 붙인 사례 ID와 물리 Excel 행을 함께 추적할 수 있다.",
        "- 제조업 등과 건설업은 컬럼 체계가 달라 원본 스키마와 공통 검색 스키마를 분리해야 한다.",
        "- 이 스크립트는 원문 사례를 정제 파일이나 임베딩으로 내보내지 않는다.",
        "",
        "## 다음 단계 전제",
        "",
        "SIF 포털 페이지에는 출처표시·변경금지 및 2차적 저작물 작성 금지 조건이 표시되어 있다. 검색 인덱스 생성·임베딩 및 외부 배포 범위는 제공기관 이용조건 확인 후 결정한다.",
        "",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(output), encoding="utf-8")
    print(f"시트 점검 완료: {len(workbook.sheet_names)} sheets; 사례 시트 {len(summaries)}개")
    for item in summaries:
        print(f"{item['sheet']}: rows={item['valid_serial_rows']}, missing_serial={item['rows_without_serial']}, duplicate_serial={item['duplicate_serials']}, duplicate_rows={item['duplicate_full_rows']}")
    print(f"profile={args.output}")


if __name__ == "__main__":
    main()
