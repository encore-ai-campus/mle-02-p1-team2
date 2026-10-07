"""UI adapter for the reusable Single Agent; no conversation persistence."""
from dataclasses import dataclass, field
from typing import Any, Literal

from preventra_agent.models import ConversationTurn


@dataclass(frozen=True)
class AssistantRequest:
    request_id: str
    session_id: str
    question: str
    previous_questions: tuple[str, ...] = ()
    history: tuple[ConversationTurn, ...] = ()
    context: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    title: str
    source_id: str
    excerpt: str
    location: str = ""
    reference: str = ""
    source: dict = field(default_factory=dict)


@dataclass
class AssistantResult:
    status: Literal["not_connected", "ready", "error"] = "ready"
    answer: str = ""
    cases: list[Evidence] = field(default_factory=list)
    guides: list[Evidence] = field(default_factory=list)
    figures: list[Any] = field(default_factory=list)
    statistics_caption: str = ""
    used_tools: list[str] = field(default_factory=list)
    tool_results: list[Any] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    plan_sources: list[Evidence] = field(default_factory=list)


def dispatch(request: AssistantRequest, *, agent=None) -> AssistantResult:
    from preventra_agent.agent import SafetyAgent
    from preventra_agent.tools import SafetyTools
    from preventra_ui.statistics_view import get_statistics

    if agent is None:
        agent = SafetyAgent(backend=SafetyTools(statistics_loader=get_statistics))
    result = agent.run(request.question, request.history, request.request_id, conversation_id=request.session_id)
    cases, guides, figures, captions, plans = [], [], [], [], []
    selected = {item.reference for item in result.evidence}
    for item in result.evidence:
        if item.kind == "statistics":
            src = item.source
            captions.append(f"[{item.reference}] {src['source']} · {src['industry']} · {src['size']} · {', '.join(map(str, src['years']))}년 · {src['aggregation']}")
            continue
        converted = Evidence(item.title, item.source.get("doc_id") or item.source.get("guide_id") or "",
                             item.excerpt, reference=item.reference, source=item.source)
        (cases if item.kind == "sif" else plans if item.kind == "plan" else guides).append(converted)
    for tool_result in result.tool_results:
        if any(item.reference in selected for item in tool_result.evidence):
            figures.extend(tool_result.figures)
    return AssistantResult(status=result.status, answer=result.final_answer, cases=cases, guides=guides,
                           figures=figures, statistics_caption="\n\n".join(captions),
                           used_tools=result.used_tools, tool_results=result.tool_results, trace=result.trace, plan_sources=plans)
