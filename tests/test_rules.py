"""Integrity checks for the rule-code registry (`yaozarrs._rules`)."""

from __future__ import annotations

import importlib.util
import re
import warnings
from pathlib import Path

import pytest
from packaging.version import Version
from pydantic import TypeAdapter, ValidationError

from yaozarrs import v05, v06
from yaozarrs._rules import (
    RULES,
    Rule,
    RuleCodes,
    SpecSource,
    error_code,
    get_rule,
    rewrap_error,
    rule_error,
)
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
    # each dataset's transformation is checked against the axes instead (NGFF-CT-004),
    # and each array's number of dimensions (NGFF-DS-005)
    ("NGFF-DS-002", "0.6"),
}
# yaozarrs checks the rule in a version whose spec doesn't state it.
KNOWN_OVERREACH = {
    # shared omero model; the 0.4 schema only requires `color` to be a string
    ("NGFF-OM-001", "0.4"),
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
        if src.is_schema:
            # schemas have no keywords: base schemas are MUST, strict schemas SHOULD
            strict = src.doc.path.rsplit("/", 1)[-1].startswith("strict_")
            assert rule.level == ("SHOULD" if strict else "MUST")
        elif src.implied:
            assert rule.notes, "explain in `notes` why a keyword-less quote counts"
        else:
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
    assert {c for c in used if not (RULES[c].example or RULES[c].examples)} == set()


# ---------------------------------------------------------------------------
# coverage: each example fires exactly where it should
# ---------------------------------------------------------------------------


def _expected(rule: Rule, version: str) -> bool:
    if (rule.code, version) in KNOWN_OVERREACH:
        return True
    if (rule.code, version) in KNOWN_GAPS:
        return False
    if rule.code.startswith("YZ-"):
        return ngff_rules.example_for(rule, version) is not None
    return version in {s.doc.version for s in rule.sources}


@pytest.mark.parametrize(
    "rule, version",
    [
        pytest.param(r, v, id=f"{r.code}-{v}")
        for r in RULES.values()
        if r.example or r.examples
        for v in ngff_rules.MODULES
    ],
)
def test_example_coverage(rule: Rule, version: str) -> None:
    example = ngff_rules.example_for(rule, version)
    if example and example.store is not None:
        pytest.importorskip("fsspec")
    emitted = rule.code in ngff_rules.emitted_codes(rule, version)
    assert emitted == _expected(rule, version)


def test_known_exceptions_have_examples() -> None:
    for code, version in KNOWN_GAPS | KNOWN_OVERREACH:
        assert version in ngff_rules.MODULES
        assert ngff_rules.example_for(RULES[code], version)


# ---------------------------------------------------------------------------
# messages and docs
# ---------------------------------------------------------------------------


def test_schema_source() -> None:
    src = next(s for s in get_rule("NGFF-CT-045").sources)
    assert src.is_schema
    assert src.doc.path == "schemas/coordinate_transformations.schema"
    assert f"/blob/{src.doc.sha}/schemas/coordinate" in src.permalink
    v4 = next(s for s in get_rule("NGFF-PL-037").sources if s.doc.version == "0.4")
    assert v4.doc.path == "0.4/schemas/plate.schema"
    assert v4.doc.cache_name == "ome-ngff-0.4.1-plate.schema"


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


def test_rewrap_error_keeps_code() -> None:
    # the code survives the context that callers add to a message
    example = ngff_rules.example_for(get_rule("NGFF-CT-004"), "0.6")
    with pytest.raises(ValidationError) as e:
        v06.Multiscale.model_validate(example.data)
    (err,) = e.value.errors()
    assert err["type"] == "NGFF-CT-004"
    assert "datasets[" in err["msg"]
    assert err["msg"].count("See https://") == 1

    original = rule_error("NGFF-CT-004", "bad")
    assert error_code(rewrap_error(original, "a: ", ": b")) == "NGFF-CT-004"
    assert str(rewrap_error(original, "a: ", ": b")).startswith("a: bad: b\n  See ")
    assert error_code(rewrap_error(original, code="NGFF-CT-041")) == "NGFF-CT-041"
    plain = rewrap_error(ValueError("bad"), "a: ")
    assert str(plain) == "a: bad" and error_code(plain) is None


def test_storage_dimension_mismatch_keeps_code() -> None:
    # a dimensionality error found in storage validation keeps its specific code
    pytest.importorskip("fsspec")
    image = get_rule("NGFF-DS-005").example
    assert image
    files = ngff_rules.to_v06_store(image.files)
    files["s0/zarr.json"]["shape"] = [4, 4]
    scene = {
        "version": "0.6",
        "scene": {
            "coordinateSystems": [{"name": "world", "axes": [{"name": "x"}]}],
            "coordinateTransformations": [
                {
                    "type": "scale",
                    "scale": [1, 1],
                    "input": {"name": "physical", "path": "image"},
                    "output": {"name": "world"},
                }
            ],
        },
    }
    root = {"zarr_format": 3, "node_type": "group", "attributes": {"ome": scene}}
    store = {"zarr.json": root, **{f"image/{k}": v for k, v in files.items()}}
    assert "NGFF-CT-004" in ngff_rules._store_codes(store)


def test_field_error_codes_nested_discriminated_union() -> None:
    # discriminated unions stay discriminated in models nested in other models
    example = ngff_rules.example_for(get_rule("NGFF-CT-005"), "0.6")
    multiscale = {
        "coordinateSystems": [
            {
                "name": "physical",
                "axes": [
                    {"name": "y", "type": "space"},
                    {"name": "x", "type": "space"},
                ],
            }
        ],
        "datasets": [example.data],
    }
    with pytest.raises(ValidationError) as e:
        v06.Image.model_validate({"multiscales": [multiscale]})
    (err,) = e.value.errors()
    assert err["type"] == "NGFF-CT-005"
    assert err["ctx"]["pydantic_type"] == "union_tag_invalid"


def test_rule_codes_unknown_code() -> None:
    with pytest.raises(KeyError):
        RuleCodes(missing="NGFF-XX-999")


def test_docs_render() -> None:
    pytest.importorskip("fsspec")  # coverage of store examples
    docs = ngff_rules.expected_docs()
    assert set(docs) == {"index.md"} | {f"{c}.md" for c in RULES}
