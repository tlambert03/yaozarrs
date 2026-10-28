"""Rule codes for pydantic's own errors on model fields (missing, wrong type, ...)."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any, cast, get_args

from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError, core_schema
from pydantic_core.core_schema import ErrorType

from yaozarrs._rules._registry import RULES

if TYPE_CHECKING:
    from pydantic import BaseModel
    from pydantic_core import CoreSchema, ErrorDetails
    from typing_extensions import LiteralString

_BUILTIN_TYPES = frozenset(get_args(ErrorType))

# shorthands for groups of pydantic error types
_ERROR_GROUPS: dict[str, tuple[str, ...]] = {
    "int": ("int_type", "int_parsing", "int_from_float"),
    "str": ("string_type",),
    "list": ("list_type",),
    "object": ("model_type",),
}


class RuleCodes:
    """Field metadata: maps pydantic error types on the field to rule codes.

    Use in `Annotated`, at the top level of a field's type, e.g.
    `id: Annotated[int, RuleCodes(missing="NGFF-PL-009", int="NGFF-PL-010")]`.

    Keys are pydantic error types (`missing`, `greater_than`, ...), or one of the
    shorthands `int`, `str`, `list`, `object`. An error gets the code only if it is
    on the field itself or on an item of it (e.g. `("rgba", 2)`), not inside a
    nested model or union member. Use one `RuleCodes` per field: pydantic < 2.6
    keeps only one metadata object of each type.
    """

    __slots__ = ("codes",)

    def __init__(self, **codes: str) -> None:
        self.codes: dict[str, str] = {}
        for key, code in codes.items():
            if code not in RULES:
                raise KeyError(f"Unknown rule code: {code!r}")
            self.codes.update(dict.fromkeys(_ERROR_GROUPS.get(key, (key,)), code))

    def __repr__(self) -> str:
        return f"RuleCodes({', '.join(f'{k}={v!r}' for k, v in self.codes.items())})"


@cache
def _field_codes(cls: type[BaseModel]) -> dict[str, dict[str, str]]:
    """Map of field name (and alias) to its {pydantic error type: rule code}."""
    out: dict[str, dict[str, str]] = {}
    for name, info in cls.model_fields.items():
        codes = {}
        for m in info.metadata:
            if isinstance(m, RuleCodes):
                codes.update(m.codes)
        if codes:
            out[name] = codes
            if info.alias:
                out[info.alias] = codes
    return out


def _code_for(err: ErrorDetails, field_codes: dict[str, dict[str, str]]) -> str | None:
    loc = err["loc"]
    # only errors on the field itself, or on an item of it
    if not loc or not all(isinstance(x, int) for x in loc[1:]):
        return None
    return field_codes.get(str(loc[0]), {}).get(err["type"])


def _custom(type_: str, msg: str, ctx: dict[str, Any] | None) -> PydanticCustomError:
    return PydanticCustomError(
        cast("LiteralString", type_), cast("LiteralString", msg), ctx
    )


def tag_field_errors(cls: type[BaseModel], exc: ValidationError) -> ValidationError:
    """Return `exc`, with errors on fields of `cls` re-typed to their rule codes."""
    if not (field_codes := _field_codes(cls)):
        return exc
    errors = exc.errors(include_url=False)
    codes = [_code_for(err, field_codes) for err in errors]
    if not any(codes):
        return exc

    details: list[InitErrorDetails] = []
    for err, code in zip(errors, codes):
        type_, ctx = err["type"], err.get("ctx")
        detail: InitErrorDetails = {
            "type": type_,
            "loc": err["loc"],
            "input": err["input"],
        }
        if code is not None:
            msg = f"{err['msg']}\n  See {RULES[code].url}"
            detail["type"] = _custom(code, msg, {**(ctx or {}), "pydantic_type": type_})
        elif type_ not in _BUILTIN_TYPES:  # custom errors must be re-created as such
            detail["type"] = _custom(type_, err["msg"], ctx)
        elif ctx:
            detail["ctx"] = ctx
        details.append(detail)
    return ValidationError.from_exception_data(exc.title, details)


def with_field_rules(cls: type[BaseModel], schema: CoreSchema) -> CoreSchema:
    """Wrap the fields validator of `cls`'s model `schema` with `tag_field_errors`.

    The wrapper goes inside the `model` schema rather than around it (as a
    `model_validator(mode="wrap")` would), so that pydantic still labels the model
    by its class name in union error locations and titles.
    """
    node: Any = schema
    while node.get("type") != "model":
        if (node := node.get("schema")) is None:
            return schema

    def _validate(value: Any, handler: core_schema.ValidatorFunctionWrapHandler) -> Any:
        try:
            return handler(value)
        except ValidationError as e:
            if (tagged := tag_field_errors(cls, e)) is e:
                raise
            raise tagged from None

    node["schema"] = core_schema.no_info_wrap_validator_function(
        _validate, node["schema"]
    )
    return schema
