from typing import Annotated, TypeAlias

from pydantic import AfterValidator, Field

from yaozarrs._base import _BaseModel
from yaozarrs._rules import RuleCodes, rule_error
from yaozarrs._types import duplicates

from ._axes import AxesList

__all__ = ["CoordinateSystem"]


class CoordinateSystem(_BaseModel):
    """A named set of axes in which coordinates (e.g. physical positions) are expressed.

    Coordinate transformations map points between coordinate systems, referring to
    them by `name`.
    """

    # MUST contain the field `name`. The value MUST be a non-empty string ...
    name: Annotated[
        str,
        RuleCodes(missing="YZ-CS-001", str="YZ-CS-002", string_too_short="YZ-CS-002"),
    ] = Field(min_length=1, description="Name of the coordinate system.")
    # MUST contain the field `axes`, whose value is an array of valid `axes`
    axes: Annotated[
        AxesList,
        RuleCodes(
            missing="YZ-CS-004", list="YZ-CS-004", listItemsNotUnique="YZ-AX-001"
        ),
    ] = Field(description="The axes of this coordinate system.")

    @property
    def ndim(self) -> int:
        """Number of axes (dimensions) in this coordinate system."""
        return len(self.axes)


def _validate_names(systems: list[CoordinateSystem]) -> list[CoordinateSystem]:
    # [name] MUST be a non-empty string that is unique among all entries in a
    # `coordinateSystems` array.
    if dupes := duplicates([cs.name for cs in systems]):
        raise rule_error(
            "YZ-CS-003",
            f"Coordinate system names must be unique. Duplicates: {dupes}",
        )
    return systems


# (unique names imply uniqueItems, which coordinate_systems.schema declares, but
# image.schema doesn't for a multiscale's coordinateSystems; see `SceneDef`)
CoordinateSystemsList: TypeAlias = Annotated[
    list[CoordinateSystem], AfterValidator(_validate_names)
]
