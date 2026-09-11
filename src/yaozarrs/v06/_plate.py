import re
from typing import Annotated, Literal

from annotated_types import MinLen
from pydantic import AfterValidator, Field, NonNegativeInt, PositiveInt, model_validator
from typing_extensions import Self

from yaozarrs._base import _BaseModel
from yaozarrs._types import UniqueList

from ._version import OMEV06

# NOTE (v0.6): the plate schema is structurally identical to v0.5 (only the
# `version` string changed), but the well schema changed: field-of-view paths
# now explicitly allow `._-` (with zarr node-name restrictions), see
# `FOVPathName` below.

__all__ = [  # noqa: RUF022  (don't resort, this is used for docs ordering)
    "Plate",
    "PlateDef",
    # PlateDef
    "Column",
    "Row",
    "PlateWell",
    "Acquisition",
    # Well and its dependencies
    "Well",
    "WellDef",
    "FieldOfView",
]

_FOV_PATH_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _validate_fov_path(path: str) -> str:
    # well.schema (v0.6): pattern ^[A-Za-z0-9_.-]+$, and per zarr node-name
    # rules the path must not consist only of periods or start with "__".
    if not _FOV_PATH_PATTERN.fullmatch(path):
        raise ValueError(
            f"Field-of-view path {path!r} may only contain characters in "
            "[A-Za-z0-9_.-]."
        )
    if all(c == "." for c in path):
        raise ValueError(
            f"Field-of-view path {path!r} must not consist only of periods."
        )
    if path.startswith("__"):
        raise ValueError(
            f"Field-of-view path {path!r} must not start with the reserved prefix '__'."
        )
    return path


FOVPathName = Annotated[str, AfterValidator(_validate_fov_path)]


# ------------------------------------------------------------------------------
# Acquisition model
# ------------------------------------------------------------------------------


