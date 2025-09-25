"""v05 ome-zarr model.

https://ngff.openmicroscopy.org/0.5/
https://github.com/ome/ngff/tree/8cbba216e37407bd2d4bd5c7128ab13bd0a6404e
"""

from typing import TypeAlias

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

__all__ = [
    "ChannelAxis",
    "CustomAxis",
    "Dataset",
    "Image",
    "Multiscale",
    "Omero",
    "OmeroChannel",
    "OmeroWindow",
    "ScaleTransformation",
    "SpaceAxis",
    "TimeAxis",
    "TranslationTransformation",
]


V5OMENode: TypeAlias = Image  # TODO: union
"""Anything that can live in th "ome" key of a v0.5 ome-zarr file."""
