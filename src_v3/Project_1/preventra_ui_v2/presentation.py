"""Display-only formatting; persisted answers and Agent evidence stay intact."""
from dataclasses import replace
import re

from preventra_ui.gateway import AssistantResult

# Match only Preventra citation tokens, including escaped Markdown brackets.
# Other bracketed text (measurements, links, labels) must remain readable.
_CITATIONS = re.compile(
    r"[ \t]*\\?\[(?:SIF|GUIDE|STATS|PLAN)-\d+"
    r"(?:[ \t]*[,;·][ \t]*(?:SIF|GUIDE|STATS|PLAN)-\d+)*\\?\]"
)


def without_reference_tokens(text: str) -> str:
    return _CITATIONS.sub("", text).strip()


def for_display(result: AssistantResult) -> AssistantResult:
    """Return a shallow display copy without modifying history or tool results."""
    return replace(
        result,
        answer=without_reference_tokens(result.answer),
        statistics_caption=without_reference_tokens(result.statistics_caption),
    )
