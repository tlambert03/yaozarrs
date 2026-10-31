"""Stable codes for the normative statements yaozarrs checks.

Every error or warning that yaozarrs raises for a spec violation carries a code
(e.g. `NGFF-AX-002`) that identifies one normative statement in the NGFF spec, and
links to a docs page describing it. Checks that go beyond the NGFF spec use the
`YZ-` namespace. The registry of all codes lives in `rules.toml`.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, cast

from pydantic_core import PydanticCustomError

from yaozarrs._rules._fields import RuleCodes
from yaozarrs._rules._model import Rule, SpecDoc, SpecSource
from yaozarrs._rules._registry import RULES
from yaozarrs._validation_warning import ValidationWarning

if TYPE_CHECKING:
    from typing_extensions import LiteralString

__all__ = [
    "RULES",
    "Rule",
    "RuleCodes",
    "RuleWarning",
    "SpecDoc",
    "SpecSource",
    "error_code",
    "get_rule",
    "rewrap_error",
    "rule_error",
    "rule_url",
    "warn_rule",
]


class RuleWarning(ValidationWarning, UserWarning):
    r"""A warning tied to a rule code.

    The message starts with `[<code>]`, so it can be filtered with e.g.
    `warnings.filterwarnings("ignore", message=r"\\[NGFF-PL-002\\]")`.
    """

    def __init__(self, code: str, msg: str) -> None:
        self.code = code
        self.url = rule_url(code)
        super().__init__(f"[{code}] {msg}\n  See {self.url}")


def get_rule(code: str) -> Rule:
    return RULES[code]


def rule_url(code: str) -> str:
    return get_rule(code).url


def rule_error(code: str, msg: str) -> PydanticCustomError:
    """Return an error (to be raised in a pydantic validator) for rule `code`."""
    # no context is passed, so braces in `msg` are left alone by pydantic
    template = f"{msg}\n  See {rule_url(code)}"
    return PydanticCustomError(
        cast("LiteralString", code), cast("LiteralString", template)
    )


def error_code(e: Exception) -> str | None:
    """Return the rule code of error `e`, if it has one."""
    return e.type if isinstance(e, PydanticCustomError) else None


def rewrap_error(
    e: ValueError, prefix: str = "", suffix: str = "", code: str | None = None
) -> ValueError:
    """Return `e` with more context in its message, and optionally a different code."""
    msg = str(e)
    if old := error_code(e):
        msg = msg.removesuffix(f"\n  See {rule_url(old)}")
    msg = f"{prefix}{msg}{suffix}"
    if code := code or old:
        return rule_error(code, msg)
    return ValueError(msg)


def warn_rule(code: str, msg: str, stacklevel: int = 2) -> None:
    """Emit a `RuleWarning` for rule `code`."""
    warnings.warn(RuleWarning(code, msg), stacklevel=stacklevel + 1)
