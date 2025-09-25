import json
from pathlib import Path

import pytest

from yaomem import OMEZarr

DATA = Path(__file__).parent / "data"
ZARR_JSONS = sorted(DATA.rglob("zarr.json"))
OME_ATTRS: dict[str, dict] = {
    str(path.parent.relative_to(DATA)): data["attributes"]
    for path in ZARR_JSONS
    if isinstance(data := json.loads(path.read_text()), dict)
    and "ome" in data.get("attributes", {})
}


@pytest.mark.parametrize("attrs", OME_ATTRS.values(), ids=OME_ATTRS.keys())
def test_data(attrs: dict) -> None:
    obj = OMEZarr.model_validate(attrs)

    js = obj.model_dump_json()
    obj2 = OMEZarr.model_validate_json(js)

    assert obj == obj2
