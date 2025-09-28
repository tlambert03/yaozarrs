from pathlib import Path

import pytest

from yaozarrs import from_uri, v04, v05

DATA = Path(__file__).parent / "data"
V05_DATA = DATA / "v05"


@pytest.mark.parametrize(
    "uri,expected_type",
    [
        (
            "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.5/idr0062A/6001240_labels.zarr",
            v05.Image,
        ),
        (V05_DATA / "6001240_labels.zarr", v05.Image),
        (
            "https://uk1s3.embassy.ebi.ac.uk/idr/share/ome2024-ngff-challenge/idr0010/76-45.zarr",
            v05.Plate,
        ),
        (
            V05_DATA / "76-45.ome.zarr",
            v05.Plate,
        ),
        (
            "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr",
            v04.Image,
        ),
    ],
)
def test_from_uri(uri: str, expected_type: type) -> None:
    try:
        obj = from_uri(uri)
    except FileNotFoundError as e:
        pytest.xfail(reason=f"Internet down?: {e}")
        return

    if isinstance(obj, v05.OMEZarrGroupJSON):
        # in v05, the ome info is inside the doc['attributes']['ome'] key
        assert isinstance(obj.attributes.ome, expected_type)
        assert obj.uri.endswith("zarr.json")
    else:
        # in v04, the document is itself the ome model
        assert isinstance(obj, v04.OMEZarrGroupJSON)
        assert isinstance(obj, expected_type)
