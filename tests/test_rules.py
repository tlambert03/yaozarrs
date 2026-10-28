"""Integrity checks for the rule-code registry (`yaozarrs._rules`)."""

from __future__ import annotations

import importlib.util
import re
import warnings
from pathlib import Path

import pytest
from packaging.version import Version
from pydantic import TypeAdapter, ValidationError

from yaozarrs import v05
from yaozarrs._rules import RULES, Rule, RuleCodes, SpecSource, get_rule
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
    # shared omero model; 0.4 describes omero without RFC 2119 keywords
    ("NGFF-OM-001", "0.4"),
    ("NGFF-OM-002", "0.4"),
    ("NGFF-OM-003", "0.4"),
    ("NGFF-OM-004", "0.4"),
    ("NGFF-OM-005", "0.4"),
    ("NGFF-OM-006", "0.4"),
    # the v0.4 storage validator mirrors v0.5, but 0.4 states these without keywords
    ("NGFF-LB-001", "0.4"),
    ("NGFF-LB-002", "0.4"),
    ("NGFF-LB-003", "0.4"),
    ("NGFF-IL-003", "0.4"),
    ("NGFF-IL-004", "0.4"),
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
    if rule.example and rule.example.store is not None:
        pytest.importorskip("fsspec")
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


def test_field_error_codes() -> None:
    with pytest.raises(ValidationError) as e:
        v05.PlateWell.model_validate({"path": "A1", "rowIndex": -1})
    errs = {x["loc"]: x for x in e.value.errors()}
    assert errs[("path",)]["type"] == "NGFF-PL-032"
    assert errs[("rowIndex",)]["type"] == "NGFF-PL-004"
    assert errs[("columnIndex",)]["type"] == "NGFF-PL-033"
    # the original pydantic error is kept in ctx and in the message
    missing = errs[("columnIndex",)]
    assert missing["ctx"]["pydantic_type"] == "missing"
    assert missing["msg"].startswith("Field required")
    assert get_rule("NGFF-PL-033").url in missing["msg"]


def test_field_error_codes_nested() -> None:
    # codes survive nesting; locations and non-rule errors are unchanged
    plate = {"plate": {"rows": [{"name": "A_"}], "columns": [{"name": "1"}]}}
    with pytest.raises(ValidationError) as e:
        v05.Plate.model_validate(plate)
    errs = {x["loc"]: x["type"] for x in e.value.errors()}
    assert errs == {
        ("plate", "rows", 0, "name"): "NGFF-PL-026",
        ("plate", "wells"): "NGFF-PL-028",
    }
    with pytest.raises(ValidationError) as e:
        v05.Omero.model_validate({"channels": [{"color": "FF0000", "window": 1}]})
    (err,) = e.value.errors()
    assert err["loc"] == ("channels", 0, "window") and err["type"] == "model_type"


def test_field_error_codes_on_assignment() -> None:
    well = v05.PlateWell(path="A/1", rowIndex=0, columnIndex=0)
    with pytest.raises(ValidationError) as e:
        well.rowIndex = -1
    assert e.value.errors()[0]["type"] == "NGFF-PL-004"


def test_field_error_codes_keep_union_labels() -> None:
    # tagging must not change how pydantic names models in union errors
    with pytest.raises(ValidationError) as e:
        adapter = TypeAdapter(v05.ScaleTransformation | v05.TranslationTransformation)
        adapter.validate_python({"type": "scale"})
    assert e.value.title == "union[ScaleTransformation,TranslationTransformation]"
    assert {x["loc"][0] for x in e.value.errors()} == {
        "ScaleTransformation",
        "TranslationTransformation",
    }


def test_rule_codes_unknown_code() -> None:
    with pytest.raises(KeyError):
        RuleCodes(missing="NGFF-XX-999")


def test_docs_render() -> None:
    pytest.importorskip("fsspec")  # coverage of store examples
    docs = ngff_rules.expected_docs()
    assert set(docs) == {"index.md"} | {f"{c}.md" for c in RULES}
