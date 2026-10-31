"""Maintenance tool for the rule registry in `src/yaozarrs/_rules/rules.toml`.

Usage (from the repo root):

    uv run python scripts/ngff_rules.py fetch          # vendor pinned spec sources
    uv run python scripts/ngff_rules.py check [--fix]  # verify quotes are at `lines`
    uv run python scripts/ngff_rules.py relocate <repo> <ref> <path>
    uv run python scripts/ngff_rules.py coverage       # where each example fires
    uv run python scripts/ngff_rules.py docs           # generate docs/rules/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.request
import warnings
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from yaozarrs import v04, v05, v06, validate_zarr_store
from yaozarrs._rules import RULES, Rule, RuleWarning, SpecDoc
from yaozarrs._rules._registry import REGISTRY_FILE, SPEC_DOCS, TRACKED_VERSIONS
from yaozarrs._storage import StorageValidationError, StorageValidationWarning

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import ModuleType

    from yaozarrs._rules._model import Example

ROOT = Path(__file__).resolve().parent.parent
SPEC_SOURCES = ROOT / "tests" / "spec_sources"
DOCS_DIR = ROOT / "docs" / "rules"

# yaozarrs model module for each spec version it implements
MODULES: dict[str, ModuleType] = {"0.4": v04, "0.5": v05, "0.6": v06}
# env vars that change which rules fire; coverage is computed without them
BEHAVIOR_ENV_VARS = (
    "YAOZARRS_ALLOW_RISKY_NODE_NAMES",
    "YAOZARRS_IGNORE_RISKY_FOV_NAMES",
    "YAOZARRS_STRICT_FOV_NAMES",
)


# ---------------------------------------------------------------------------
# quote lookup
# ---------------------------------------------------------------------------


def find_quote(text: str, quote: str) -> list[tuple[int, int]]:
    """Return the (start, end) line spans where `quote` occurs, ignoring whitespace."""
    chars: list[str] = []
    line_of: list[int] = []
    prev_space = True
    for lineno, line in enumerate(text.splitlines(), 1):
        for ch in line + "\n":
            if ch.isspace():
                if prev_space:
                    continue
                ch, prev_space = " ", True
            else:
                prev_space = False
            chars.append(ch)
            line_of.append(lineno)
    norm = "".join(chars)
    needle = " ".join(quote.split())
    spans = []
    idx = norm.find(needle)
    while idx != -1:
        spans.append((line_of[idx], line_of[idx + len(needle) - 1]))
        idx = norm.find(needle, idx + 1)
    return spans


def spec_text(doc: SpecDoc) -> str:
    """Return the vendored text of `doc`."""
    path = SPEC_SOURCES / doc.cache_name
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `scripts/ngff_rules.py fetch`")
    return path.read_text(encoding="utf-8")


def check_quote(doc: SpecDoc, quote: str, lines: tuple[int, int]) -> str | None:
    """Return a problem description, or None if `quote` is at `lines` of `doc`."""
    spans = find_quote(spec_text(doc), quote)
    if lines in spans:
        return None
    if not spans:
        return "quote not found"
    return f"quote found at {spans}, not at {lines}"


# ---------------------------------------------------------------------------
# coverage: run each rule's example against every version module
# ---------------------------------------------------------------------------


@contextmanager
def _default_behavior() -> Generator[None]:
    saved = {k: os.environ.pop(k) for k in BEHAVIOR_ENV_VARS if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


# numpy-style dtype strings for zarr v2 `.zarray` files
_V2_DTYPES = {
    "bool": "|b1",
    "int8": "|i1",
    "uint8": "|u1",
    **{f"{k}{n}": f"<{k[0]}{n // 8}" for k in ("int", "uint") for n in (16, 32, 64)},
    "float32": "<f4",
    "float64": "<f8",
}


def to_v04_store(files: dict[str, dict]) -> dict[str, dict]:
    """Convert a v0.5 (zarr v3) store example into the equivalent v0.4 (zarr v2)."""
    out: dict[str, dict] = {}
    for path, meta in files.items():
        prefix = path.removesuffix("zarr.json")
        if meta["node_type"] == "array":
            shape = meta["shape"]
            out[f"{prefix}.zarray"] = {
                "zarr_format": 2,
                "shape": shape,
                "chunks": shape,
                "dtype": _V2_DTYPES[meta["data_type"]],
                "compressor": None,
                "fill_value": 0,
                "order": "C",
                "filters": None,
            }
            continue
        attrs = dict(meta.get("attributes", {}))
        ome = dict(attrs.pop("ome", {}))
        ome.pop("version", None)
        # in v0.4 the version lives on each of these objects instead
        if "multiscales" in ome:
            ome["multiscales"] = [{**ms, "version": "0.4"} for ms in ome["multiscales"]]
        for key in ("plate", "well", "image-label"):
            if key in ome:
                ome[key] = {**ome[key], "version": "0.4"}
        out[f"{prefix}.zgroup"] = {"zarr_format": 2}
        out[f"{prefix}.zattrs"] = {**attrs, **ome}
    return out


def _dataset_to_v06(ds: dict) -> dict:
    """Convert a v0.5 `datasets` entry into the equivalent v0.6."""
    ts = ds.get("coordinateTransformations")
    if not isinstance(ts, list) or not ts:
        return ds
    ref = {"input": {"path": ds.get("path")}, "output": {"name": "physical"}}
    # v0.6 has a single transformation: several become a sequence
    t = ts[0] if len(ts) == 1 else {"type": "sequence", "transformations": ts}
    return {**ds, "coordinateTransformations": [{**t, **ref}]}


def _multiscale_to_v06(ms: dict) -> dict:
    """Convert a v0.5 `multiscales` entry into the equivalent v0.6."""
    out = {}
    if "axes" in ms:
        out["coordinateSystems"] = [{"name": "physical", "axes": ms["axes"]}]
    out.update({k: v for k, v in ms.items() if k != "axes"})
    if isinstance(ms.get("datasets"), list):
        out["datasets"] = [_dataset_to_v06(ds) for ds in ms["datasets"]]
    return out


def to_v06_store(files: dict[str, dict]) -> dict[str, dict]:
    """Convert a v0.5 (zarr v3) store example into the equivalent v0.6."""
    out: dict[str, dict] = {}
    for path, meta in files.items():
        ome = meta.get("attributes", {}).get("ome")
        if ome is None:
            out[path] = meta
            continue
        ome: dict[str, Any] = {**ome, "version": "0.6"}
        if "multiscales" in ome:
            ome["multiscales"] = [_multiscale_to_v06(m) for m in ome["multiscales"]]
        attrs = {**meta["attributes"], "ome": ome}
        out[path] = {**meta, "attributes": attrs}
    return out


def example_for(rule: Rule, version: str) -> Example | None:
    """Return `rule`'s example for `version`, in that version's format."""
    if version in rule.examples:
        return rule.examples[version]
    if (ex := rule.example) is None:
        return None
    if ex.store is not None:
        convert = {"0.4": to_v04_store, "0.6": to_v06_store}.get(version)
        files = convert(ex.files) if convert else ex.files
        return replace(ex, store=json.dumps(files, indent=2))
    if version == "0.6" and ex.model in ("Multiscale", "Dataset"):
        fn = _multiscale_to_v06 if ex.model == "Multiscale" else _dataset_to_v06
        return replace(ex, json=json.dumps(fn(cast("dict", ex.data)), indent=2))
    return ex


def _store_codes(files: dict[str, dict]) -> set[str]:
    """Write `files` to a temporary store, validate it, and return emitted codes."""
    with tempfile.TemporaryDirectory(suffix=".zarr") as tmp:
        for path, content in files.items():
            dest = Path(tmp, path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(content), encoding="utf-8")
        codes: set[str] = set()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                validate_zarr_store(tmp)
            except StorageValidationError as e:
                codes.update(c for d in e.errors() if (c := d.get("code")))
            except ValidationError as e:
                codes.update(err["type"] for err in e.errors())
            except ValueError:
                pass  # e.g. the OME-Zarr version could not be determined
        for x in w:
            if isinstance(x.message, StorageValidationWarning):
                codes.update(c for d in x.message.warnings() if (c := d.get("code")))
            elif isinstance(x.message, RuleWarning):
                codes.add(x.message.code)
        return codes


def emitted_codes(rule: Rule, version: str) -> set[str]:
    """Codes emitted when validating `rule`'s example as spec `version`."""
    if (ex := example_for(rule, version)) is None:
        return set()
    with _default_behavior():
        if ex.store is not None:
            return _store_codes(ex.files)
        if (model := getattr(MODULES[version], ex.model or "", None)) is None:
            return set()
        codes: set[str] = set()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                model.model_validate_json(ex.json or "null")
            except ValidationError as e:
                codes.update(err["type"] for err in e.errors())
    codes.update(x.message.code for x in w if isinstance(x.message, RuleWarning))
    return codes


