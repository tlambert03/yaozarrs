"""Integrity checks for the rule-code registry (`yaozarrs._rules`)."""

from __future__ import annotations

import importlib.util
import re
import warnings
from pathlib import Path

import pytest
from packaging.version import Version
from pydantic import ValidationError

from yaozarrs import v05
from yaozarrs._rules import RULES, Rule, SpecSource, get_rule
from yaozarrs._rules._registry import TRACKED_VERSIONS

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "ngff_rules", ROOT / "scripts" / "ngff_rules.py"
)
assert _spec and _spec.loader
ngff_rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ngff_rules)

CODE_RE = re.compile(r"^(NGFF-[A-Z]{2}-\d{3}|YZ-\d{3})$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Where yaozarrs behavior knowingly differs from "checked in every version whose
# spec states the rule". Both sets are verified, so stale entries fail the test.
# Spec states the rule, but yaozarrs doesn't check it (yet).
KNOWN_GAPS = {
    ("NGFF-DS-001", "0.4"),
    ("NGFF-PL-001", "0.4"),
    ("NGFF-PL-002", "0.4"),
    ("NGFF-PL-003", "0.4"),
    ("NGFF-PL-006", "0.4"),
    ("NGFF-WL-002", "0.4"),
}
# yaozarrs checks the rule in a version whose spec doesn't state it.
KNOWN_OVERREACH = {
    ("NGFF-OM-001", "0.4"),  # shared omero model; 0.4 has no hex-color statement
}


# ---------------------------------------------------------------------------
# registry integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule", RULES.values(), ids=list(RULES))
def test_rule_fields(rule: Rule) -> None:
    assert CODE_RE.match(rule.code)
    assert SLUG_RE.match(rule.slug)
    if rule.status == "withdrawn":
        assert rule.removed, "withdrawn rules must set `removed`"
    for code in rule.supersedes:
        assert code in RULES and code != rule.code

    if rule.code.startswith("YZ-"):
        assert rule.level is None and rule.introduced is None and not rule.sources
        assert rule.severity is not None
        return

    assert rule.level and rule.introduced
    assert rule.sources or not rule.checkable
    versions = [Version(s.doc.version) for s in rule.sources]
    assert Version(rule.introduced) <= versions[0]
    if rule.removed:
        assert Version(rule.introduced) < Version(rule.removed)
        assert all(v < Version(rule.removed) for v in versions)
    for src in rule.sources:
        assert src.doc.version in TRACKED_VERSIONS
        assert re.search(rf"\b{rule.level}\b", src.quote), (
            f"quote for {rule.code} does not contain {rule.level!r}"
        )


def test_unique_slugs() -> None:
    slugs = [r.slug for r in RULES.values()]
    assert len(slugs) == len(set(slugs))


def test_tracked_versions_ordered() -> None:
    versions = [Version(v) for v in TRACKED_VERSIONS]
    assert versions == sorted(versions)


@pytest.mark.parametrize(
    "src",
    [
        pytest.param(src, id=f"{r.code}-{src.doc.version}")
        for r in RULES.values()
        for src in r.sources
    ],
)
def test_quote_at_lines(src: SpecSource) -> None:
    assert ngff_rules.check_quote(src.doc, src.quote, src.lines) is None


def test_codes_in_source_exist() -> None:
    """Every code used in `src/` is registered and has an example."""
    pattern = re.compile(r"\"((?:NGFF-[A-Z]{2}-|YZ-)\d{3})\"")
    used: set[str] = set()
    for path in (ROOT / "src" / "yaozarrs").rglob("*.py"):
        used.update(pattern.findall(path.read_text(encoding="utf-8")))
    assert used - set(RULES) == set()
    assert {c for c in used if RULES[c].example is None} == set()


# ---------------------------------------------------------------------------
# coverage: each example fires exactly where it should
# ---------------------------------------------------------------------------


def _expected(rule: Rule, version: str) -> bool:
    if (rule.code, version) in KNOWN_OVERREACH:
        return True
    if (rule.code, version) in KNOWN_GAPS:
        return False
    if rule.code.startswith("YZ-"):
        return True
    return version in {s.doc.version for s in rule.sources}


@pytest.mark.parametrize(
    "rule, version",
    [
        pytest.param(r, v, id=f"{r.code}-{v}")
        for r in RULES.values()
        if r.example
        for v in ngff_rules.MODULES
    ],
)
def test_example_coverage(rule: Rule, version: str) -> None:
    emitted = rule.code in ngff_rules.emitted_codes(rule, version)
    assert emitted == _expected(rule, version)


def test_known_exceptions_have_examples() -> None:
    for code, version in KNOWN_GAPS | KNOWN_OVERREACH:
        assert RULES[code].example and version in ngff_rules.MODULES


# ---------------------------------------------------------------------------
# messages and docs
# ---------------------------------------------------------------------------


def test_rule_warning_filterable() -> None:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warnings.filterwarnings("ignore", message=r"\[NGFF-AX-006\]")
        v05.SpaceAxis(name="x", unit="lightyear")
    assert not w


def test_rule_error_message() -> None:
    rule = get_rule("NGFF-AX-001")
    assert rule.example
    with pytest.raises(ValidationError) as e:
        v05.Multiscale.model_validate(rule.example.data)
    err = next(x for x in e.value.errors() if x["type"] == rule.code)
    assert rule.url in err["msg"]


def test_docs_render() -> None:
    docs = ngff_rules.expected_docs()
    assert set(docs) == {"index.md"} | {f"{c}.md" for c in RULES}
