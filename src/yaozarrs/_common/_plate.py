"""Plate building blocks (identical in v0.5 and v0.6)."""

from typing import Annotated

from annotated_types import MinLen
from pydantic import Field, NonNegativeInt, PositiveInt, model_validator
from typing_extensions import Self

from yaozarrs._base import _BaseModel
from yaozarrs._rules import RuleCodes, rule_error, warn_rule
from yaozarrs._types import UniqueList

# ------------------------------------------------------------------------------
# Acquisition model
# ------------------------------------------------------------------------------


class Acquisition(_BaseModel):
    """An imaging acquisition run within a plate.

    In high-content screening, multiple acquisition runs may be performed on the
    same plate (e.g., at different timepoints or with different settings).
    This class groups related images from a single acquisition session.
    """

    id: Annotated[
        NonNegativeInt,
        RuleCodes(missing="YZ-PL-009", int="YZ-PL-010", greater_than_equal="YZ-PL-010"),
    ] = Field(
        description="Unique identifier within the plate for this acquisition",
    )
    maximumfieldcount: Annotated[
        PositiveInt | None, RuleCodes(int="YZ-PL-012", greater_than="YZ-PL-012")
    ] = Field(
        default=None,
        description=(
            "Maximum number of fields-of-view across all wells in this acquisition"
        ),
    )
    name: Annotated[str | None, RuleCodes(str="YZ-PL-011")] = Field(
        default=None,
        description="Human-readable name for this acquisition",
    )
    description: Annotated[str | None, RuleCodes(str="YZ-PL-013")] = Field(
        default=None,
        description="Detailed description of the acquisition parameters or purpose",
    )
    starttime: Annotated[
        NonNegativeInt | None,
        RuleCodes(int="YZ-PL-014"),
    ] = Field(
        default=None,
        description=(
            "Acquisition start time as Unix epoch timestamp (seconds since 1970-01-01)"
        ),
    )
    endtime: Annotated[NonNegativeInt | None, RuleCodes(int="YZ-PL-014")] = Field(
        default=None,
        description=(
            "Acquisition end time as Unix epoch timestamp (seconds since 1970-01-01)"
        ),
    )


# ------------------------------------------------------------------------------
# Column model
# ------------------------------------------------------------------------------


class Column(_BaseModel):
    """A column in the plate grid.

    Columns are typically numbered (1, 2, 3, ...) but can use any
    alphanumeric identifier.
    """

    name: Annotated[
        str,
        RuleCodes(
            missing="YZ-PL-017",
            str="YZ-PL-036",
            string_pattern_mismatch="YZ-PL-018",
        ),
    ] = Field(
        description="Column identifier (typically numeric, e.g., '1', '2', '3')",
        pattern=r"^[A-Za-z0-9]+$",
    )


# ------------------------------------------------------------------------------
# Row model
# ------------------------------------------------------------------------------


class Row(_BaseModel):
    """A row in the plate grid.

    Rows are typically lettered (A, B, C, ...) but can use any alphanumeric identifier.
    """

    name: Annotated[
        str,
        RuleCodes(
            missing="YZ-PL-024",
            str="YZ-PL-025",
            string_pattern_mismatch="YZ-PL-026",
        ),
    ] = Field(
        description="Row identifier (typically alphabetic, e.g., 'A', 'B', 'C')",
        pattern=r"^[A-Za-z0-9]+$",
    )


# ------------------------------------------------------------------------------
# Well model
# ------------------------------------------------------------------------------


# naming this PlateWell to disambiguate from a top level Well (see _well.py)
class PlateWell(_BaseModel):
    """A well location reference within a plate.

    Maps a well's row/column position to its data location. This is a
    lightweight reference used in plate metadata, not the full well group
    (see the top-level `Well` model for the complete well metadata).
    """

    path: Annotated[
        str,
        RuleCodes(
            missing="YZ-PL-030",
            str="YZ-PL-031",
            string_pattern_mismatch="YZ-PL-032",
        ),
    ] = Field(
        description=(
            "Relative path to the well's group (format: 'row/column', e.g., 'A/1')"
        ),
        pattern=r"^[A-Za-z0-9]+/[A-Za-z0-9]+$",
    )
    rowIndex: Annotated[
        NonNegativeInt,
        RuleCodes(missing="YZ-PL-033", int="YZ-PL-034", greater_than_equal="YZ-PL-004"),
    ] = Field(
        description="Zero-based index into the plate's rows list",
    )
    columnIndex: Annotated[
        NonNegativeInt,
        RuleCodes(missing="YZ-PL-033", int="YZ-PL-035", greater_than_equal="YZ-PL-005"),
    ] = Field(
        description="Zero-based index into the plate's columns list",
    )


