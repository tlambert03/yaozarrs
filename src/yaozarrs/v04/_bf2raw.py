from typing import Annotated, Literal

from annotated_types import MinLen
from pydantic import Field

from yaozarrs._base import ZarrGroupModel
from yaozarrs._rules import RuleCodes


class Bf2Raw(ZarrGroupModel):
    bioformats2raw_layout: Annotated[
        Literal[3], RuleCodes(missing="NGFF-BF-003", literal_error="NGFF-BF-003")
    ] = Field(
        alias="bioformats2raw.layout",
        description="The top-level identifier metadata added by bioformats2raw",
    )


class Series(ZarrGroupModel):
    """Model for the ome group that contains OME-XML metadata."""

    series: Annotated[
        list[str], MinLen(1), RuleCodes(list="NGFF-BF-004", str="NGFF-BF-004")
    ] = Field(
        description="An array of the same length and the same order as "
        "the images defined in the OME-XML"
    )
