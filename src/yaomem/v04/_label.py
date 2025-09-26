from typing import Annotated, Any, Literal

from annotated_types import Interval, Len, MinLen
from pydantic import Field, field_validator

from yaomem._base import _BaseModel
from yaomem._utils import UniqueList

# ------------------------------------------------------------------------------
# Color model
# ------------------------------------------------------------------------------

Int8bit = Annotated[int, Interval(ge=0, le=255)]


class LabelColor(_BaseModel):
    label_value: float = Field(
        description="The value of the label",
        alias="label-value",
    )
    rgba: Annotated[list[Int8bit], Len(min_length=4, max_length=4)] | None = Field(
        default=None,
        description=(
            "The RGBA color stored as an array of four integers between 0 and 255"
        ),
    )

    @field_validator("rgba", mode="before")
    @classmethod
    def _validate_rgba(cls, v: Any) -> Any:
        if v is not None:
            for val in v:
                if not (0 <= val <= 255):
                    raise ValueError(
                        f"RGBA values must be between 0 and 255, got {val}"
                    )
        return v


# ------------------------------------------------------------------------------
# Properties model
# ------------------------------------------------------------------------------


class LabelProperty(_BaseModel):
    label_value: int = Field(
        description="The pixel value for this label",
        alias="label-value",
    )


# ------------------------------------------------------------------------------
# Source model
# ------------------------------------------------------------------------------


class LabelSource(_BaseModel):
    image: str | None = None


# ------------------------------------------------------------------------------
# ImageLabel model
# ------------------------------------------------------------------------------


class ImageLabel(_BaseModel):
    colors: Annotated[UniqueList[LabelColor], MinLen(1)] | None = Field(
        default=None,
        description="The colors for this label image",
    )
    properties: Annotated[UniqueList[LabelProperty], MinLen(1)] | None = Field(
        default=None,
        description="The properties for this label image",
    )
    source: LabelSource | None = Field(
        default=None,
        description="The source of this label image",
    )
    version: Literal["0.4"] | None = Field(
        default=None,
        description="The version of the specification",
    )


# ------------------------------------------------------------------------------
# Label model (top-level for individual label images)
# ------------------------------------------------------------------------------


class Label(_BaseModel):
    """Model for individual label images with multiscales + image-label metadata."""

    image_label: ImageLabel = Field(alias="image-label")
