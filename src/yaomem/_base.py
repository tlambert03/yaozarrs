from typing import ClassVar

from pydantic import BaseModel, ConfigDict

__all__ = ["_BaseModel"]


class _BaseModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore",
        validate_assignment=True,
        validate_default=True,
    )
