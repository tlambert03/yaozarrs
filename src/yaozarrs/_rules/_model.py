"""Data model for rule codes (see `yaozarrs._rules`)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

Level = Literal["MUST", "MUST NOT", "SHOULD", "SHOULD NOT", "MAY"]
Status = Literal["draft", "stable", "withdrawn"]
Severity = Literal["error", "warning"]

DOCS_URL = "https://imaging-formats.github.io/yaozarrs/rules/{code}/"


@dataclass(frozen=True)
class SpecDoc:
    """One version of the spec source file, pinned to an immutable commit."""

    version: str
    tag: str
    repo: str
    sha: str
    path: str

    @property
    def raw_url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.sha}/{self.path}"

    @property
    def cache_name(self) -> str:
        """File name of the vendored copy in `tests/spec_sources/`."""
        suffix = self.path.rsplit(".", 1)[-1]
        return f"{self.repo.replace('/', '-')}-{self.tag}.{suffix}"


@dataclass(frozen=True)
class SpecSource:
    """A verbatim quote of a normative statement, at specific lines of a `SpecDoc`."""

    doc: SpecDoc
    lines: tuple[int, int]
    quote: str

    @property
    def permalink(self) -> str:
        start, end = self.lines
        anchor = f"L{start}" if start == end else f"L{start}-L{end}"
        return (
            f"https://github.com/{self.doc.repo}/blob/{self.doc.sha}/"
            f"{self.doc.path}#{anchor}"
        )


@dataclass(frozen=True)
class Example:
    """A minimal document that violates a rule, when validated as `model`."""

    model: str  # name of a model class in a version module, e.g. `Multiscale`
    json: str

    @property
    def data(self) -> object:
        return json.loads(self.json)


@dataclass(frozen=True)
class Rule:
    """A single normative statement (or yaozarrs-specific check)."""

    code: str
    slug: str
    summary: str
    level: Level | None = None  # None for `YZ-` rules
    sources: tuple[SpecSource, ...] = ()
    introduced: str | None = None  # None for `YZ-` rules
    removed: str | None = None
    status: Status = "stable"
    severity: Severity | None = None  # defaults to `warning` for SHOULD, else `error`
    checkable: bool = True
    supersedes: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    notes: str = ""
    example: Example | None = None  # None if yaozarrs doesn't check this rule

    @property
    def url(self) -> str:
        return DOCS_URL.format(code=self.code)

    @property
    def default_severity(self) -> Severity:
        if self.severity is not None:
            return self.severity
        return "warning" if self.level in ("SHOULD", "SHOULD NOT") else "error"
