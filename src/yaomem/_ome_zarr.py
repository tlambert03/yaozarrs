from . import v05
from ._base import _BaseModel


class OMEZarr(_BaseModel):
    """Model with *any* valid OME-Zarr structure."""

    ome: v05.OMENode
