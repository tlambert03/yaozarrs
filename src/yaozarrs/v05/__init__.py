"""v05 ome-zarr model.

https://ngff.openmicroscopy.org/0.5/
https://github.com/ome/ngff/tree/8cbba216e37407bd2d4bd5c7128ab13bd0a6404e
"""

from typing import TypeAlias

from pydantic import BaseModel

from yaozarrs.v05._bf2raw import Bf2Raw
from yaozarrs.v05._ome import OME

from ._image import (
    ChannelAxis,
    CustomAxis,
    Dataset,
    Image,
    Multiscale,
    Omero,
    OmeroChannel,
    OmeroWindow,
    ScaleTransformation,
    SpaceAxis,
    TimeAxis,
    TranslationTransformation,
)
from ._label import (
    ImageLabel,
    Label,
    LabelColor,
    LabelProperty,
    LabelsGroup,
    LabelSource,
)
from ._plate import Acquisition, Column, Plate, PlateDef, PlateWell, Row
from ._well import FieldOfView, Well, WellDef

__all__ = [
    "Acquisition",
    "ChannelAxis",
    "Column",
    "CustomAxis",
    "Dataset",
    "FieldOfView",
    "Image",
    "ImageLabel",
    "Label",
    "LabelColor",
    "LabelProperty",
    "LabelSource",
    "LabelsGroup",
    "Multiscale",
    "Omero",
    "OmeroChannel",
    "OmeroWindow",
    "Plate",
    "PlateDef",
    "PlateWell",
    "Row",
    "ScaleTransformation",
    "SpaceAxis",
    "TimeAxis",
    "TranslationTransformation",
    "Well",
    "WellDef",
]


OMENode: TypeAlias = Image | Plate | Label | Well | OME | Bf2Raw
"""Anything that can live in the "ome" key of a v0.5 ome-zarr file."""


class OMEZarr(BaseModel):
    ome: OMENode
