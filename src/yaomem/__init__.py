"""Yet another ome-zarr model."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yaomem")
except PackageNotFoundError:
    __version__ = "uninstalled"
__author__ = "Talley Lambert"
__email__ = "talley.lambert@gmail.com"