# ------------------------------------------------------------------------------
# Plate model
# ------------------------------------------------------------------------------


class PlateDef(_BaseModel):
    """Plate layout and well organization.

    Defines the grid structure of a microplate and maps wells to their data.
    This is the core content of the `plate` metadata field.
    """

    columns: Annotated[
        UniqueList[Column],
        MinLen(1),
        RuleCodes(
            missing="YZ-PL-015",
            list="YZ-PL-016",
            object="YZ-PL-016",
            too_short="YZ-PL-037",
            listItemsNotUnique="YZ-PL-019",
        ),
    ] = Field(description="Column definitions for the plate grid")
    rows: Annotated[
        UniqueList[Row],
        MinLen(1),
        RuleCodes(
            missing="YZ-PL-022",
            list="YZ-PL-023",
            object="YZ-PL-023",
            too_short="YZ-PL-038",
            listItemsNotUnique="YZ-PL-027",
        ),
    ] = Field(description="Row definitions for the plate grid")
    wells: Annotated[
        UniqueList[PlateWell],
        MinLen(1),
        RuleCodes(
            missing="YZ-PL-028",
            list="YZ-PL-029",
            object="YZ-PL-029",
            too_short="YZ-PL-039",
            listItemsNotUnique="YZ-PL-040",
        ),
    ] = Field(
        description="List of all wells present in this plate with their grid positions"
    )

    acquisitions: Annotated[
        list[Acquisition] | None, RuleCodes(list="YZ-PL-008", object="YZ-PL-008")
    ] = Field(
        default=None,
        description="Imaging acquisition runs performed on this plate",
    )
    field_count: Annotated[
        PositiveInt | None, RuleCodes(int="YZ-PL-020", greater_than="YZ-PL-020")
    ] = Field(
        default=None,
        description="Maximum number of fields-of-view per well across the entire plate",
    )
    name: Annotated[str | None, RuleCodes(str="YZ-PL-021")] = Field(
        default=None,
        description="Human-readable name for this plate",
    )

    @model_validator(mode="after")
    def _validate_well_indices(self) -> Self:
        for well in self.wells:
            if well.rowIndex >= len(self.rows):
                raise rule_error(
                    "YZ-PL-004",
                    f"Well {well.path} has rowIndex {well.rowIndex} "
                    f"but only {len(self.rows)} rows exist",
                )
            if well.columnIndex >= len(self.columns):
                raise rule_error(
                    "YZ-PL-005",
                    f"Well {well.path} has columnIndex {well.columnIndex} "
                    f"but only {len(self.columns)} columns exist",
                )
            # The `rowIndex`, `columnIndex`, and `path` MUST all refer to the same
            # row/column pair.
            row = self.rows[well.rowIndex].name
            col = self.columns[well.columnIndex].name
            if well.path != f"{row}/{col}":
                raise rule_error(
                    "YZ-PL-006",
                    f"Well path {well.path!r} does not match its rowIndex "
                    f"({well.rowIndex}) and columnIndex ({well.columnIndex}), "
                    f"which refer to '{row}/{col}'",
                )
        return self

    @model_validator(mode="after")
    def _warn_case_collisions(self) -> Self:
        # Care SHOULD be taken to avoid collisions on case-insensitive filesystems
        # (e.g. avoid using both `Aa` and `aA`).
        for kind, code, items in (
            ("row", "YZ-PL-003", self.rows),
            ("column", "YZ-PL-002", self.columns),
        ):
            lowered = [x.name.lower() for x in items]
            if clashes := [x.name for x in items if lowered.count(x.name.lower()) > 1]:
                warn_rule(
                    code,
                    f"Plate {kind} names {clashes} differ only by case, which will "
                    "collide on case-insensitive filesystems.",
                    stacklevel=2,
                )
        return self

    @model_validator(mode="after")
    def _validate_acquisition_ids(self) -> Self:
        # Each acquisition object MUST contain an `id` key whose value MUST be an
        # unique integer identifier greater than or equal to 0 within the context
        # of the plate
        ids = [acq.id for acq in self.acquisitions or ()]
        if dupes := sorted({i for i in ids if ids.count(i) > 1}):
            raise rule_error(
                "YZ-PL-001",
                f"Acquisition ids must be unique within a plate. Duplicates: {dupes}",
            )
        return self
