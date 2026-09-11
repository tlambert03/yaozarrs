"""Tests for the `UniqueList` annotated type."""

import time
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from yaozarrs._types import UniqueList, _canonical_key


class Item(BaseModel):
    name: str
    value: int = 0


class OtherItem(BaseModel):
    name: str
    value: int = 0


class Model(BaseModel):
    items: UniqueList[Item]


class Basic(BaseModel):
    items: UniqueList[Any]


def test_unique_list_accepts_unique_items() -> None:
    model = Model(items=[Item(name="a"), Item(name="b"), Item(name="a", value=1)])
    assert len(model.items) == 3


def test_unique_list_rejects_duplicates() -> None:
    with pytest.raises(ValidationError, match="List items are not unique"):
        Model(items=[Item(name="a"), Item(name="b"), Item(name="a")])


def test_unique_list_reports_first_duplicate_pair() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Model(items=[Item(name="a"), Item(name="b"), Item(name="a"), Item(name="b")])
    # indices are reported lowest-first, and the earliest duplicate pair wins
    assert "(0, 2)" in str(exc_info.value)


def test_unique_list_json_schema() -> None:
    assert Model.model_json_schema()["properties"]["items"]["uniqueItems"] is True


# --- JSON-equivalence semantics -------------------------------------------------
# `BaseModel.__eq__` compares classes, so distinct model classes are never equal,
# even with identical fields -- and same-named classes in different modules must
# not collide either.


def test_distinct_model_classes_are_not_duplicates() -> None:
    class Mixed(BaseModel):
        items: UniqueList[Any]

    assert len(Mixed(items=[Item(name="a"), OtherItem(name="a")]).items) == 2


def test_same_named_models_in_different_modules_are_not_duplicates() -> None:
    """`v04.Column` and `v05.Column` share a class name but are distinct models."""
    from yaozarrs import v04, v05

    a, b = v04.Column(name="1"), v05.Column(name="1")
    assert a != b  # BaseModel.__eq__ compares classes
    assert _canonical_key(a) != _canonical_key(b)
    assert len(Basic(items=[a, b]).items) == 2


@pytest.mark.parametrize(
    "items",
    [
        ["a", "b", "c"],
        [1, 2, 3],
        [None, False, "x"],
        [{"a": 1, "b": 2}, {"b": 2, "a": 1, "c": 3}],
        [{"a": 1}, {"a": 2}],
        [["a"], ["b"]],
        [["a"], ["a", "b"]],  # differing lengths are unequal, not an error
        [[1, [2]], [1, [3]]],
    ],
)
def test_unique_non_model_items(items: list) -> None:
    assert Basic(items=items).items == items


@pytest.mark.parametrize(
    "items",
    [
        ["a", "b", "a"],
        [1, 2, 1],
        [1, 1.0],  # numeric equivalence, as with `a == b`
        [1, True],
        [{"a": 1, "b": 2}, {"b": 2, "a": 1}],  # key order is irrelevant
        [["a"], ["a"]],
        [["a"], ("a",)],  # list/tuple are both JSON arrays
        [{"a": [1, {"b": 2}]}, {"a": [1, {"b": 2}]}],
    ],
)
def test_duplicate_non_model_items(items: list) -> None:
    with pytest.raises(ValidationError, match="List items are not unique"):
        Basic(items=items)


def test_int_keyed_and_str_keyed_mappings_differ() -> None:
    assert Basic(items=[{1: "a"}, {"1": "a"}]).items == [{1: "a"}, {"1": "a"}]


def test_unorderable_mapping_keys() -> None:
    assert Basic(items=[{1: "a", "b": 2}]).items == [{1: "a", "b": 2}]


def test_unsupported_type_raises_type_error() -> None:
    with pytest.raises(TypeError, match="Unsupported type for JSON equivalence"):
        Basic(items=[{1, 2}])


# --- performance ----------------------------------------------------------------


def test_unique_list_is_not_quadratic() -> None:
    """Validation must scale ~linearly (see #54)."""

    def _elapsed(n: int) -> float:
        items = [Item(name=str(i)) for i in range(n)]
        t0 = time.perf_counter()
        Model(items=items)
        return time.perf_counter() - t0

    _elapsed(500)  # warmup
    small = _elapsed(1000)
    large = _elapsed(8000)
    # quadratic would be ~64x; allow generous headroom for timing noise
    assert large < max(small, 1e-3) * 20
