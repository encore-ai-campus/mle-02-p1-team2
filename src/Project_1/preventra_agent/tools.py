"""Structured retrieval/statistics adapters; no final answers or chat DB writes."""
from collections import defaultdict
import json
from typing import Literal

import numpy as np
import pandas as pd
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from preventra_agent.models import Evidence, ToolResult
from services.query_analysis import analyze_query
from services.statistics import (
    METRIC_FILES, SIZE_ORDER, SOURCE_2025, YEARS, filter_statistics,
    industry_totals, industry_trend, kpi_value, load_statistics,
)
from services.visualization import plot_industry_bar, plot_six_year_line

Metric = Literal["사고재해자수", "사고사망자수", "사망만인율"]


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=2000, description="현재 질문의 작업·장비·요청을 포함하는 독립 검색문. 후속 질문은 대화의 명시적 작업을 반영하되 장비를 추측하지 않는다.")


class StatisticsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: Metric = Field(description="사고재해자수, 사고사망자수 또는 사망만인율")
    industry: str | None = Field(description="정확한 산업중분류 이름. 건설업 등. 전체는 null. 모호한 '우리 업종'은 먼저 사용자에게 확인.")
    size: str | None = Field(description="사업장 규모. " + ", ".join(SIZE_ORDER) + ". 전체는 null. 사망만인율은 반드시 단일 규모.")
    year: int | None = Field(description="조회 연도. null이면 확보된 해당 지표의 최신 연도. 미확보 연도를 최신 연도로 대체하지 않는다.")


class TrendInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: Metric = Field(description="추세 지표: 사고재해자수, 사고사망자수, 사망만인율")
    industry: str | None = Field(description="정확한 산업중분류. 전체 건수 추세는 null. 사망만인율에는 단일 산업 필수.")
    size: str | None = Field(description="사업장 규모. " + ", ".join(SIZE_ORDER) + ". 전체는 null. 사망만인율에는 단일 규모 필수.")
    start_year: int | None = Field(description="조회 시작 연도. null이면 수록 시작연도(2020).")
    end_year: int | None = Field(description="조회 종료 연도. null이면 수록 마지막연도(2025).")


def default_rag():
    from services.safety_rag import get_service
    return get_service()


