import pytest
from pydantic import ValidationError

from yaozarrs import v04

X_AXIS = {"name": "x", "type": "space", "unit": "millimeter"}
Y_AXIS = {"name": "y", "type": "space", "unit": None}
Z_AXIS = {"name": "z", "type": "space", "unit": None}
T_AXIS = {"name": "t", "type": "time", "unit": "second"}
C_AXIS = {"name": "c", "type": "channel"}


def scale_tform(d: int) -> dict:
    return {"type": "scale", "scale": [1] * d}


def translate_tform(d: int, offset: float = 10.0) -> dict:
    return {"type": "translation", "translation": [offset] * d}


V04_VALID_IMAGES = [
    {
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
    },
    # Test with 3D space axes
    {
        "multiscales": [
            {
                "name": "image3d",
                "axes": [X_AXIS, Y_AXIS, Z_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]},
                ],
            }
        ],
    },
    # Test with time axis
    {
        "multiscales": [
            {
                "name": "timeseries",
                "axes": [T_AXIS, X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]},
                ],
            }
        ],
    },
    # Test with channel axis
    {
        "multiscales": [
            {
                "name": "multichannel",
                "axes": [C_AXIS, X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]},
                ],
            }
        ],
    },
    # Test with all axes
    {
        "multiscales": [
            {
                "name": "full5d",
                "axes": [T_AXIS, C_AXIS, Z_AXIS, Y_AXIS, X_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(5)]},
                ],
            }
        ],
    },
    # Test with translation transformation
    {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {
                        "path": "0",
                        "coordinateTransformations": [
                            scale_tform(2),
                            translate_tform(2),
                        ],
                    },
                ],
            }
        ],
    },
    # Test with omero metadata
    {
        "multiscales": [
            {
                "axes": [C_AXIS, Y_AXIS, X_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]},
                ],
            }
        ],
        "omero": {
            "channels": [
                {
                    "window": {"start": 0, "min": 0, "end": 100, "max": 255},
                    "color": "FF0000",
                }
            ]
        },
    },
]


V04_INVALID_IMAGES = [
    # Missing required multiscales
    {},
    # Empty multiscales array
    {"multiscales": []},
    # Missing axes
    {
        "multiscales": [
            {
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]},
                ]
            }
        ]
    },
    # Insufficient space axes (only 1)
    {
        "multiscales": [
            {
                "axes": [X_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(1)]},
                ],
            }
        ]
    },
    # Too many space axes (4)
    {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS, Z_AXIS, {"name": "w", "type": "space"}],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(4)]},
                ],
            }
        ]
    },
    # Multiple time axes
    {
        "multiscales": [
            {
                "axes": [T_AXIS, {"name": "t2", "type": "time"}, X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(4)]},
                ],
            }
        ]
    },
    # Multiple channel axes
    {
        "multiscales": [
            {
                "axes": [C_AXIS, {"name": "c2", "type": "channel"}, X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(4)]},
                ],
            }
        ]
    },
    # No scale transformation
    {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [translate_tform(2)]},
                ],
            }
        ]
    },
    # Multiple scale transformations
    {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {
                        "path": "0",
                        "coordinateTransformations": [scale_tform(2), scale_tform(2)],
                    },
                ],
            }
        ]
    },
    # Mismatched transformation dimensions
    {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]},
                ],
            }
        ]
    },
    # Empty datasets
    {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [],
            }
        ]
    },
    # Duplicate axis names
    {
        "multiscales": [
            {
                "axes": [X_AXIS, X_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]},
                ],
            }
        ]
    },
]


@pytest.mark.parametrize("data", V04_VALID_IMAGES)
def test_valid_v04_images(data: dict) -> None:
    """Test that valid v04 image metadata can be parsed."""
    img = v04.Image.model_validate(data)
    assert img.multiscales
    assert len(img.multiscales) >= 1


@pytest.mark.parametrize("data", V04_INVALID_IMAGES)
def test_invalid_v04_images(data: dict) -> None:
    """Test that invalid v04 image metadata raises validation errors."""
    with pytest.raises(ValidationError):
        v04.Image.model_validate(data)