class Acquisition(_BaseModel):
    """An imaging acquisition run within a plate.

    In high-content screening, multiple acquisition runs may be performed on the
    same plate (e.g., at different timepoints or with different settings).
    This class groups related images from a single acquisition session.
    """

    id: NonNegativeInt = Field(
        description="Unique identifier within the plate for this acquisition",
    )
    maximumfieldcount: PositiveInt | None = Field(
        default=None,
        description=(
            "Maximum number of fields-of-view across all wells in this acquisition"
        ),
    )
    name: str | None = Field(
        default=None,
        description="Human-readable name for this acquisition",
    )
    description: str | None = Field(
        default=None,
        description="Detailed description of the acquisition parameters or purpose",
    )
    starttime: NonNegativeInt | None = Field(
        default=None,
        description=(
            "Acquisition start time as Unix epoch timestamp (seconds since 1970-01-01)"
        ),
    )
    endtime: NonNegativeInt | None = Field(
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

    name: str = Field(
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

    name: str = Field(
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
    (see [`Well`][yaozarrs.v06.Well] for the complete well metadata).
    """

    path: str = Field(
        description=(
            "Relative path to the well's group (format: 'row/column', e.g., 'A/1')"
        ),
        pattern=r"^[A-Za-z0-9]+/[A-Za-z0-9]+$",
    )
    rowIndex: NonNegativeInt = Field(
        description="Zero-based index into the plate's rows list",
    )
    columnIndex: NonNegativeInt = Field(
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

    columns: Annotated[UniqueList[Column], MinLen(1)] = Field(
        description="Column definitions for the plate grid"
    )
    rows: Annotated[UniqueList[Row], MinLen(1)] = Field(
        description="Row definitions for the plate grid"
    )
    wells: Annotated[UniqueList[PlateWell], MinLen(1)] = Field(
        description="List of all wells present in this plate with their grid positions"
    )

    acquisitions: list[Acquisition] | None = Field(
        default=None,
        description="Imaging acquisition runs performed on this plate",
    )
    field_count: PositiveInt | None = Field(
        default=None,
        description="Maximum number of fields-of-view per well across the entire plate",
    )
    name: str | None = Field(
        default=None,
        description="Human-readable name for this plate",
    )

    @model_validator(mode="after")
    def _validate_well_indices(self) -> Self:
        for well in self.wells:
            if well.rowIndex >= len(self.rows):
                raise ValueError(
                    f"Well {well.path} has rowIndex {well.rowIndex} "
                    f"but only {len(self.rows)} rows exist"
                )
            if well.columnIndex >= len(self.columns):
                raise ValueError(
                    f"Well {well.path} has columnIndex {well.columnIndex} "
                    f"but only {len(self.columns)} columns exist"
                )
            # spec: rowIndex, columnIndex, and path MUST all refer to the same
            # row/column pair.
            expected = (
                f"{self.rows[well.rowIndex].name}/{self.columns[well.columnIndex].name}"
            )
            if well.path != expected:
                raise ValueError(
                    f"Well path {well.path!r} does not match the row/column "
                    f"names at rowIndex {well.rowIndex} and columnIndex "
                    f"{well.columnIndex} (expected {expected!r})"
                )
        return self

    @model_validator(mode="after")
    def _validate_unique_acquisition_ids(self) -> Self:
        # spec: each acquisition id MUST be unique within the plate.
        if self.acquisitions:
            ids = [acq.id for acq in self.acquisitions]
            if len(ids) != len(set(ids)):
                dupes = sorted({i for i in ids if ids.count(i) > 1})
                raise ValueError(f"Acquisition ids must be unique. Duplicates: {dupes}")
        return self


# ------------------------------------------------------------------------------
# Plate model (top-level)
# ------------------------------------------------------------------------------


class Plate(_BaseModel):
    """Top-level plate metadata for high-content screening.

    This model corresponds to the `zarr.json` file in a plate group, organizing
    a microplate's wells in a grid layout. Each well contains one or more
    fields-of-view, which in turn contain multiscale images.

    !!! example "Typical Structure"
        ```
        my_plate.ome.zarr
        ├── A                       # Col A
        │   ├── 1                   # Row 1
        │   │   ├── 0               # FOV 0 (in A1)
        │   │   │   ├── 0           # FOV 0 - Multiscale level 0
        │   │   │   └── zarr.json   # contains ["ome"]["multiscales"]
        │   │   ├── 1               # FOV 1 (in A1)
        │   │   │   ├── 0           # FOV 1 - Multiscale level 0
        │   │   │   └── zarr.json   # contains ["ome"]["multiscales"]
        │   │   └── zarr.json       # well metadata (contains ['ome']['well'])
        │   ├── 2
        │   │   └── ...
        │   └── 3
        │       └── ...
        ├── B
        │   └── ...
        ├── C
        │   └── ...
        └── zarr.json                # plate metadata (contains ['ome']['plate'])
        ```

    !!! note
        See also:

        - [`Well`][yaozarrs.v06.Well]
        - [`FieldOfView`][yaozarrs.v06.FieldOfView]
    """

    version: OMEV06 = Field(
        default="0.6.dev4",
        description="OME-NGFF specification version",
    )
    plate: PlateDef = Field(
        description="Plate layout and well organization",
    )

    bioformats2raw_layout: Literal[3] | None = Field(
        default=None,
        alias="bioformats2raw.layout",
        description=(
            "Marker indicating this plate was created by bioformats2raw version 3"
        ),
    )


class FieldOfView(_BaseModel):
    """A single field-of-view (imaging position) within a well.

    Wells typically contain multiple fields-of-view when the well area is larger
    than a single camera frame. Each field-of-view is a complete multiscale image.

    This class appears within the `images` list of a [`WellDef`][yaozarrs.v06.WellDef].
    """

    path: FOVPathName = Field(
        description=(
            "Relative path to this field's image group "
            "(typically a number like '0', '1', etc.)"
        ),
    )
    acquisition: int | None = Field(
        default=None,
        description=(
            "Acquisition ID linking this field to a specific acquisition run. "
            "Required when the parent plate has multiple acquisitions."
        ),
    )


class WellDef(_BaseModel):
    """Organization of fields-of-view within a well.

    This is the core content of the `well` metadata field, listing all
    imaging positions captured for this well.
    """

    images: Annotated[UniqueList[FieldOfView], MinLen(1)] = Field(
        description="List of all fields-of-view imaged in this well",
    )

    @model_validator(mode="after")
    def _validate_unique_paths(self) -> Self:
        # spec: a path "MUST NOT be a duplicate of any other path in the images
        # list" (stronger than whole-object uniqueness: same path with different
        # acquisition is still forbidden).
        paths = [img.path for img in self.images]
        if len(paths) != len(set(paths)):
            dupes = sorted({p for p in paths if paths.count(p) > 1})
            raise ValueError(f"Field-of-view paths must be unique. Duplicates: {dupes}")
        return self


# ------------------------------------------------------------------------------
# Well model (top-level)
# ------------------------------------------------------------------------------


class Well(_BaseModel):
    """Top-level well metadata within a plate.

    This model corresponds to the `zarr.json` file in a well group. It lists
    all fields-of-view (imaging positions) captured within this well.

    !!! example "Typical Structure"
        ```
        A/1/                   # Well at row A, column 1
        ├── zarr.json          # Contains this metadata
        ├── 0/                 # First field-of-view
        │   ├── zarr.json      # Image metadata
        │   ├── 0/             # Highest resolution
        │   └── 1/             # Next resolution
        └── 1/                 # Second field-of-view
        ```
    """

    version: OMEV06 = Field(
        default="0.6.dev4",
        description="OME-NGFF specification version",
    )
    well: WellDef = Field(
        description="Field-of-view organization for this well",
    )
