"""Load the rule registry from `rules.toml`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib

from yaozarrs._rules._model import Example, Rule, SpecDoc, SpecSource

REGISTRY_FILE = Path(__file__).parent / "rules.toml"


def _load_rule(code: str, entry: dict[str, Any], docs: dict[str, SpecDoc]) -> Rule:
    order = list(docs)
    sources = tuple(
        sorted(
            (
                SpecSource(
                    doc=docs[version],
                    lines=(start, end),
                    quote=src["quote"],
                    implied=src.get("implied", False),
                )
                for src in entry.pop("sources", ())
                for version, (start, end) in src["lines"].items()
            ),
            key=lambda s: order.index(s.doc.version),
        )
    )
    example = Example(**entry.pop("example")) if "example" in entry else None
    for key in ("supersedes", "aliases"):
        if key in entry:
            entry[key] = tuple(entry[key])
    return Rule(code=code, sources=sources, example=example, **entry)


def _load() -> tuple[dict[str, SpecDoc], dict[str, Rule]]:
    data = tomllib.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    docs = {v: SpecDoc(version=v, **d) for v, d in data["spec"].items()}
    rules = {code: _load_rule(code, e, docs) for code, e in data["rules"].items()}
    return docs, rules


SPEC_DOCS, RULES = _load()
TRACKED_VERSIONS = tuple(SPEC_DOCS)
