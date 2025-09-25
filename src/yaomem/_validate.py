from typing import Any, TypeVar, overload

from pydantic import TypeAdapter

from .v05 import OMENode

T = TypeVar("T", bound=OMENode)


@overload
def validate_ome_node(node: Any, cls: type[T]) -> T: ...
@overload
def validate_ome_node(node: Any) -> OMENode: ...
def validate_ome_node(node: Any, cls: type[T] | Any = None) -> T | OMENode:
    """Validate any ome-zarr document or node.

    Parameters
    ----------
    node : OMENode
        The OMENode instance to validate.
    cls : type[T]
        The class to validate against. Must be a subclass of `BaseModel`.
        If not provided, defaults to `OMENode`, meaning any valid OME node object

    Raises
    ------
    pydantic.ValidationError
        If the validation fails.
    """
    adapter = TypeAdapter[T](cls or OMENode)
    return adapter.validate_python(node)
