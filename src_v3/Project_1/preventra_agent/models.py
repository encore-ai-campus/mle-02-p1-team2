"""Typed agent results; documents and chart objects never share the answer text."""
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class ConversationTurn:
    question: str
    final_answer: str


@dataclass(frozen=True)
class Evidence:
    reference: str
    kind: Literal["sif", "guide", "statistics", "plan"]
    title: str
    excerpt: str
    source: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    tool_name: str
    status: str = "ok"
    evidence: list[Evidence] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    notice: str = ""
    figures: list[Any] = field(default_factory=list, repr=False)

    def model_payload(self):
        from dataclasses import asdict
        return {"status": self.status, "evidence": [asdict(e) for e in self.evidence],
                "data": self.data, "notice": self.notice}


class FinalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    final_answer: str = Field(description="한국어 최종 답변. 구체 주장에 [SIF-1], [GUIDE-1], [STATS-1] 등 실제 제공된 reference를 인용한다.")
    evidence_ids: list[str] = Field(description="답변에 실제 채택하고 인용한 reference만. 일반 대화, 조건 확인, 근거 없음이면 빈 목록.")


@dataclass
class AgentResult:
    final_answer: str
    used_tools: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    status: str = "ready"
