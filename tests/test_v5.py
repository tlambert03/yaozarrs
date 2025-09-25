import pytest

from yaomem import v05

X_AXIS = {"name": "x", "type": "space", "unit": None}
Y_AXIS = {"name": "y", "type": "space", "unit": None}
Z_AXIS = {"name": "z", "type": "space", "unit": None}


def scale_tform(d: int) -> dict:
    return {"type": "scale", "scale": [1] * d}


V05_VALID_IMAGES = [
    {
        "version": "0.5",
        "multiscales": [
            {
                "name": "image",
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]},
                    {"path": "1", "coordinateTransformations": [scale_tform(2)]},
                ],
            }
        ],
    }
]


@pytest.mark.parametrize("obj", V05_VALID_IMAGES)
def test_valid_images(obj: dict) -> None:
    v05.Image.model_validate(obj)
