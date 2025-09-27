"""Yet another ome-zarr model."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yaozarrs")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "uninstalled"

from . import v05
from ._validate import validate_ome_json, validate_ome_node

__all__ = ["v05", "validate_ome_json", "validate_ome_node"]