def test_v04_image_with_omero() -> None:
    """Test v04 image with OMERO metadata."""
    data = {
        "multiscales": [
            {
                "axes": [C_AXIS, Y_AXIS, X_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]},
                ],
            }
        ],
        "omero": {
            "channels": [
                {
                    "window": {"start": 0.0, "min": 0.0, "end": 100.0, "max": 255.0},
                    "color": "FF0000",
                    "label": "Red Channel",
                    "active": True,
                }
            ]
        },
    }

    img = v04.Image.model_validate(data)
    assert img.omero is not None
    assert len(img.omero.channels) == 1
    assert img.omero.channels[0].color == "FF0000"


def test_v04_multiscale_properties() -> None:
    """Test v04 multiscale properties."""
    data = {
        "multiscales": [
            {
                "name": "test_image",
                "version": "0.4",
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]},
                ],
                "coordinateTransformations": [scale_tform(2)],
            }
        ]
    }

    img = v04.Image.model_validate(data)
    ms = img.multiscales[0]
    assert ms.name == "test_image"
    assert ms.version == "0.4"
    assert ms.ndim == 2
    assert ms.coordinateTransformations is not None


def test_v04_validate_ome_node() -> None:
    """Test that v04 images can be validated as OME nodes."""
    data = {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]},
                ],
            }
        ]
    }

    # Should validate as an Image
    result = v04.Image.model_validate(data)
    assert isinstance(result, v04.Image)


# ===============================================================================
# Additional comprehensive test cases for complete coverage
# ===============================================================================


def test_v04_axis_types() -> None:
    """Test all axis types and their properties."""
    # Test SpaceAxis with all valid units
    space_axis = v04.SpaceAxis(name="x", unit="micrometer")
    assert space_axis.name == "x"
    assert space_axis.type == "space"
    assert space_axis.unit == "micrometer"

    # Test SpaceAxis without unit
    space_axis_no_unit = v04.SpaceAxis(name="y")
    assert space_axis_no_unit.unit is None

    # Test TimeAxis with valid units
    time_axis = v04.TimeAxis(name="t", unit="second")
    assert time_axis.name == "t"
    assert time_axis.type == "time"
    assert time_axis.unit == "second"

    # Test ChannelAxis
    channel_axis = v04.ChannelAxis(name="c")
    assert channel_axis.name == "c"
    assert channel_axis.type == "channel"

    # Test CustomAxis with type
    custom_axis = v04.CustomAxis(name="custom", type="custom_type")
    assert custom_axis.name == "custom"
    assert custom_axis.type == "custom_type"

    # Test CustomAxis without type
    custom_axis_no_type = v04.CustomAxis(name="other")
    assert custom_axis_no_type.type is None


def test_v04_transformations() -> None:
    """Test transformation objects and their properties."""
    # Test ScaleTransformation
    scale = v04.ScaleTransformation(scale=[1.0, 2.0, 3.0])
    assert scale.type == "scale"
    assert scale.scale == [1.0, 2.0, 3.0]
    assert scale.ndim == 3

    # Test TranslationTransformation
    translation = v04.TranslationTransformation(translation=[10.0, 20.0])
    assert translation.type == "translation"
    assert translation.translation == [10.0, 20.0]
    assert translation.ndim == 2


def test_v04_dataset_model() -> None:
    """Test Dataset model directly."""
    dataset = v04.Dataset(
        path="level_0",
        coordinateTransformations=[
            v04.ScaleTransformation(scale=[1.0, 1.0]),
            v04.TranslationTransformation(translation=[0.0, 0.0]),
        ],
    )
    assert dataset.path == "level_0"
    assert len(dataset.coordinateTransformations) == 2
    assert isinstance(dataset.coordinateTransformations[0], v04.ScaleTransformation)
    assert isinstance(
        dataset.coordinateTransformations[1], v04.TranslationTransformation
    )


def test_v04_omero_models() -> None:
    """Test OMERO-related models directly."""
    # Test OmeroWindow
    window = v04.OmeroWindow(start=0.0, min=0.0, end=100.0, max=255.0)
    assert window.start == 0.0
    assert window.min == 0.0
    assert window.end == 100.0
    assert window.max == 255.0

    # Test OmeroChannel with all fields
    channel = v04.OmeroChannel(
        window=window, color="FF0000", label="Red", family="linear", active=True
    )
    assert channel.window == window
    assert channel.color == "FF0000"
    assert channel.label == "Red"
    assert channel.family == "linear"
    assert channel.active is True

    # Test OmeroChannel with minimal fields
    minimal_channel = v04.OmeroChannel(window=window, color="00FF00")
    assert minimal_channel.color == "00FF00"
    assert minimal_channel.label is None
    assert minimal_channel.family is None
    assert minimal_channel.active is None

    # Test Omero
    omero = v04.Omero(channels=[channel, minimal_channel])
    assert len(omero.channels) == 2