class SafetyTools:
    def __init__(self, rag_factory=default_rag, statistics_loader=load_statistics):
        self.rag_factory = rag_factory
        self.statistics_loader = statistics_loader
        self._data = None
        self._references = defaultdict(int)

    def reference(self, prefix):
        self._references[prefix] += 1
        return f"{prefix}-{self._references[prefix]}"

    def search(self, query, kind):
        from services.safety_rag import VECTOR_DIM, to_evidence
        service = self.rag_factory()
        context = analyze_query(query)
        search_query = context.sif_query if kind == "sif" else context.kosha_query
        vector = np.asarray(service.embeddings.embed_query(search_query), dtype=np.float32)
        if len(vector) != VECTOR_DIM:
            raise ValueError("Embedding dimension mismatch")
        # Reuse ranking/filtering/OCR corrections; do not call ask/save_turn.
        documents = (service.retrieve_sif(vector, context) if kind == "sif"
                     else service.retrieve_kosha(vector, context))
        tool_name = "search_sif_cases" if kind == "sif" else "search_kosha_guides"
        results = []
        for document in documents:
            source = to_evidence(document, kind)
            metadata = {
                "source": source.source_file or "KOSHA GUIDE",
                "doc_id": source.source_id if kind == "sif" else None,
                "guide_id": source.source_id if kind != "sif" else None,
                "title": source.title, "section": source.section, "page": source.page,
                "source_url": source.source_url, "sheet": source.sheet, "row_number": source.row_number,
            }
            text = document.page_content
            if kind == "sif":
                text = text.split("위험성 감소대책(예시):", 1)[0]
            results.append(Evidence(self.reference("SIF" if kind == "sif" else "GUIDE"),
                                    "sif" if kind == "sif" else "guide", source.title,
                                    text[:5000].strip(), metadata))
        return ToolResult(tool_name, "ok" if results else "empty", results,
                          notice="검색 후보입니다. 직접 관련된 근거만 최종 답변에 채택하세요. OCR 문장은 조건과 적용 범위를 유지하세요." if results else "직접 관련된 검색 근거를 찾지 못했습니다.")

    def data(self):
        if self._data is None:
            self._data = self.statistics_loader()
        return self._data

    def validate_scope(self, name, metric, industry, size):
        data = self.data()
        if data.empty:
            return ToolResult(name, "empty", notice="확보된 통계 데이터가 없습니다.")
        industries = sorted(data["산업중분류"].unique().tolist())
        if industry is not None and industry not in industries:
            return ToolResult(name, "needs_clarification", data={"available_industries": industries},
                              notice="일치하는 산업중분류가 없습니다. 목록에서 해당 업종을 확인하세요. 임의의 업종으로 대체하지 마세요.")
        if size is not None and size not in SIZE_ORDER:
            return ToolResult(name, "needs_clarification", data={"available_sizes": list(SIZE_ORDER)}, notice="사업장 규모를 확인해 주세요.")
        if metric == "사망만인율" and (industry is None or size is None):
            return ToolResult(name, "needs_clarification", data={"available_sizes": list(SIZE_ORDER)},
                              notice="사망만인율은 분모 없이 합산·평균하지 않습니다. 단일 산업중분류와 사업장 규모를 지정해 주세요.")
        return None

    def source(self, metric, years, industry, size):
        return {
            "source": "한국산업안전보건공단 산업중분류별 규모별 통계 CSV",
            "files": [SOURCE_2025[metric] if year == 2025 else f"history/{METRIC_FILES[metric]}_{year}.csv" for year in years],
            "years": years, "industry": industry or "확보된 산업중분류 전체",
            "size": size or "확보된 규모 전체", "metric": metric,
            "aggregation": "단일 산업·규모 원자료율" if metric == "사망만인율" else "확보된 셀의 건수 합계; 누락값 제외",
            "unit": "만인율" if metric == "사망만인율" else "명",
        }

    def snapshot(self, metric, industry, size, year):
        name = "get_accident_statistics"
        issue = self.validate_scope(name, metric, industry, size)
        if issue:
            return issue
        data = self.data()
        present = filter_statistics(data, metric=metric).dropna(subset=["값"])
        if present.empty:
            return ToolResult(name, "empty", notice="해당 지표 자료가 없습니다.")
        year = int(present["연도"].max()) if year is None else year
        rows = filter_statistics(data, metric=metric, industry=industry, size=size, year=year)
        value = kpi_value(data, year, industry, size, metric)
        if value is None:
            return ToolResult(name, "empty", data={"year": year}, notice="요청한 연도·조건의 원자료가 없습니다. 0명이나 0%를 뜻하지 않습니다.")
        source = self.source(metric, [year], industry, size)
        evidence = Evidence(self.reference("STATS"), "statistics", f"{year}년 {industry or '확보범위 전체'} {metric}", "", source)
        payload = {"year": year, "value": value, "valid_cells": int(rows["값"].notna().sum()), "total_cells": len(rows)}
        figures = []
        if metric != "사망만인율":
            totals = industry_totals(data, year, metric, size)
            if industry:
                totals = totals.loc[totals["산업중분류"] == industry]
            payload["industries"] = totals.rename(columns={"값": "value"}).to_dict("records")
            figures = [plot_industry_bar(totals, metric, industry)]
        return ToolResult(name, evidence=[evidence], data=payload, figures=figures,
                          notice="전국 전체 통계와의 일치 여부는 별도 확인이 필요합니다. 그래프는 확보된 산업중분류 범위입니다.")

    def trend(self, metric, industry, size, start_year, end_year):
        name = "get_accident_trend"
        issue = self.validate_scope(name, metric, industry, size)
        if issue:
            return issue
        start = YEARS[0] if start_year is None else start_year
        end = YEARS[-1] if end_year is None else end_year
        if start > end or end - start > 30:
            return ToolResult(name, "needs_clarification", notice="시작·종료 연도를 확인해 주세요. 한 번에 최대 31년 범위만 조회합니다.")
        data = self.data()
        if industry:
            table = industry_trend(data, industry, metric, size)
        else:
            table = pd.DataFrame({"연도": YEARS, "값": [kpi_value(data, year, None, size, metric) for year in YEARS]})
        table = table.set_index("연도").reindex(range(start, end + 1)).rename_axis("연도").reset_index()
        if not table["값"].notna().any():
            return ToolResult(name, "empty", notice="요청한 기간·조건의 추세 자료가 없습니다.")
        records = [{"year": int(row.연도), "value": None if pd.isna(row.값) else float(row.값)} for row in table.itertuples()]
        available = [row["year"] for row in records if row["value"] is not None]
        missing = [row["year"] for row in records if row["value"] is None]
        source = self.source(metric, available, industry, size)
        source["requested_years"] = [start, end]
        evidence = Evidence(self.reference("STATS"), "statistics", f"{industry or '확보범위 전체'} · {metric} 추세", "", source)
        payload = {"records": records, "missing_years": missing}
        observed = [r for r in records if r["value"] is not None]
        if len(observed) >= 2:
            first, last = observed[0], observed[-1]
            payload["change"] = {"from_year": first["year"], "to_year": last["year"], "difference": last["value"] - first["value"],
                                 "percent": round((last["value"] / first["value"] - 1) * 100, 2) if first["value"] else None}
        fig = plot_six_year_line(table, industry or "확보범위 전체", metric, available[-1], size)
        fig.update_layout(title=f"{industry or '확보범위 전체'} · {metric} ({start}–{end})")
        fig.update_xaxes(tickvals=list(range(start, end + 1)))
        return ToolResult(name, evidence=[evidence], data=payload, figures=[fig],
                          notice="누락 연도는 null이며 0으로 대체하거나 선을 연결하지 않습니다. 집계 범위는 출처 조건을 따릅니다.")

    def build(self):
        definitions = [
            ("search_sif_cases", "실제 유사 산업재해 사고사례·사고 경위·원인을 조회합니다. 점검·작업방법만 묻는 질문에는 사용하지 않습니다. 관련 후보와 원본 식별자만 반환합니다.", SearchInput, lambda **kw: self.search(kind="sif", **kw)),
            ("search_kosha_guides", "작업 전 점검, 작업방법, 안전조치, 예방기준을 KOSHA GUIDE 원문에서 조회합니다. 실제 사고사례 요청만 있으면 사용하지 않습니다. 문서·절·페이지와 발췌를 반환합니다.", SearchInput, lambda **kw: self.search(kind="guide", **kw)),
            ("get_accident_statistics", "단일 연도의 산업별 사고재해자수·사고사망자수·사망만인율과 산업 비교를 조회합니다. 비율은 단일 산업·규모 필수입니다. 모르는 업종을 추측하지 않습니다.", StatisticsInput, self.snapshot),
            ("get_accident_trend", "여러 연도·최근 변화·증감·추세 질문에 사용합니다. 2020–2025 자료와 출처를 반환합니다. 2021 사망만인율은 결측입니다. 단일 연도 질문에는 get_accident_statistics를 사용합니다.", TrendInput, self.trend),
        ]
        tools = []
        for name, description, schema, function in definitions:
            def invoke(_function=function, _name=name, **kwargs):
                try:
                    result = _function(**kwargs)
                except Exception:
                    result = ToolResult(_name, "error", notice="자료 조회를 완료하지 못했습니다. 연결 또는 데이터 준비 상태를 확인해야 합니다. 수치나 근거를 추측하지 마세요.")
                return json.dumps(result.model_payload(), ensure_ascii=False, allow_nan=False), result
            tools.append(StructuredTool.from_function(invoke, name=name, description=description,
                         args_schema=schema, response_format="content_and_artifact"))
        return tools
