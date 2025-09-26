import pytest
from pydantic import ValidationError

from yaomem import v04

V04_VALID_LABELS = [
    # Simple label with just version
    {"image-label": {"version": "0.4"}},
    # Label with colors
    {
        "image-label": {
            "colors": [
                {"label-value": 1, "rgba": [255, 0, 0, 255]},
                {"label-value": 2, "rgba": [0, 255, 0, 255]},
            ]
        }
    },
    # Label with properties
    {"image-label": {"properties": [{"label-value": 1}, {"label-value": 2}]}},
    # Label with source
    {"image-label": {"source": {"image": "../image.zarr"}}},
    # Label with all fields
    {
        "image-label": {
            "version": "0.4",
            "colors": [{"label-value": 1, "rgba": [255, 0, 0, 255]}],
            "properties": [{"label-value": 1}],
            "source": {"image": "../image.zarr"},
        }
    },
    # Label with colors without RGBA (valid since rgba is optional)
    {"image-label": {"colors": [{"label-value": 1.5}, {"label-value": 2.0}]}},
]


V04_INVALID_LABELS = [
    # Missing image-label
    {},
    # Empty image-label is actually valid per schema
    # {"image-label": {}},
    # Invalid RGBA values (out of range)
    {
        "image-label": {
            "colors": [
                {
                    "label-value": 1,
                    "rgba": [256, 0, 0, 255],  # 256 is out of range
                }
            ]
        }
    },
    # Invalid RGBA array length
    {
        "image-label": {
            "colors": [
                {
                    "label-value": 1,
                    "rgba": [255, 0, 0],  # Should be 4 elements
                }
            ]
        }
    },
    # Empty colors array (should have minItems: 1)
    {"image-label": {"colors": []}},
    # Empty properties array (should have minItems: 1)
    {"image-label": {"properties": []}},
    # Missing required label-value in colors
    {
        "image-label": {
            "colors": [
                {"rgba": [255, 0, 0, 255]}  # Missing label-value
            ]
        }
    },
    # Missing required label-value in properties
    {
        "image-label": {
            "properties": [
                {}  # Missing label-value
            ]
        }
    },
]


@pytest.mark.parametrize("data", V04_VALID_LABELS)
def test_valid_v04_labels(data):
    """Test that valid v04 label metadata can be parsed."""
    label = v04.Label.model_validate(data)
    assert label.image_label is not None


@pytest.mark.parametrize("data", V04_INVALID_LABELS)
def test_invalid_v04_labels(data):
    """Test that invalid v04 label metadata raises validation errors."""
    with pytest.raises(ValidationError):
        v04.Label.model_validate(data)


def test_v04_label_color_rgba_validation():
    """Test RGBA color validation."""
    # Valid RGBA values
    color = v04.LabelColor(**{"label-value": 1, "rgba": [255, 128, 0, 255]})
    assert color.rgba == [255, 128, 0, 255]

    # Test without RGBA
    color_no_rgba = v04.LabelColor(**{"label-value": 2})
    assert color_no_rgba.rgba is None

    # Invalid RGBA values should raise ValidationError
    with pytest.raises(ValidationError):
        v04.LabelColor(**{"label-value": 1, "rgba": [256, 0, 0, 255]})  # 256 > 255

    with pytest.raises(ValidationError):
        v04.LabelColor(**{"label-value": 1, "rgba": [-1, 0, 0, 255]})  # -1 < 0


def test_v04_label_properties():
    """Test label properties."""
    prop = v04.LabelProperty(**{"label-value": 42})
    assert prop.label_value == 42


def test_v04_label_source():
    """Test label source."""
    source = v04.LabelSource(image="../parent.zarr")
    assert source.image == "../parent.zarr"

    # Test without image
    empty_source = v04.LabelSource()
    assert empty_source.image is None


def test_v04_image_label():
    """Test ImageLabel model."""
    image_label = v04.ImageLabel(
        version="0.4",
        colors=[v04.LabelColor(**{"label-value": 1, "rgba": [255, 0, 0, 255]})],
        properties=[v04.LabelProperty(**{"label-value": 1})],
        source=v04.LabelSource(image="../source.zarr"),
    )

    assert image_label.version == "0.4"
    assert len(image_label.colors) == 1
    assert len(image_label.properties) == 1
    assert image_label.source.image == "../source.zarr"


def test_v04_validate_label_as_ome_node():
    """Test that v04 labels can be validated as OME nodes."""
    data = {"image-label": {"colors": [{"label-value": 1, "rgba": [255, 0, 0, 255]}]}}

    # Should validate as a Label
    result = v04.Label.model_validate(data)
    assert isinstance(result, v04.Label)