def test_v04_multiscale_with_global_transforms() -> None:
    """Test multiscale with global coordinate transformations."""
    data = {
        "multiscales": [
            {
                "name": "global_transform_test",
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]},
                    {"path": "1", "coordinateTransformations": [scale_tform(2)]},
                ],
                "coordinateTransformations": [
                    {"type": "scale", "scale": [0.1, 0.1]},
                    {"type": "translation", "translation": [100.0, 200.0]},
                ],
            }
        ]
    }

    img = v04.Image.model_validate(data)
    ms = img.multiscales[0]
    assert ms.coordinateTransformations is not None
    assert len(ms.coordinateTransformations) == 2
    assert ms.coordinateTransformations[0].type == "scale"
    assert ms.coordinateTransformations[1].type == "translation"


def test_v04_multiple_multiscales() -> None:
    """Test image with multiple multiscale entries."""
    data = {
        "multiscales": [
            {
                "name": "first",
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]}
                ],
            },
            {
                "name": "second",
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "1", "coordinateTransformations": [scale_tform(2)]}
                ],
            },
        ]
    }

    img = v04.Image.model_validate(data)
    assert len(img.multiscales) == 2
    assert img.multiscales[0].name == "first"
    assert img.multiscales[1].name == "second"


def test_v04_complex_omero_metadata() -> None:
    """Test complex OMERO metadata with multiple channels."""
    data = {
        "multiscales": [
            {
                "axes": [{"name": "c", "type": "channel"}, X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]}
                ],
            }
        ],
        "omero": {
            "channels": [
                {
                    "window": {"start": 0.0, "min": 0.0, "end": 100.0, "max": 255.0},
                    "color": "FF0000",
                    "label": "DAPI",
                    "family": "linear",
                    "active": True,
                },
                {
                    "window": {"start": 10.0, "min": 0.0, "end": 200.0, "max": 4095.0},
                    "color": "00FF00",
                    "label": "GFP",
                    "active": False,
                },
                {
                    "window": {"start": 5.0, "min": 0.0, "end": 150.0, "max": 1023.0},
                    "color": "0000FF",
                },
            ]
        },
    }

    img = v04.Image.model_validate(data)
    assert img.omero is not None
    assert len(img.omero.channels) == 3

    # Check first channel
    ch1 = img.omero.channels[0]
    assert ch1.color == "FF0000"
    assert ch1.label == "DAPI"
    assert ch1.family == "linear"
    assert ch1.active is True

    # Check second channel
    ch2 = img.omero.channels[1]
    assert ch2.color == "00FF00"
    assert ch2.label == "GFP"
    assert ch2.active is False
    assert ch2.family is None  # Not specified

    # Check third channel (minimal)
    ch3 = img.omero.channels[2]
    assert ch3.color == "0000FF"
    assert ch3.label is None
    assert ch3.active is None


def test_v04_transformation_validation_edge_cases() -> None:
    """Test edge cases in transformation validation."""
    # Multiple translation transforms (should fail)
    with pytest.raises(ValidationError, match="at most one translation transformation"):
        v04.Dataset(
            path="test",
            coordinateTransformations=[
                v04.ScaleTransformation(scale=[1.0, 1.0]),
                v04.TranslationTransformation(translation=[0.0, 0.0]),
                v04.TranslationTransformation(
                    translation=[10.0, 10.0]
                ),  # Second translation
            ],
        )

    # No scale transform (should fail)
    with pytest.raises(ValidationError, match="exactly one scale transformation"):
        v04.Dataset(
            path="test",
            coordinateTransformations=[
                v04.TranslationTransformation(translation=[0.0, 0.0])
            ],
        )

    # Empty transformations list (should fail)
    with pytest.raises(ValidationError):
        v04.Dataset(path="test", coordinateTransformations=[])


