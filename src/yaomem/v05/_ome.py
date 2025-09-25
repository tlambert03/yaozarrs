"""OME-Zarr group produced by bioformats2raw to contain OME metadata."""

from typing import Annotated, Literal

from annotated_types import MinLen
from pydantic import Field

from ._base import _BaseModel


class OME(_BaseModel):
    """Model for the ome group that contains OME-XML metadata."""

    version: Literal["0.5"] = "0.5"
    series: Annotated[list[str], MinLen(1)] = Field(
        description="An array of the same length and the same order as "
        "the images defined in the OME-XML"
    )
