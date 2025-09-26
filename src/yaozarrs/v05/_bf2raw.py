from typing import Literal

from pydantic import Field

from yaozarrs._base import _BaseModel


class Bf2Raw(_BaseModel):
    version: Literal["0.5"] = "0.5"
    bioformats2raw_layout: Literal[3] = Field(
        alias="bioformats2raw.layout",
        description="The top-level identifier metadata added by bioformats2raw",
    )