def test_v04_datasets_validation() -> None:
    """Test dataset list validation edge cases."""
    # Datasets with different dimensions (should fail)
    with pytest.raises(ValidationError, match="same number of dimensions"):
        data = {
            "multiscales": [
                {
                    "axes": [X_AXIS, Y_AXIS],
                    "datasets": [
                        {"path": "0", "coordinateTransformations": [scale_tform(2)]},
                        {
                            "path": "1",
                            "coordinateTransformations": [scale_tform(3)],
                        },  # Different dims
                    ],
                }
            ]
        }
        v04.Image.model_validate(data)

    # More than 5 dimensions (should fail)
    with pytest.raises(ValidationError, match="not have more than 5 dimensions"):
        data = {
            "multiscales": [
                {
                    "axes": [
                        {"name": "t", "type": "time"},
                        {"name": "c", "type": "channel"},
                        {"name": "z", "type": "space"},
                        {"name": "y", "type": "space"},
                        {"name": "x", "type": "space"},
                        {"name": "extra", "type": "space"},  # 6 dimensions
                    ],
                    "datasets": [
                        {"path": "0", "coordinateTransformations": [scale_tform(6)]}
                    ],
                }
            ]
        }
        v04.Image.model_validate(data)


def test_v04_global_transform_dimension_mismatch() -> None:
    """Test validation of global coordinate transformations dimension matching."""
    # Global transform dimensions don't match axes
    with pytest.raises(ValidationError, match="does not match the number of axes"):
        data = {
            "multiscales": [
                {
                    "axes": [X_AXIS, Y_AXIS],  # 2D
                    "datasets": [
                        {"path": "0", "coordinateTransformations": [scale_tform(2)]}
                    ],
                    "coordinateTransformations": [scale_tform(3)],  # 3D transform
                }
            ]
        }
        v04.Image.model_validate(data)


def test_v04_minimal_valid_image() -> None:
    """Test the most minimal valid v04 image."""
    data = {
        "multiscales": [
            {
                "axes": [
                    {"name": "y", "type": "space"},
                    {"name": "x", "type": "space"},
                ],
                "datasets": [
                    {
                        "path": "0",
                        "coordinateTransformations": [
                            {"type": "scale", "scale": [1.0, 1.0]}
                        ],
                    }
                ],
            }
        ]
    }
    img = v04.Image.model_validate(data)
    assert len(img.multiscales) == 1
    assert len(img.multiscales[0].axes) == 2
    assert len(img.multiscales[0].datasets) == 1
    assert img.omero is None


def test_v04_axis_name_uniqueness() -> None:
    """Test that axis names must be unique."""
    with pytest.raises(ValidationError, match="List items are not unique"):
        data = {
            "multiscales": [
                {
                    "axes": [
                        {"name": "x", "type": "space"},
                        {"name": "x", "type": "space"},  # Duplicate name
                    ],
                    "datasets": [
                        {"path": "0", "coordinateTransformations": [scale_tform(2)]}
                    ],
                }
            ]
        }
        v04.Image.model_validate(data)


def test_v04_axis_name_uniqueness_custom_validation() -> None:
    """Test that axis names must be unique - triggers custom validation logic."""
    # Import the validation function directly to test it
    from yaozarrs.v04._image import _validate_axes_list

    # Create axes with same names but different types to bypass UniqueList
    axes = [
        v04.SpaceAxis(name="duplicate"),
        v04.TimeAxis(name="duplicate"),  # Same name, different types
        v04.SpaceAxis(name="y"),
    ]

    # This should trigger our custom validation at lines 45-46
    with pytest.raises(
        ValueError, match=r"Axis names must be unique\. Found duplicates"
    ):
        _validate_axes_list(axes)


def test_v04_space_units() -> None:
    """Test various space units are accepted."""
    space_units = ["micrometer", "millimeter", "meter", "nanometer", "inch", "foot"]

    for unit in space_units:
        axis = v04.SpaceAxis(name="test", unit=unit)
        assert axis.unit == unit

        data = {
            "multiscales": [
                {
                    "axes": [
                        {"name": "y", "type": "space", "unit": unit},
                        {"name": "x", "type": "space", "unit": unit},
                    ],
                    "datasets": [
                        {"path": "0", "coordinateTransformations": [scale_tform(2)]}
                    ],
                }
            ]
        }
        img = v04.Image.model_validate(data)
        assert img.multiscales[0].axes[0].unit == unit


