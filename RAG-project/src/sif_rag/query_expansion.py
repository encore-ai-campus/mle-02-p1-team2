"""Offline query expansion backed by the cleaned occupational-safety glossary."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd


DEFAULT_GLOSSARY = Path("data/processed/15161288_safety_glossary_pairs.csv")


def normalize_term(value: object) -> str:
    """Normalize Unicode and whitespace without changing the source file."""
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).casefold()).strip()


class GlossaryExpander:
    """Expand exact glossary terms while retaining the user's original query."""

    def __init__(self, aliases: dict[str, set[str]], max_expansions: int = 8):
        if max_expansions < 0:
            raise ValueError("max_expansions는 0 이상이어야 합니다.")
        self.aliases = aliases
        self.max_expansions = max_expansions
        self._patterns: dict[str, re.Pattern[str]] = {}

    @classmethod
    def from_csv(
        cls,
        path: Path = DEFAULT_GLOSSARY,
        *,
        min_term_length: int = 2,
        max_expansions: int = 8,
    ) -> "GlossaryExpander":
        frame = pd.read_csv(path, encoding="utf-8-sig")
        required = {"canonical_term", "variant"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"용어사전 필수 컬럼이 없습니다: {sorted(missing)}")

        groups: dict[str, set[str]] = defaultdict(set)
        for canonical, variant in frame[["canonical_term", "variant"]].itertuples(index=False, name=None):
            canonical_term, variant_term = normalize_term(canonical), normalize_term(variant)
            if len(canonical_term) < min_term_length or len(variant_term) < min_term_length:
                continue
            groups[canonical_term].update((canonical_term, variant_term))

        aliases: dict[str, set[str]] = defaultdict(set)
        for terms in groups.values():
            for term in terms:
                aliases[term].update(terms - {term})
        return cls(dict(aliases), max_expansions=max_expansions)

    def _pattern_for(self, first_character: str) -> re.Pattern[str] | None:
        if first_character not in self._patterns:
            terms = sorted(
                (term for term in self.aliases if term.startswith(first_character)),
                key=lambda term: (-len(term), term),
            )
            if not terms:
                return None
            alternatives = [r"\s+".join(re.escape(part) for part in term.split()) for term in terms]
            self._patterns[first_character] = re.compile(
                r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)", re.IGNORECASE
            )
        return self._patterns[first_character]

    def expand(self, query: str) -> dict[str, object]:
        original = str(query).strip()
        normalized = normalize_term(original)
        if self.max_expansions == 0:
            return {
                "query": original,
                "expanded_query": original,
                "matched_terms": [],
                "added_terms": [],
            }
        matches: list[str] = []
        expansions: list[str] = []
        seen_matches: set[str] = set()
        seen_expansions: set[str] = set()

        for first_character in dict.fromkeys(normalized):
            pattern = self._pattern_for(first_character)
            if pattern is None:
                continue
            for match in pattern.finditer(normalized):
                term = match.group(0)
                if term in seen_matches:
                    continue
                seen_matches.add(term)
                matches.append(term)
                for candidate in sorted(self.aliases[term], key=lambda item: (len(item), item)):
                    if candidate in normalized or candidate in seen_expansions:
                        continue
                    seen_expansions.add(candidate)
                    expansions.append(candidate)
                    if len(expansions) >= self.max_expansions:
                        break
                if len(expansions) >= self.max_expansions:
                    break
            if len(expansions) >= self.max_expansions:
                break

        expanded_query = f"{original} {' '.join(expansions)}".strip() if expansions else original
        return {
            "query": original,
            "expanded_query": expanded_query,
            "matched_terms": matches,
            "added_terms": expansions,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="산업안전 용어사전 기반 오프라인 질의 확장")
    parser.add_argument("query", help="검색 질문")
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--max-expansions", type=int, default=8)
    parser.add_argument("--min-term-length", type=int, default=2)
    args = parser.parse_args()

    expander = GlossaryExpander.from_csv(
        args.glossary,
        min_term_length=args.min_term_length,
        max_expansions=args.max_expansions,
    )
    print(json.dumps(expander.expand(args.query), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
