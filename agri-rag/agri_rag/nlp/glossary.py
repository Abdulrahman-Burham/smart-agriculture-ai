"""Egyptian agricultural dialect glossary.

Farmers in different governorates use different words for the same crop, pest or practice
(e.g. "قوطة" vs "طماطم"). The glossary maps dialect variants to the canonical term used in the
knowledge base so both lexical and semantic retrieval see the canonical wording.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .arabic import tokenize


@dataclass(frozen=True)
class GlossaryEntry:
    canonical: str
    variants: tuple[str, ...]
    category: str = "general"


@dataclass
class Expansion:
    expanded: str
    matches: list[tuple[str, str]] = field(default_factory=list)  # (matched variant, canonical)


class Glossary:
    def __init__(self, entries: list[GlossaryEntry]):
        self.entries = entries
        self._index: list[tuple[tuple[str, ...], GlossaryEntry, str]] = []
        for entry in entries:
            for variant in (entry.canonical, *entry.variants):
                key = tuple(tokenize(variant, drop_stopwords=False))
                if key:
                    self._index.append((key, entry, variant))
        # longest phrases first so "الندوة المتأخرة" wins over "الندوة"
        self._index.sort(key=lambda item: -len(item[0]))

    @classmethod
    def load(cls, path: Path) -> "Glossary":
        if not Path(path).exists():
            return cls([])
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            [GlossaryEntry(e["canonical"], tuple(e.get("variants", [])), e.get("category", "general"))
             for e in raw["entries"]]
        )

    _WINDOW_SLACK = 2  # dialect speech inserts filler words: "الورق بتاع القوطة بيصفر"

    @classmethod
    def _contains(cls, tokens: list[str], key: tuple[str, ...]) -> bool:
        """True if all tokens of `key` occur close together (order-free, within a small window)."""
        n = len(key)
        if n == 1:
            return key[0] in tokens
        size = n + cls._WINDOW_SLACK
        needed = set(key)
        return any(needed <= set(tokens[i:i + size]) for i in range(max(1, len(tokens) - size + 1)))

    def expand(self, query: str) -> Expansion:
        tokens = tokenize(query, drop_stopwords=False)
        matches: list[tuple[str, str]] = []
        seen: set[str] = set()
        for key, entry, variant in self._index:
            if entry.canonical in seen:
                continue
            if self._contains(tokens, key):
                seen.add(entry.canonical)
                if tuple(tokenize(entry.canonical, drop_stopwords=False)) != key:
                    matches.append((variant, entry.canonical))
        extra = " ".join(canonical for _, canonical in matches)
        return Expansion(f"{query} {extra}".strip() if extra else query, matches)

    def canonicalize(self, term: str | None, category: str | None = None) -> str | None:
        """Map a user-supplied term (e.g. a crop name) to its canonical form."""
        if not term:
            return term
        key = tuple(tokenize(term, drop_stopwords=False))
        for k, entry, _ in self._index:
            if k == key and (category is None or entry.category == category):
                return entry.canonical
        return term.strip()
