"""Future Single Agent boundary. No network, database, or generated answers yet."""
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class AssistantRequest:
    request_id: str
    session_id: str
    question: str
    previous_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Evidence:
    title: str
    source_id: str
    excerpt: str
    location: str = ""


@dataclass
class AssistantResult:
    status: Literal["not_connected", "ready", "error"] = "not_connected"
    answer: str = ""
    cases: list[Evidence] = field(default_factory=list)
    guides: list[Evidence] = field(default_factory=list)
    figures: list[Any] = field(default_factory=list)
    statistics_caption: str = ""


def dispatch(request: AssistantRequest) -> AssistantResult:
    """Replace this body with the Single Agent adapter in the next phase.

    Preserve request_id for idempotency. Return only evidence actually selected
    for the answer, plus figures with their scope/source in statistics_caption.
    UI state is transient; this function does not save or restore conversations.
    """
    return AssistantResult()
