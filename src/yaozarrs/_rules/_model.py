"""Data model for rule codes (see `yaozarrs._rules`)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
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
        repo = self.repo.replace("/", "-")
        if self.path.endswith(".schema"):
            return f"{repo}-{self.tag}-{self.path.rsplit('/', 1)[-1]}"
        suffix = self.path.rsplit(".", 1)[-1]
        return f"{repo}-{self.tag}.{suffix}"

    def schema(self, name: str) -> SpecDoc:
        """Return the JSON schema file `name` of this spec version."""
        folder = self.path.rpartition("/")[0]
        path = f"{folder}/schemas/{name}" if folder else f"schemas/{name}"
        return replace(self, path=path)


@dataclass(frozen=True)
class SpecSource:
    """A verbatim quote of a normative statement, at specific lines of a `SpecDoc`."""

    doc: SpecDoc
    lines: tuple[int, int]
    quote: str
    # the statement is a requirement, but this version states it without an
    # RFC 2119 keyword (the rule's `notes` say why it counts)
    implied: bool = False

    @property
    def is_schema(self) -> bool:
        """Whether this quotes one of the spec's JSON schemas, rather than its prose."""
        return self.doc.path.endswith(".schema")

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
    """A minimal input that violates a rule.

    Either a JSON document validated as `model`, or a `store`: a JSON object mapping
    metadata file paths (`zarr.json`, `s0/zarr.json`, ...) to their contents, validated
    with `validate_zarr_store`.  A rule's `example` is in the v0.5 format, and is
    converted for other versions (see `example_for` in `scripts/ngff_rules.py`); its
    `examples` are in the format of the version they are for.
    """

    model: str | None = None  # name of a model class in a version module
    json: str | None = None
    store: str | None = None

    @property
    def data(self) -> object:
        return json.loads(self.json or "null")

    @property
    def files(self) -> dict[str, dict]:
        return json.loads(self.store or "{}")


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
    # replaces `example` for specific versions
    examples: dict[str, Example] = field(default_factory=dict, hash=False)

    @property
    def url(self) -> str:
        return DOCS_URL.format(code=self.code)

    @property
    def default_severity(self) -> Severity:
        if self.severity is not None:
            return self.severity
        return "warning" if self.level in ("SHOULD", "SHOULD NOT") else "error"
