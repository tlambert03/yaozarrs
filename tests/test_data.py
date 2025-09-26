import json
from pathlib import Path

import pytest
from yaozarrs import OMEZarr

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

    # FIXME:
    # we shouldn't have to do by_alias=True here...
    # but it's required for pydantic <2.10.0
    js = obj.model_dump_json(by_alias=True)
    obj2 = OMEZarr.model_validate_json(js)
    assert obj == obj2
