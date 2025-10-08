"""A .zattrs document found in any ome-zarr v0.4 group.

https://ngff.openmicroscopy.org/0.4/

Here are ALL the possible .zattrs documents you might encounter with OME v0.4 metadata:

1. Image Group

Discovery: Self-contained, resolution levels in datasets paths
my_image/
├── .zattrs            # ← Contains THIS metadata
├── 0/
├── 1/
└── labels/
    ├── .zattrs        # Lists available labels
    └── ...

{
  "multiscales": [
    {
      "version": "0.4",
      "name": "example_image",
      "axes": [
        {"name": "t", "type": "time", "unit": "millisecond"},
        {"name": "c", "type": "channel"},
        {"name": "z", "type": "space", "unit": "micrometer"},
        {"name": "y", "type": "space", "unit": "micrometer"},
        {"name": "x", "type": "space", "unit": "micrometer"}
      ],
      "datasets": [
        {
          "path": "0",
          "coordinateTransformations": [
            {
              "type": "scale",
              "scale": [1.0, 1.0, 0.5, 0.5, 0.5]
            }
          ]
        }
      ],
      "type": "gaussian"
    }
  ],
  "omero": {
    "version": "0.4",
    "channels": [
      {
        "color": "0000FF",
        "label": "DAPI",
        "window": {
          "min": 0,
          "max": 255,
          "start": 0,
          "end": 255
        }
      }
    ]
  }
}

2. Plate Group

Discovery: Wells listed explicitly in wells array
my_plate/
├── .zattrs            # ← Contains THIS metadata
├── A/
│   ├── 1/
│   │   ├── .zattrs    # Well metadata
│   │   ├── 0/         # Field 0
│   │   └── 1/         # Field 1
│   └── 2/
└── B/
    └── 1/

{
  "plate": {
    "version": "0.4",
    "name": "experiment_001",
    "columns": [
      {"name": "1"},
      {"name": "2"}
    ],
    "rows": [
      {"name": "A"},
      {"name": "B"}
    ],
    "wells": [
      {
        "path": "A/1",
        "rowIndex": 0,
        "columnIndex": 0
      },
      {
        "path": "B/1",
        "rowIndex": 1,
        "columnIndex": 0
      }
    ],
    "acquisitions": [
      {
        "id": 1,
        "maximumfieldcount": 2,
        "name": "initial_scan"
      }
    ],
    "field_count": 4
  }
}

3. Well Group

Discovery: Images listed explicitly in images array
my_plate/A/1/
├── .zattrs            # ← Contains THIS metadata
├── 0/                 # Field/image 0
│   ├── .zattrs        # Image metadata
│   ├── 0/             # Resolution level
│   └── 1/
└── 1/                 # Field/image 1
    └── ...

{
  "well": {
    "version": "0.4",
    "images": [
      {
        "path": "0",
        "acquisition": 1
      },
      {
        "path": "1",
        "acquisition": 1
      }
    ]
  }
}

4. Labels Index Group

Discovery: Must explore filesystem for labels/ directories
my_image/
├── .zattrs            # Image metadata
├── 0/
└── labels/
    ├── .zattrs        # ← Contains THIS metadata
    ├── cell_seg/
    │   ├── .zattrs    # Label image metadata
    │   └── 0/
    └── nuclei_seg/
        └── ...

{
  "labels": ["cell_segmentation", "nuclei_segmentation"]
}

5. Label Image Group

Discovery: Listed in parent labels group's labels array
my_image/labels/cell_segmentation/
├── .zattrs            # ← Contains THIS metadata
├── 0/                 # Resolution level 0
└── 1/                 # Resolution level 1

{
  "multiscales": [
    {
      "version": "0.4",
      "axes": [
        {"name": "z", "type": "space", "unit": "micrometer"},
        {"name": "y", "type": "space", "unit": "micrometer"},
        {"name": "x", "type": "space", "unit": "micrometer"}
      ],
      "datasets": [
        {
          "path": "0",
          "coordinateTransformations": [
            {"type": "scale", "scale": [0.5, 0.5, 0.5]}
          ]
        }
      ]
    }
  ],
  "image-label": {
    "version": "0.4",
    "colors": [
      {
        "label-value": 1,
        "rgba": [255, 0, 0, 128]
      }
    ],
    "properties": [
      {
        "label-value": 1,
        "cell_type": "neuron",
        "area": 1250.5
      }
    ],
    "source": {
      "image": "../../"
    }
  }
}

6. Bioformats2raw Collection Group

Discovery: Must explore numbered directories (0/, 1/, 2/, etc.)
converted_file/
├── .zattrs            # ← Contains THIS metadata
├── 0/                 # First image (by convention)
│   └── .zattrs        # Image metadata
├── 1/                 # Second image (by convention)
│   └── .zattrs
├── 2/                 # Third image (by convention)
│   └── .zattrs
└── OME/
    └── METADATA.ome.xml

{
  "bioformats2raw.layout": 3
}
"""

from typing import Annotated, Any, TypeAlias

from pydantic import BaseModel, Discriminator, Tag

from ._bf2raw import Bf2Raw
from ._image import Image
from ._label import LabelImage, LabelsGroup
from ._plate import Plate
from ._series import Series
from ._well import Well


def _discriminate_ome_v04_metadata(v: Any) -> str | None:
    if isinstance(v, dict):
        if "image-label" in v:
            return "label-image"
        if "multiscales" in v:
            return "image"
        if "plate" in v:
            return "plate"
        if "bioformats2raw.layout" in v or "bioformats2raw_layout" in v:
            return "bf2raw"
        if "well" in v:
            return "well"
        if "labels" in v:
            return "labels-group"
        if "series" in v:
            return "series"
    elif isinstance(v, BaseModel):
        if isinstance(v, LabelImage):
            return "label-image"
        if isinstance(v, Image):
            return "image"
        if isinstance(v, Plate):
            return "plate"
        if isinstance(v, Bf2Raw):
            return "bf2raw"
        if isinstance(v, Well):
            return "well"
        if isinstance(v, LabelsGroup):
            return "labels-group"
        if isinstance(v, Series):  # pragma: no cover
            return "series"
    return None


# NOTE:
# these are ALL also ZarrGroupModels (i.e. have a "uri" attribute)
OMEZarrGroupJSON: TypeAlias = Annotated[
    (
        Annotated[LabelImage, Tag("label-image")]
        | Annotated[Image, Tag("image")]
        | Annotated[Plate, Tag("plate")]
        | Annotated[Bf2Raw, Tag("bf2raw")]
        | Annotated[Well, Tag("well")]
        | Annotated[LabelsGroup, Tag("labels-group")]
        | Annotated[Series, Tag("series")]
    ),
    Discriminator(_discriminate_ome_v04_metadata),
]
"""A .zattrs document found in any ome-zarr group.

OME-ZARR v0.4 uses zarr format version 2:
https://zarr-specs.readthedocs.io/en/latest/v2/v2.0.html

...where the node-type is defined by the presence of a .zgroup or .zarray file.
Either node type may also contain a .zattrs file, and that's where the OME metadata
lives, without any top-level key.
"""
