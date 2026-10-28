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

from yaozarrs._rules._model import Rule, SpecDoc, SpecSource
from yaozarrs._rules._registry import RULES
from yaozarrs._validation_warning import ValidationWarning

if TYPE_CHECKING:
    from typing_extensions import LiteralString

__all__ = [
    "RULES",
    "Rule",
    "RuleWarning",
    "SpecDoc",
    "SpecSource",
    "get_rule",
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


def warn_rule(code: str, msg: str, stacklevel: int = 2) -> None:
    """Emit a `RuleWarning` for rule `code`."""
    warnings.warn(RuleWarning(code, msg), stacklevel=stacklevel + 1)
