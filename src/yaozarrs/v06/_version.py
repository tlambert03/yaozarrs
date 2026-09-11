"""Shared version type for OME-NGFF v0.6 models."""

import re
from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator

# Accept the 0.6 line: "0.6", "0.6.0", and dev tags like "0.6.dev4". Reject a
# 0.6.Z *patch* release where Z is a numeral > 0 (e.g. "0.6.1") -- that would
# be different content we don't claim to support -- and anything not in 0.6
# (e.g. "0.5", "0.66").
_V06_PATTERN = re.compile(r"^0\.6(\.0|\.dev\d+)?$")


def _validate_v06_version(v: str) -> str:
    if not _V06_PATTERN.fullmatch(v):
        raise ValueError(
            f"version must be '0.6', '0.6.0', or a '0.6.devN' tag, got {v!r}"
        )
    return v


# `Literal["0.6"]` surfaces the canonical value for IDE autocompletion, while the
# `| str` + validator accept the full 0.6 line (e.g. "0.6.dev4", "0.6", "0.6.0")
# so we don't have to bump anything when v0.6 lands or when testing newer dev tags.
OMEV06: TypeAlias = Annotated[
    Literal["0.6"] | str, AfterValidator(_validate_v06_version)
]