def test_v04_time_units() -> None:
    """Test various time units are accepted."""
    time_units = ["second", "millisecond", "microsecond", "minute", "hour", "day"]

    for unit in time_units:
        axis = v04.TimeAxis(name="t", unit=unit)
        assert axis.unit == unit

        data = {
            "multiscales": [
                {
                    "axes": [
                        {"name": "t", "type": "time", "unit": unit},
                        {"name": "y", "type": "space"},
                        {"name": "x", "type": "space"},
                    ],
                    "datasets": [
                        {"path": "0", "coordinateTransformations": [scale_tform(3)]}
                    ],
                }
            ]
        }
        img = v04.Image.model_validate(data)
        assert img.multiscales[0].axes[0].unit == unit


def test_v04_version_field_variations() -> None:
    """Test version field in various contexts."""
    # Version in multiscale
    data = {
        "multiscales": [
            {
                "version": "0.4",
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]}
                ],
            }
        ]
    }
    img = v04.Image.model_validate(data)
    assert img.multiscales[0].version == "0.4"

    # No version field (should still work)
    data_no_version = {
        "multiscales": [
            {
                "axes": [X_AXIS, Y_AXIS],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(2)]}
                ],
            }
        ]
    }
    img_no_version = v04.Image.model_validate(data_no_version)
    assert img_no_version.multiscales[0].version == "0.4"


def test_v04_transformation_minimal_dimensions() -> None:
    """Test transformations with minimal dimensions (2D)."""
    # Scale with minimum 2 dimensions
    scale_2d = v04.ScaleTransformation(scale=[1.0, 2.0])
    assert scale_2d.ndim == 2

    # Translation with minimum 2 dimensions
    translation_2d = v04.TranslationTransformation(translation=[10.0, 20.0])
    assert translation_2d.ndim == 2

    # Test with 1D should fail (below minimum)
    with pytest.raises(ValidationError):
        v04.ScaleTransformation(scale=[1.0])

    with pytest.raises(ValidationError):
        v04.TranslationTransformation(translation=[10.0])


def test_v04_custom_axis_validation() -> None:
    """Test custom axis validation."""
    # Custom axis with custom type
    data_custom_type = {
        "multiscales": [
            {
                "axes": [
                    {"name": "wavelength", "type": "spectral"},
                    {"name": "y", "type": "space"},
                    {"name": "x", "type": "space"},
                ],
                "datasets": [
                    {"path": "0", "coordinateTransformations": [scale_tform(3)]}
                ],
            }
        ]
    }
    img_custom = v04.Image.model_validate(data_custom_type)
    assert img_custom.multiscales[0].axes[0].type == "spectral"

    # Test direct CustomAxis creation
    custom_axis = v04.CustomAxis(name="custom", type="spectral")
    assert custom_axis.name == "custom"
    assert custom_axis.type == "spectral"

    # Test CustomAxis with no type
    custom_axis_no_type = v04.CustomAxis(name="other")
    assert custom_axis_no_type.type is None


def test_v04_large_multiscale_pyramid() -> None:
    """Test a large multiscale pyramid with many resolution levels."""
    datasets = []
    for i in range(10):  # 10 resolution levels
        datasets.append(
            {
                "path": str(i),
                "coordinateTransformations": [
                    {"type": "scale", "scale": [2.0**i, 2.0**i]}
                ],
            }
        )

    data = {
        "multiscales": [
            {
                "name": "large_pyramid",
                "axes": [X_AXIS, Y_AXIS],
                "datasets": datasets,
            }
        ]
    }

    img = v04.Image.model_validate(data)
    assert len(img.multiscales[0].datasets) == 10
    assert img.multiscales[0].name == "large_pyramid"
    # Check that scale factors increase correctly
    scale_0 = img.multiscales[0].datasets[0].coordinateTransformations[0]
    scale_5 = img.multiscales[0].datasets[5].coordinateTransformations[0]
    assert isinstance(scale_0, v04.ScaleTransformation)
    assert isinstance(scale_5, v04.ScaleTransformation)
    assert scale_0.scale == [1.0, 1.0]
    assert scale_5.scale == [32.0, 32.0]
