import pytest
from pydantic import ValidationError
from yaozarrs import v04

V04_VALID_PLATES = [
    # Simple plate with minimal required fields
    {
        "plate": {
            "rows": [{"name": "A"}, {"name": "B"}],
            "columns": [{"name": "1"}, {"name": "2"}],
            "wells": [
                {"path": "A/1", "rowIndex": 0, "columnIndex": 0},
                {"path": "A/2", "rowIndex": 0, "columnIndex": 1},
                {"path": "B/1", "rowIndex": 1, "columnIndex": 0},
            ],
        }
    },
    # Plate with all optional fields
    {
        "plate": {
            "version": "0.4",
            "name": "Test Plate",
            "field_count": 4,
            "rows": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
            "columns": [{"name": "01"}, {"name": "02"}, {"name": "03"}],
            "wells": [
                {"path": "A/01", "rowIndex": 0, "columnIndex": 0},
                {"path": "B/02", "rowIndex": 1, "columnIndex": 1},
                {"path": "C/03", "rowIndex": 2, "columnIndex": 2},
            ],
            "acquisitions": [
                {
                    "id": 0,
                    "name": "First acquisition",
                    "description": "Initial imaging run",
                    "maximumfieldcount": 4,
                    "starttime": 1234567890,
                    "endtime": 1234567950,
                },
                {
                    "id": 1,
                    "name": "Second acquisition",
                    "maximumfieldcount": 2,
                },
            ],
        }
    },
    # Plate with acquisition without optional fields
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
            "acquisitions": [{"id": 0}],  # Just required id field
        }
    },
]


V04_INVALID_PLATES = [
    # Missing plate key
    {},
    # Empty plate
    {"plate": {}},
    # Missing rows
    {
        "plate": {
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
        }
    },
    # Missing columns
    {
        "plate": {
            "rows": [{"name": "A"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
        }
    },
    # Missing wells
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
        }
    },
    # Empty rows array
    {
        "plate": {
            "rows": [],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
        }
    },
    # Empty columns array
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
        }
    },
    # Empty wells array
    {"plate": {"rows": [{"name": "A"}], "columns": [{"name": "1"}], "wells": []}},
    # Invalid well path pattern
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [
                {"path": "A-1", "rowIndex": 0, "columnIndex": 0}
            ],  # Should be A/1
        }
    },
    # Invalid row name pattern (contains special chars)
    {
        "plate": {
            "rows": [{"name": "A@"}],  # Invalid pattern
            "columns": [{"name": "1"}],
            "wells": [{"path": "A@/1", "rowIndex": 0, "columnIndex": 0}],
        }
    },
    # Invalid column name pattern
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1@"}],  # Invalid pattern
            "wells": [{"path": "A/1@", "rowIndex": 0, "columnIndex": 0}],
        }
    },
    # Well rowIndex out of bounds
    {
        "plate": {
            "rows": [{"name": "A"}],  # Only 1 row (index 0)
            "columns": [{"name": "1"}],
            "wells": [
                {"path": "A/1", "rowIndex": 1, "columnIndex": 0}
            ],  # Index 1 doesn't exist
        }
    },
    # Well columnIndex out of bounds
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],  # Only 1 column (index 0)
            "wells": [
                {"path": "A/1", "rowIndex": 0, "columnIndex": 1}
            ],  # Index 1 doesn't exist
        }
    },
    # Negative rowIndex
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": -1, "columnIndex": 0}],
        }
    },
    # Negative columnIndex
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": -1}],
        }
    },
    # Invalid field_count (must be positive)
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
            "field_count": 0,  # Must be > 0
        }
    },
    # Invalid acquisition id (negative)
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
            "acquisitions": [{"id": -1}],
        }
    },
    # Invalid maximumfieldcount (must be positive)
    {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
            "acquisitions": [{"id": 0, "maximumfieldcount": 0}],  # Must be > 0
        }
    },
]


@pytest.mark.parametrize("data", V04_VALID_PLATES)
def test_valid_v04_plates(data):
    """Test that valid v04 plate metadata can be parsed."""
    plate = v04.Plate.model_validate(data)
    assert plate.plate is not None
    assert len(plate.plate.rows) >= 1
    assert len(plate.plate.columns) >= 1
    assert len(plate.plate.wells) >= 1


@pytest.mark.parametrize("data", V04_INVALID_PLATES)
def test_invalid_v04_plates(data):
    """Test that invalid v04 plate metadata raises validation errors."""
    with pytest.raises(ValidationError):
        v04.Plate.model_validate(data)


def test_v04_plate_acquisition():
    """Test v04 plate acquisition model."""
    acq = v04.Acquisition(
        id=42,
        name="Test Acquisition",
        description="Test description",
        maximumfieldcount=10,
        starttime=1234567890,
        endtime=1234567950,
    )

    assert acq.id == 42
    assert acq.name == "Test Acquisition"
    assert acq.description == "Test description"
    assert acq.maximumfieldcount == 10
    assert acq.starttime == 1234567890
    assert acq.endtime == 1234567950


def test_v04_plate_row_column():
    """Test v04 plate row and column models."""
    row = v04.Row(name="A")
    assert row.name == "A"

    column = v04.Column(name="01")
    assert column.name == "01"


def test_v04_plate_well():
    """Test v04 plate well model."""
    well = v04.PlateWell(path="A/01", rowIndex=0, columnIndex=0)
    assert well.path == "A/01"
    assert well.rowIndex == 0
    assert well.columnIndex == 0


def test_v04_plate_def_validation():
    """Test v04 plate def validation logic."""
    # Test valid plate def
    plate_def = v04.PlateDef(
        rows=[v04.Row(name="A"), v04.Row(name="B")],
        columns=[v04.Column(name="1"), v04.Column(name="2")],
        wells=[
            v04.PlateWell(path="A/1", rowIndex=0, columnIndex=0),
            v04.PlateWell(path="B/2", rowIndex=1, columnIndex=1),
        ],
    )
    assert len(plate_def.rows) == 2
    assert len(plate_def.columns) == 2

    # Test that validation catches out-of-bounds indices
    with pytest.raises(ValidationError, match=r"rowIndex.*but only.*rows exist"):
        v04.PlateDef(
            rows=[v04.Row(name="A")],  # Only 1 row
            columns=[v04.Column(name="1")],
            wells=[
                v04.PlateWell(path="A/1", rowIndex=1, columnIndex=0)
            ],  # rowIndex=1 invalid
        )

    with pytest.raises(ValidationError, match=r"columnIndex.*but only.*columns exist"):
        v04.PlateDef(
            rows=[v04.Row(name="A")],
            columns=[v04.Column(name="1")],  # Only 1 column
            wells=[
                v04.PlateWell(path="A/1", rowIndex=0, columnIndex=1)
            ],  # columnIndex=1 invalid
        )


def test_v04_validate_plate_as_ome_node():
    """Test that v04 plates can be validated as OME nodes."""
    data = {
        "plate": {
            "rows": [{"name": "A"}],
            "columns": [{"name": "1"}],
            "wells": [{"path": "A/1", "rowIndex": 0, "columnIndex": 0}],
        }
    }

    # Should validate as a Plate
    result = v04.Plate.model_validate(data)
    assert isinstance(result, v04.Plate)
