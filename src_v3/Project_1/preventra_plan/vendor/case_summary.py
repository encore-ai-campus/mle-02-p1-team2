"""Transparent, keyword-only summaries of the local SANUP-P SIF archive."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pandas as pd

from preventra_plan.vendor.work_plan import WorkItem


SIF_SOURCE_URL = "https://www.data.go.kr/data/15140383/fileData.do"
GENERIC_TERMS = {
    "작업", "작업환경", "공사", "설치", "준비", "계속", "자재", "반입",
    "정리", "보수", "점검", "휴대용", "이동식",
}


@dataclass(frozen=True)
class CaseGuide:
    accident_type: str
    count: int
    situation: str
    controls: tuple[str, ...]
    record_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaseSummary:
    keyword: str
    field: str
    total: int
    counts: tuple[tuple[str, int], ...]
    guides: tuple[CaseGuide, ...] = ()
    category_counts: tuple[tuple[str, int], ...] = ()
    record_ids: tuple[str, ...] = ()


def summarize_cases(item: WorkItem, frame: pd.DataFrame) -> CaseSummary | None:
    """Reuse the teammate matching rules on an already-loaded construction catalog."""
    activity_terms = [term for term in re.findall(r"[가-힣A-Za-z]{2,}", item.activity) if term not in GENERIC_TERMS]
    equipment_terms = [term for term in re.findall(r"[가-힣A-Za-z]{2,}", item.equipment) if term not in GENERIC_TERMS]
    work_text = frame["work_name"].astype(str) + " " + frame["unit_work"].astype(str)
    equipment_text = frame["causal_object"].astype(str)
    candidates: list[tuple[int, str, str, pd.Series]] = []
    for term in dict.fromkeys(activity_terms):
        mask = work_text.str.contains(term, regex=False, case=False)
        if mask.sum() >= 5:
            candidates.append((int(mask.sum()), term, "작업명·단위작업", mask))
    if not candidates:
        for term in dict.fromkeys(equipment_terms):
            mask = equipment_text.str.contains(term, regex=False, case=False)
            if mask.sum() >= 5:
                candidates.append((int(mask.sum()), term, "기인물", mask))
    if not candidates:
        return None
    total, keyword, field, mask = min(candidates, key=lambda value: value[0])
    matched = frame.loc[mask].copy()
    matched["accident_type"] = matched["accident_type"].replace("", "미분류")
    counts = matched["accident_type"].value_counts().head(5)
    categories = matched["work_name"].astype(str).replace("", "미분류").value_counts().head(3)
    guides = []
    for accident_type, count in counts.head(3).items():
        cases = matched.loc[matched["accident_type"].eq(accident_type)]
        situations = [
            str(value).strip() for value in cases.get("trigger_factor", pd.Series(dtype=str)).fillna("")
            if str(value).strip()
        ]
        measures = []
        available = cases.get("risk_measures_available", pd.Series(True, index=cases.index))
        usable_measures = cases.loc[available.fillna(False).astype(bool)]
        for value in usable_measures.get("risk_reduction_measures", pd.Series(dtype=str)).fillna(""):
            if not str(value).strip():
                continue
            for line in re.split(r"[\r\n]+|(?=▶)|(?=•)|(?=●)", str(value)):
                cleaned = re.sub(r"^[\s▶•●·\-]+", "", line).strip()
                if re.fullmatch(r"원인\s*미상", cleaned):
                    continue
                if 12 <= len(cleaned) <= 320 and cleaned not in measures:
                    measures.append(cleaned)
        record_ids = tuple(
            str(value) for value in cases.get("record_id", pd.Series(dtype=str)).fillna("")
            if str(value).strip()
        )[:3]
        guides.append(CaseGuide(
            str(accident_type), int(count),
            Counter(situations).most_common(1)[0][0] if situations else "사례의 위험 상황 설명이 등록되지 않았습니다.",
            tuple(measures[:3]), record_ids,
        ))
    return CaseSummary(
        keyword, field, total,
        tuple((str(name), int(value)) for name, value in counts.items()),
        tuple(guides),
        tuple((str(name), int(value)) for name, value in categories.items()),
        tuple(sorted(matched["record_id"].astype(str))),
    )