def coverage(rule: Rule) -> list[str]:
    """Spec versions in which yaozarrs emits `rule.code` for its example."""
    return [v for v in MODULES if rule.code in emitted_codes(rule, v)]


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def _download(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def cmd_fetch(_: argparse.Namespace) -> int:
    """Download the pinned spec sources into `tests/spec_sources/`."""
    SPEC_SOURCES.mkdir(parents=True, exist_ok=True)
    for doc in SPEC_DOCS.values():
        dest = SPEC_SOURCES / doc.cache_name
        if dest.exists():
            print(f"exists: {dest.relative_to(ROOT)}")
            continue
        dest.write_text(_download(doc.raw_url), encoding="utf-8")
        print(f"fetched: {dest.relative_to(ROOT)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Verify every quote is at its recorded lines (optionally fix the lines)."""
    problems = 0
    for rule in RULES.values():
        for src in rule.sources:
            if msg := check_quote(src.doc, src.quote, src.lines):
                problems += 1
                print(f"{rule.code} [{src.doc.version}]: {msg}")
    if not (args.fix and problems):
        return 1 if problems else 0

    # tomlkit preserves comments and formatting; it is only in the `dev` group
    import tomlkit

    doc = tomlkit.parse(REGISTRY_FILE.read_text(encoding="utf-8"))
    for code, entry in doc["rules"].items():  # type: ignore[union-attr]
        for src in entry.get("sources", []):
            for version in list(src["lines"]):
                spans = find_quote(spec_text(SPEC_DOCS[version]), src["quote"])
                if len(spans) == 1:
                    src["lines"][version] = list(spans[0])
                else:
                    print(f"{code} [{version}]: cannot fix, quote found at {spans}")
    REGISTRY_FILE.write_text(tomlkit.dumps(doc), encoding="utf-8")
    print("updated line numbers where the quote was found exactly once")
    return 0


def cmd_relocate(args: argparse.Namespace) -> int:
    """Look for the latest quote of every rule in a new version of the spec."""
    text = _download(
        f"https://raw.githubusercontent.com/{args.repo}/{args.ref}/{args.path}"
    )
    for rule in RULES.values():
        if not rule.sources or rule.removed:
            continue
        src = rule.sources[-1]
        spans = find_quote(text, src.quote)
        status = f"found at {spans}" if spans else "NOT FOUND (changed or removed?)"
        print(f"{rule.code} ({src.doc.version} quote): {status}")
    return 0


def cmd_coverage(_: argparse.Namespace) -> int:
    """Print the versions in which each rule's example fires."""
    for rule in RULES.values():
        checked = ", ".join(coverage(rule)) or "-"
        print(f"{rule.code:<12} {checked}")
    return 0


# ---------------------------------------------------------------------------
# docs
# ---------------------------------------------------------------------------


def _versions(rule: Rule) -> str:
    if rule.introduced is None:
        return "—"
    if rule.removed:
        return f"{rule.introduced} to {rule.removed}"
    return f"{rule.introduced}+"


def _rendered_examples(rule: Rule, checked: list[str]) -> list[tuple[str, str]]:
    """(introduction, JSON) of `rule`'s examples, one for each distinct document."""
    by_doc: dict[tuple[str | None, str], list[str]] = {}
    for version in checked or list(MODULES):
        if (ex := example_for(rule, version)) is not None:
            is_store = ex.store is not None
            body = ex.store if is_store else ex.json
            key = (None if is_store else ex.model, (body or "").strip())
            by_doc.setdefault(key, []).append(version)
        if not checked and by_doc:
            break
    out = []
    for (model, body), versions in by_doc.items():
        if model is None:
            names = ", ".join(f"v{v}" for v in versions)
            intro = (
                f"This {names} store (metadata files only) fails "
                "`yaozarrs.validate_zarr_store`:"
            )
        else:
            names = " or ".join(f"`{MODULES[v].__name__}.{model}`" for v in versions)
            intro = f"This document fails validation as {names}:"
        out.append((intro, body))
    return out


def render_rule(rule: Rule, checked: list[str]) -> str:
    """Markdown page for one rule."""
    lines = [f"# {rule.code}: `{rule.slug}`", ""]
    lines += [f"> {rule.summary}", ""]
    meta = [
        ("Spec keyword", rule.level or "— (not from the NGFF spec)"),
        ("yaozarrs severity", rule.default_severity),
        ("Status", rule.status),
        ("Spec versions", _versions(rule)),
        ("Checked by yaozarrs in", ", ".join(checked) or "not checked yet"),
    ]
    if rule.supersedes:
        meta.append(
            ("Supersedes", ", ".join(f"[{c}]({c}.md)" for c in rule.supersedes))
        )
    superseded_by = [r.code for r in RULES.values() if rule.code in r.supersedes]
    if superseded_by:
        meta.append(
            ("Superseded by", ", ".join(f"[{c}]({c}.md)" for c in superseded_by))
        )
    if rule.aliases:
        meta.append(("Aliases", ", ".join(f"`{a}`" for a in rule.aliases)))
    lines += ["| | |", "|---|---|"]
    lines += [f"| **{k}** | {v} |" for k, v in meta]
    lines.append("")
    if rule.notes:
        lines += ["## Notes", "", rule.notes, ""]
    if examples := _rendered_examples(rule, checked):
        lines += ["## Example", ""]
        for intro, body in examples:
            lines += [intro, "", "```json", body, "```", ""]
    if rule.sources:
        lines += ["## Spec text", ""]
        for src in reversed(rule.sources):
            start, end = src.lines
            where = f"L{start}" if start == end else f"L{start}-L{end}"
            lines += [
                f"### {src.doc.version}",
                "",
                f"> {' '.join(src.quote.split())}",
                "",
                *(
                    ["*Stated without an RFC 2119 keyword; see Notes.*", ""]
                    if src.implied
                    else []
                ),
                f"[`{src.doc.repo}@{src.doc.tag}` · `{src.doc.path}` {where}]"
                f"({src.permalink})",
                "",
            ]
    return "\n".join(lines)


def render_index(checked: dict[str, list[str]]) -> str:
    """Markdown table of all rules."""
    tracked = ", ".join(TRACKED_VERSIONS)
    lines = [
        "# Rule codes",
        "",
        "Every error or warning that yaozarrs raises for a spec violation carries a "
        "code that identifies one normative statement in the "
        "[NGFF specification](https://ngff.openmicroscopy.org/). Each code links to "
        "the exact text in the spec that supports it, for each spec version.",
        "",
        "- `NGFF-<AREA>-<NNN>` codes refer to statements in the NGFF spec.",
        "- `YZ-<NNN>` codes are checks that yaozarrs adds beyond the spec.",
        "",
        "Codes are permanent: a code is never renumbered or reused. If a statement "
        "changes meaning in a later spec version, its code is retired and a new one "
        "supersedes it.",
        "",
        "!!! note",
        "    These codes are assigned by yaozarrs; they are not (yet) part of the NGFF "
        f"specification itself. Spec versions audited so far: {tracked}. The "
        "registry does not yet cover every normative statement in those versions.",
        "",
        "| Code | Name | Keyword | Severity | Versions | Checked in | Summary |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in RULES.values():
        lines.append(
            f"| [{r.code}]({r.code}.md) | `{r.slug}` | {r.level or '—'} | "
            f"{r.default_severity} | {_versions(r)} | "
            f"{', '.join(checked[r.code]) or '—'} | {r.summary} |"
        )
    lines.append("")
    return "\n".join(lines)


def expected_docs() -> dict[str, str]:
    """Map of file name -> content for `docs/rules/`."""
    checked = {code: coverage(rule) for code, rule in RULES.items()}
    files = {"index.md": render_index(checked)}
    files.update({f"{c}.md": render_rule(r, checked[c]) for c, r in RULES.items()})
    return files


def cmd_docs(_: argparse.Namespace) -> int:
    """Write the generated docs to `docs/rules/` (gitignored)."""
    expected = expected_docs()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in {p.name for p in DOCS_DIR.glob("*.md")} - set(expected):
        (DOCS_DIR / stale).unlink()
    for name, content in expected.items():
        (DOCS_DIR / name).write_text(content, encoding="utf-8")
    print(f"wrote {len(expected)} files to {DOCS_DIR.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(required=True)
    sub.add_parser("fetch").set_defaults(func=cmd_fetch)
    p = sub.add_parser("check")
    p.add_argument("--fix", action="store_true", help="rewrite line numbers")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("relocate")
    p.add_argument("repo", help="e.g. ome/ngff-spec")
    p.add_argument("ref", help="tag or commit sha")
    p.add_argument("path", help="spec file path in the repo, e.g. index.md")
    p.set_defaults(func=cmd_relocate)
    sub.add_parser("coverage").set_defaults(func=cmd_coverage)
    sub.add_parser("docs").set_defaults(func=cmd_docs)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
