"""Storage validation for OME-ZARR v0.6 hierarchies.

This module provides functions to validate that OME-ZARR v0.6 storage structures
conform to the specification requirements for directory layout, file existence,
and metadata consistency.
"""

from __future__ import annotations

import posixpath
import warnings
from collections import defaultdict
from dataclasses import dataclass
from itertools import chain, product
from typing import TypeAlias

from yaozarrs._storage import StorageErrorType, ValidationResult
from yaozarrs._validate import validate_ome_object, validate_ome_uri
from yaozarrs._zarr import ZarrArray, ZarrGroup
from yaozarrs.v06._bf2raw import Bf2Raw, Series
from yaozarrs.v06._image import Image, Multiscale
from yaozarrs.v06._labels import LabelImage, LabelsGroup
from yaozarrs.v06._plate import Plate, Well
from yaozarrs.v06._scene import Scene
from yaozarrs.v06._transforms import (
    AffineTransformation,
    BijectionTransformation,
    ByDimensionTransformation,
    CoordinatesTransformation,
    DisplacementsTransformation,
    InputOutput,
    RotationTransformation,
    SequenceTransformation,
    Transformation,
)
from yaozarrs.v06._version import CURRENT_VERSION
from yaozarrs.v06._zarr_json import OMEAttributes, OMEZarrGroupJSON

# ----------------------------------------------------------
# VALIDATORS
# ----------------------------------------------------------

Loc: TypeAlias = tuple[int | str, ...]


def _build_fs_path(zarr_group: ZarrGroup, relative_path: str = "") -> str:
    """Build a filesystem path for error reporting.

    Parameters
    ----------
    zarr_group : ZarrGroup
        The zarr group to build the path from.
    relative_path : str
        Optional relative path from the group (e.g., "A/1/0").

    Returns
    -------
    str
        A human-readable filesystem path (e.g., "plate.zarr/A/1/0").
    """
    # Get the base path from the group
    base = zarr_group.path or ""

    # Combine with relative path
    if relative_path:
        full_path = f"{base}/{relative_path}" if base else relative_path
    else:
        full_path = base

    # Try to get a readable store name (without protocol)
    store_path = zarr_group.store_path
    # Remove protocol prefix for readability (file://, https://, etc.)
    for prefix in ("file://", "https://", "http://", "s3://"):
        if store_path.startswith(prefix):
            store_path = store_path[len(prefix) :]
            break

    # Get just the store root name
    if full_path:
        # Extract just the zarr store name from the beginning of full store path
        # e.g., "/tmp/foo/plate.zarr/A/1" -> "plate.zarr/A/1"
        parts = store_path.rstrip("/").split("/")
        for _i, part in enumerate(parts):
            if part.endswith(".zarr") or part.endswith(".zarr/"):
                store_name = part.rstrip("/")
                return f"{store_name}/{full_path}"

    # Fall back to just returning the path
    return full_path or store_path.split("/")[-1]


@dataclass
class LabelsCheckResult:
    """Result of checking for a labels group."""

    result: ValidationResult
    labels_info: tuple[ZarrGroup, LabelsGroup] | None = None


class StorageValidatorV06:
    """Concrete implementation of storage validator. for OME-ZARR v0.6 spec."""

    __slots__ = ("_root_version",)

    @classmethod
    def validate_group(
        cls, zarr_group: ZarrGroup, attrs_model: OMEAttributes | None = None
    ) -> ValidationResult:
        """Entry point that dispatches to appropriate visitor method.

        Parameters
        ----------
        zarr_group : ZarrGroup
            The zarr group to validate.
        attrs_model : OMEAttributes
            The validated OME attributes model.

        Returns
        -------
        ValidationResult
            The validation result containing any errors found.
        """
        if attrs_model is None:
            # extract the model from the zarr attributes
            attrs_model = validate_ome_object(zarr_group.attrs, OMEAttributes)

        validator = cls()
        ome_metadata = attrs_model.ome
        loc_prefix = ("ome",)
        # The version declared at the root of this hierarchy. Children are
        # force-parsed against this same version (not a hardcoded literal), and
        # checked for consistency against it (spec index.md: "the OME-Zarr
        # version MUST be consistent within a hierarchy").
        validator._root_version = getattr(ome_metadata, "version", CURRENT_VERSION)

        # Dispatch to appropriate visitor method based on metadata type
        if isinstance(ome_metadata, LabelImage):
            return validator.visit_label_image(zarr_group, ome_metadata, loc_prefix)
        elif isinstance(ome_metadata, Image):
            return validator.visit_image(zarr_group, ome_metadata, loc_prefix)
        elif isinstance(ome_metadata, LabelsGroup):
            return validator.visit_labels_group(zarr_group, ome_metadata, loc_prefix)
        elif isinstance(ome_metadata, Plate):
            return validator.visit_plate(zarr_group, ome_metadata, loc_prefix)
        elif isinstance(ome_metadata, Well):
            return validator.visit_well(zarr_group, ome_metadata, loc_prefix)
        elif isinstance(ome_metadata, Bf2Raw):
            return validator.visit_bioformats2raw(zarr_group, ome_metadata, loc_prefix)
        elif isinstance(ome_metadata, Series):  # pragma: no cover
            return validator.visit_series(zarr_group, ome_metadata, loc_prefix)
        elif isinstance(ome_metadata, Scene):
            return validator.visit_scene(zarr_group, ome_metadata, loc_prefix)
        else:
            raise NotImplementedError(
                f"Unknown OME metadata type: {type(ome_metadata).__name__}"
            )

    def _child_metadata(
        self, child_group: ZarrGroup, loc: Loc, result: ValidationResult
    ) -> object:
        """Force-parse a child group's OME metadata as v0.6, checking version.

        Uses the hierarchy's root version (not a hardcoded literal) to parse the
        child, and records a `version_mismatch` error if the child's own
        declared version differs (spec: version MUST be consistent within a
        hierarchy). Returns either the parsed metadata object, or the
        `ValueError` raised while parsing (so callers can report either an
        `isinstance` mismatch or the underlying error).
        """
        declared = dict(child_group.attrs).get("ome", {})
        declared_version = (
            declared.get("version") if isinstance(declared, dict) else None
        )
        if declared_version is not None and declared_version != self._root_version:
            result.add_error(
                StorageErrorType.version_mismatch,
                loc,
                f"Group has version {declared_version!r}, but the root of this "
                f"hierarchy declares version {self._root_version!r}. The "
                "OME-Zarr version MUST be consistent within a hierarchy.",
                ctx={"declared": declared_version, "root": self._root_version},
            )
        try:
            return child_group.ome_metadata(version=self._root_version)
        except ValueError as e:
            return e

    def visit_label_image(
        self, zarr_group: ZarrGroup, label_image_model: LabelImage, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate a LabelImage group."""
        result = ValidationResult()

        # The value of the source key MUST be a JSON object containing information
        # about the original image from which the label image derives. This object
        # MAY include a key image, whose value MUST be a string specifying the
        # relative path to a Zarr image group.
        src = label_image_model.image_label.source
        if src is not None and (src_img := src.image) is not None:
            result = result.merge(
                self._validate_labels_image_source(zarr_group, src_img, loc_prefix)
            )

        # For label images, validate integer data types
        result = result.merge(
            self._validate_label_data_types(label_image_model, zarr_group, loc_prefix)
        )

        return result

    def visit_image(
        self, zarr_group: ZarrGroup, image_model: Image, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate an image group with multiscales metadata."""
        result = ValidationResult()

        # Collect all children we'll need to check and prefetch them in one batch
        children_to_prefetch = []
        for multiscale in image_model.multiscales:
            children_to_prefetch.extend(ds.path for ds in multiscale.datasets)
        # Also check for labels group
        children_to_prefetch.append("labels")
        zarr_group.prefetch_children(children_to_prefetch)

        # Validate each multiscale
        for ms_idx, multiscale in enumerate(image_model.multiscales):
            ms_loc = (*loc_prefix, "multiscales", ms_idx)
            # Note: datasets already prefetched above, no need to prefetch again
            result = result.merge(
                self._visit_multiscale_no_prefetch(zarr_group, multiscale, ms_loc)
            )
            # v0.6: additional transformations may reference on-disk arrays
            # (affine/rotation matrices, displacement/coordinate fields) and
            # coordinate systems in child labels groups.
            result = result.merge(
                self._visit_multiscale_transforms(zarr_group, multiscale, ms_loc)
            )

        # Check whether this image has a labels group, and validate if so
        lbls_check = self._check_for_labels_group(zarr_group, loc_prefix)
        result = result.merge(lbls_check.result)

        if lbls_check.labels_info is not None:
            labels_group, labels_model = lbls_check.labels_info
            result = result.merge(
                self.visit_labels_group(
                    labels_group,
                    labels_model,
                    (*loc_prefix, "labels"),
                    image_model,
                )
            )

        return result

    def visit_labels_group(
        self,
        labels_group: ZarrGroup,
        labels_model: LabelsGroup,
        loc_prefix: Loc,
        parent_image_model: Image | None = None,
    ) -> ValidationResult:
        """Validate a labels group and its referenced label images."""
        result = ValidationResult()

        # Prefetch all label metadata in a single batch request for performance
        labels_group.prefetch_children(labels_model.labels)

        # Validate each label path exists and is valid LabelImage
        for label_idx, label_path in enumerate(labels_model.labels):
            label_loc = (*loc_prefix, "labels", label_idx)

            if label_path not in labels_group:
                result.add_error(
                    StorageErrorType.label_path_not_found,
                    label_loc,
                    f"Label path '{label_path}' not found in labels group",
                    ctx={
                        "fs_path": _build_fs_path(labels_group, label_path),
                        "expected": "zarr group",
                    },
                )
                continue

            # Intermediate groups between `labels` and the images within it are
            # allowed, but these MUST NOT contain metadata.
            parts = label_path.split("/")
            for depth in range(1, len(parts)):
                inter_path = "/".join(parts[:depth])
                inter = labels_group.get(inter_path)
                if isinstance(inter, ZarrGroup) and "ome" in dict(inter.attrs):
                    result.add_error(
                        StorageErrorType.labels_intermediate_metadata,
                        label_loc,
                        f"Intermediate group '{inter_path}' between the labels "
                        "group and its label images must not contain OME "
                        "metadata",
                        ctx={"fs_path": _build_fs_path(labels_group, inter_path)},
                    )

            label_group = labels_group[label_path]
            if not isinstance(label_group, ZarrGroup):
                result.add_error(
                    StorageErrorType.label_path_not_group,
                    label_loc,
                    f"Label path '{label_path}' is not a zarr group",
                    ctx={
                        "fs_path": _build_fs_path(labels_group, label_path),
                        "expected": "group",
                        "found": "array",
                    },
                )
                continue

            # Validate as LabelImage
            label_image_model = self._child_metadata(label_group, label_loc, result)
            if not isinstance(label_image_model, Image):
                ctx: dict = {"path": label_path}
                if isinstance(label_image_model, Exception):
                    ctx["error"] = label_image_model
                else:
                    ctx["type"] = type(label_image_model).__name__
                result.add_error(
                    StorageErrorType.label_image_invalid,
                    label_loc,
                    f"Label path '{label_path}' does not contain "
                    "valid Image ('multiscales') metadata",
                    ctx=ctx,
                )
                continue

            # Within the multiscales object, the JSON array associated with the
            # datasets key MUST have the same number of entries (scale levels) as
            # the original unlabeled image.
            # (NB: the spec constrains the *dataset* counts, not the number of
            # multiscales objects, so mismatched multiscales counts are allowed
            # and any extras are simply not compared.)
            if parent_image_model is not None:
                for ms_idx, (lbl_ms, img_ms) in enumerate(
                    zip(label_image_model.multiscales, parent_image_model.multiscales)
                ):
                    n_lbl_ds = len(lbl_ms.datasets)
                    n_img_ds = len(img_ms.datasets)
                    # spec: the label image MUST have the *same* number of
                    # entries (scale levels) as the original unlabeled image.
                    if n_lbl_ds != n_img_ds:
                        result.add_error(
                            StorageErrorType.label_dataset_count_mismatch,
                            (*label_loc, "multiscales", ms_idx),
                            f"Label image '{label_path}' multiscale index {ms_idx} "
                            f"has {n_lbl_ds} datasets, but parent image multiscale "
                            f"index {ms_idx} has {n_img_ds}",
                            ctx={
                                "label_path": label_path,
                                "multiscale_index": ms_idx,
                                "label_datasets": n_lbl_ds,
                                "parent_datasets": n_img_ds,
                            },
                        )

            if isinstance(label_image_model, LabelImage):
                # Recursively validate the label image
                result = result.merge(
                    self.visit_label_image(label_group, label_image_model, label_loc)
                )
            else:
                result.add_warning(
                    StorageErrorType.label_image_invalid,
                    label_loc,
                    f"Label path '{label_path}' contains Image metadata, "
                    "but is not a LabelImage (SHOULD contain 'image-label' metadata)",
                    ctx={"path": label_path, "type": type(label_image_model).__name__},
                )

        return result

    def _visit_multiscale_no_prefetch(
        self, zarr_group: ZarrGroup, multiscale: Multiscale, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate multiscale without prefetching (assumes already prefetched)."""
        result = ValidationResult()

        # spec: every array referred to by a dataset path MUST have the same
        # datatype. (path, dtype) of the first dataset array found:
        first_dtype: tuple[str, str] | None = None

        for ds_idx, dataset in enumerate(multiscale.datasets):
            ds_loc = (*loc_prefix, "datasets", ds_idx, "path")

            # Check if path exists as array
            if (arr := zarr_group.get(dataset.path)) is None:
                result.add_error(
                    StorageErrorType.dataset_path_not_found,
                    ds_loc,
                    f"Dataset path '{dataset.path}' not found in zarr group",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, dataset.path),
                        "expected": "zarr array",
                    },
                )
                continue

            if not isinstance(arr, ZarrArray):
                result.add_error(
                    StorageErrorType.dataset_not_array,
                    ds_loc,
                    f"Dataset path '{dataset.path}' exists but is not a zarr array",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, dataset.path),
                        "expected": "array",
                        "found": "group",
                    },
                )
                continue

            # Check array dimensionality matches axes
            expected_ndim = len(multiscale.axes)
            if arr.ndim != expected_ndim:
                result.add_error(
                    StorageErrorType.dataset_dimension_mismatch,
                    ds_loc,
                    f"Dataset '{dataset.path}' has {arr.ndim} dimensions "
                    f"but axes specify {expected_ndim}",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, dataset.path),
                        "actual_ndim": arr.ndim,
                        "expected_ndim": expected_ndim,
                        "axes": [ax.name for ax in multiscale.axes],
                    },
                )

            # Check dtype consistency across all datasets in this multiscale
            dtype = str(arr.dtype)
            if first_dtype is None:
                first_dtype = (dataset.path, dtype)
            elif dtype != first_dtype[1]:
                result.add_error(
                    StorageErrorType.dataset_dtype_mismatch,
                    ds_loc,
                    f"Dataset '{dataset.path}' has dtype '{dtype}' but "
                    f"'{first_dtype[0]}' has dtype '{first_dtype[1]}'. All "
                    "datasets in a multiscale must have the same datatype.",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, dataset.path),
                        "dtype": dtype,
                        "expected_dtype": first_dtype[1],
                    },
                )

            # Check dimension_names attribute matches axes.
            # NB: a warning (not an error): the 0.5 spec required this, but the
            # 0.6 draft doesn't mention dimension_names at all.
            if dim_names := list(dict(arr.attrs).get("dimension_names", [])):
                expected_names = [ax.name for ax in multiscale.axes]
                if dim_names != expected_names:
                    result.add_warning(
                        StorageErrorType.dimension_names_mismatch,
                        (*ds_loc, "dimension_names"),
                        f"Array dimension_names {dim_names} don't match "
                        f"axes names {expected_names}",
                        ctx={"actual": dim_names, "expected": expected_names},
                    )

        return result

    # ------------------------------------------------------------------
    # v0.6 transform validation (RFC-5)
    # ------------------------------------------------------------------

    def _visit_multiscale_transforms(
        self, zarr_group: ZarrGroup, multiscale: Multiscale, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate `multiscales > coordinateTransformations` against storage.

        Resolves labels-linked coordinate systems (`input.path` or
        `output.path` -- the model allows the labels link on either side as of
        v0.6rc0, see `Multiscale._post_validate`) and any path-backed transform
        parameters (affine/rotation matrices, displacement and coordinate
        fields).
        """
        result = ValidationResult()
        cs_dims = {cs.name: len(cs.axes) for cs in multiscale.coordinateSystems}

        def _resolve(io: InputOutput | None, io_loc: Loc) -> int | None:
            if io is None or io.name is None:
                return None
            if io.path is None:
                return cs_dims.get(io.name)
            # references a coordinate system in a child labels group: the path
            # MUST resolve to a multiscale image group declaring a coordinate
            # system with that name.
            target = self._load_image_target(zarr_group, io.path, io_loc, result)
            if target is None:
                return None
            cs = _find_image_cs(target, io.name)
            if cs is None:
                result.add_error(
                    StorageErrorType.transform_target_invalid,
                    io_loc,
                    f"Group '{io.path}' does not declare a coordinate system "
                    f"named {io.name!r}",
                    ctx={"path": io.path, "name": io.name},
                )
                return None
            return len(cs.axes)

        for t_idx, t in enumerate(multiscale.coordinateTransformations or []):
            t_loc = (*loc_prefix, "coordinateTransformations", t_idx)
            n_in = _resolve(t.input, (*t_loc, "input"))
            n_out = _resolve(t.output, (*t_loc, "output"))
            result = result.merge(
                self._validate_transform_params(zarr_group, t, t_loc, n_in, n_out)
            )
        return result

    def visit_scene(
        self, zarr_group: ZarrGroup, scene_model: Scene, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate a scene group.

        - every transform `input`/`output` must resolve to a coordinate system,
          either declared in the scene itself (no `path`) or declared by a
          multiscale image subgroup at `path`;
        - path-backed transform parameters must resolve to valid arrays/groups;
        - the coordinate systems + transformations must form a fully connected
          graph (spec "Graph connectedness").
        """
        result = ValidationResult()
        scene_def = scene_model.scene
        scene_cs = {cs.name: cs for cs in (scene_def.coordinateSystems or [])}
        transforms = scene_def.coordinateTransformations

        # prefetch all endpoint image groups in one batch
        endpoint_paths = {
            io.path
            for t in transforms
            for io in (t.input, t.output)
            if io is not None and io.path and _is_relative_downward(io.path)
        }
        zarr_group.prefetch_children(endpoint_paths)
        image_cache: dict[str, Image | None] = {}

        def _endpoint_dims(io: InputOutput | None, io_loc: Loc) -> int | None:
            """Resolve an endpoint to its coordinate system dimensionality."""
            nonlocal result
            if io is None or io.name is None:  # enforced by the Scene model
                return None  # pragma: no cover
            if not io.path:
                if io.name not in scene_cs:
                    result.add_error(
                        StorageErrorType.transform_target_invalid,
                        io_loc,
                        f"Coordinate system {io.name!r} is not declared in the "
                        "scene (and no 'path' was given)",
                        ctx={"name": io.name},
                    )
                    return None
                return len(scene_cs[io.name].axes)
            if not _is_relative_downward(io.path):
                result.add_warning(
                    StorageErrorType.transform_target_not_found,
                    io_loc,
                    f"Path {io.path!r} is not a relative downward path; not validated",
                    ctx={"path": io.path},
                )
                return None
            if io.path not in image_cache:
                image = self._load_image_target(zarr_group, io.path, io_loc, result)
                image_cache[io.path] = image
                # spec: a scene's endpoint images are themselves ordinary image
                # groups -- their own datasets/transforms/labels MUST be valid.
                # Recurse into them (once per unique path) so e.g. a missing
                # array or an invalid child labels group is actually caught,
                # not just the endpoint's own metadata shape.
                if image is not None:
                    target = zarr_group.get(io.path)
                    if isinstance(target, ZarrGroup):
                        result = result.merge(self.visit_image(target, image, io_loc))
            if (image := image_cache[io.path]) is None:
                return None
            if (cs := _find_image_cs(image, io.name)) is None:
                result.add_error(
                    StorageErrorType.transform_target_invalid,
                    io_loc,
                    f"Image '{io.path}' does not declare a coordinate system "
                    f"named {io.name!r}",
                    ctx={"path": io.path, "name": io.name},
                )
                return None
            return len(cs.axes)

        # (path, name) pairs identify coordinate systems in the graph;
        # scene-level systems have path "".
        nodes: set[tuple[str, str]] = {("", name) for name in scene_cs}
        adjacency: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)

        for t_idx, t in enumerate(transforms):
            t_loc = (*loc_prefix, "scene", "coordinateTransformations", t_idx)
            n_in = _endpoint_dims(t.input, (*t_loc, "input"))
            n_out = _endpoint_dims(t.output, (*t_loc, "output"))
            result = result.merge(
                self._validate_transform_params(zarr_group, t, t_loc, n_in, n_out)
            )
            if (
                t.input is not None
                and t.input.name is not None
                and t.output is not None
                and t.output.name is not None
            ):
                u = (t.input.path or "", t.input.name)
                v = (t.output.path or "", t.output.name)
                nodes.update((u, v))
                adjacency[u].add(v)
                adjacency[v].add(u)

        # Graph connectedness: any two coordinate systems in the metadata MUST
        # be connected by a sequence of transformations (direction-agnostic).
        if len(nodes) > 1:
            seen = {next(iter(nodes))}
            stack = list(seen)
            while stack:
                for neighbor in adjacency[stack.pop()]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            if unreached := nodes - seen:
                names = sorted("/".join(filter(None, n[::-1])) for n in unreached)
                result.add_error(
                    StorageErrorType.transform_graph_disconnected,
                    (*loc_prefix, "scene", "coordinateTransformations"),
                    "The scene's coordinate systems and transformations do not "
                    f"form a fully connected graph. Disconnected from the rest: "
                    f"{names}",
                    ctx={"disconnected": names},
                )

        return result

    def _validate_transform_params(
        self,
        zarr_group: ZarrGroup,
        transform: Transformation,
        loc: Loc,
        n_in: int | None,
        n_out: int | None,
    ) -> ValidationResult:
        """Validate on-disk parameters of a transform (recursively).

        `n_in`/`n_out` are the dimensionalities of the input/output coordinate
        systems when known (None when unresolvable, e.g. mid-sequence).
        """
        result = ValidationResult()
        if isinstance(transform, AffineTransformation):
            if transform.path is not None:
                # spec: 2D array of shape (M)x(N+1)
                result = result.merge(
                    self._check_matrix_array(
                        zarr_group,
                        transform.path,
                        loc,
                        expected_rows=n_out,
                        expected_cols=None if n_in is None else n_in + 1,
                        kind="affine",
                    )
                )
        elif isinstance(transform, RotationTransformation):
            if transform.path is not None:
                # spec: 2D array of shape NxN (input and output dims identical)
                n = n_in if n_in is not None else n_out
                result = result.merge(
                    self._check_matrix_array(
                        zarr_group,
                        transform.path,
                        loc,
                        expected_rows=n,
                        expected_cols=n,
                        kind="rotation",
                    )
                )
        elif isinstance(
            transform, (DisplacementsTransformation, CoordinatesTransformation)
        ):
            result = result.merge(
                self._check_vector_field(zarr_group, transform, loc, n_in, n_out)
            )
        elif isinstance(transform, SequenceTransformation):
            children = transform.transformations
            for c_idx, child in enumerate(children):
                # only the outermost dims are known: the first child's input is
                # the sequence's input, the last child's output its output.
                c_in = n_in if c_idx == 0 else None
                c_out = n_out if c_idx == len(children) - 1 else None
                result = result.merge(
                    self._validate_transform_params(
                        zarr_group, child, (*loc, "transformations", c_idx), c_in, c_out
                    )
                )
        elif isinstance(transform, BijectionTransformation):
            result = result.merge(
                self._validate_transform_params(
                    zarr_group, transform.forward, (*loc, "forward"), n_in, n_out
                )
            )
            result = result.merge(
                self._validate_transform_params(
                    zarr_group, transform.inverse, (*loc, "inverse"), n_out, n_in
                )
            )
        elif isinstance(transform, ByDimensionTransformation):
            for c_idx, item in enumerate(transform.transformations):
                result = result.merge(
                    self._validate_transform_params(
                        zarr_group,
                        item.transformation,
                        (*loc, "transformations", c_idx, "transformation"),
                        len(item.input_axes),
                        len(item.output_axes),
                    )
                )
        return result

    def _check_matrix_array(
        self,
        zarr_group: ZarrGroup,
        path: str,
        loc: Loc,
        expected_rows: int | None,
        expected_cols: int | None,
        kind: str,
    ) -> ValidationResult:
        """Check that a path-backed affine/rotation matrix is a valid 2D array."""
        result = ValidationResult()
        if not _is_relative_downward(path):
            result.add_warning(
                StorageErrorType.transform_path_not_found,
                (*loc, "path"),
                f"Path {path!r} is not a relative downward path; not validated",
                ctx={"path": path},
            )
            return result

        arr = zarr_group.get(path)
        if arr is None:
            result.add_error(
                StorageErrorType.transform_path_not_found,
                (*loc, "path"),
                f"The {kind} transform's path '{path}' was not found",
                ctx={"fs_path": _build_fs_path(zarr_group, path), "kind": kind},
            )
            return result
        if not isinstance(arr, ZarrArray):
            result.add_error(
                StorageErrorType.transform_array_invalid,
                (*loc, "path"),
                f"The {kind} transform's path '{path}' is not a zarr array",
                ctx={"path": path, "expected": "array", "found": "group"},
            )
            return result

        shape = arr.metadata.shape
        if shape is None or len(shape) != 2:
            result.add_error(
                StorageErrorType.transform_array_invalid,
                (*loc, "path"),
                f"The {kind} matrix at '{path}' must be 2-dimensional, "
                f"got shape {list(shape or ())}",
                ctx={"path": path, "shape": list(shape or ())},
            )
            return result

        rows, cols = shape
        if (expected_rows is not None and rows != expected_rows) or (
            expected_cols is not None and cols != expected_cols
        ):
            want = (
                f"({expected_rows or '?'}, {expected_cols or '?'})"
                if kind == "affine"
                else f"({expected_rows}, {expected_cols})"
            )
            result.add_error(
                StorageErrorType.transform_array_invalid,
                (*loc, "path"),
                f"The {kind} matrix at '{path}' has shape {list(shape)}, "
                f"but the input/output coordinate systems require {want}",
                ctx={"path": path, "shape": list(shape)},
            )
        return result

    def _check_vector_field(
        self,
        zarr_group: ZarrGroup,
        transform: DisplacementsTransformation | CoordinatesTransformation,
        loc: Loc,
        n_in: int | None,
        n_out: int | None,
    ) -> ValidationResult:
        """Check a displacements/coordinates field (a multiscale group at `path`).

        Spec constraints: the multiscale image MUST have N+1 dimensions (N =
        input dims); exactly one axis MUST have type "displacement"/"coordinate";
        the array length along that axis MUST equal N (displacements, with M=N)
        or M (coordinates).
        """
        result = ValidationResult()
        path = transform.path
        kind = transform.type  # "displacements" | "coordinates"
        vec_type = "displacement" if kind == "displacements" else "coordinate"

        if not _is_relative_downward(path):
            result.add_warning(
                StorageErrorType.transform_path_not_found,
                (*loc, "path"),
                f"Path {path!r} is not a relative downward path; not validated",
                ctx={"path": path},
            )
            return result

        image = self._load_image_target(zarr_group, path, (*loc, "path"), result)
        if image is None:
            return result

        target = zarr_group.get(path)
        multiscale = image.multiscales[0]
        if isinstance(target, ZarrGroup):
            # spec (0.6rc0 changelog): displacements/coordinates vector fields
            # are stored as a *normal* multiscale group with the same metadata
            # as other multiscales -- validate it exactly like `visit_image`
            # would (dataset arrays exist, ndim/dtype match, etc). Without this
            # a missing or wrong-shaped dataset array silently passes: only the
            # *metadata* was being checked before, not the arrays on disk.
            result = result.merge(
                self._visit_multiscale_no_prefetch(target, multiscale, (*loc, "path"))
            )

        if kind == "displacements" and None not in (n_in, n_out) and n_in != n_out:
            result.add_error(
                StorageErrorType.vector_field_invalid,
                loc,
                f"A displacements transform requires input and output coordinate "
                f"systems of equal dimensionality, got {n_in} and {n_out}",
                ctx={"path": path, "n_in": n_in, "n_out": n_out},
            )

        axes = multiscale.axes
        if n_in is not None and len(axes) != n_in + 1:
            result.add_error(
                StorageErrorType.vector_field_invalid,
                (*loc, "path"),
                f"The {kind} field at '{path}' must have {n_in + 1} dimensions "
                f"(input dimensionality + 1), but has {len(axes)} axes",
                ctx={"path": path, "ndim": len(axes), "expected": n_in + 1},
            )

        vec_idxs = [
            i for i, ax in enumerate(axes) if getattr(ax, "type", None) == vec_type
        ]
        if len(vec_idxs) != 1:
            result.add_error(
                StorageErrorType.vector_field_invalid,
                (*loc, "path"),
                f"The {kind} field at '{path}' must have exactly one axis of "
                f"type {vec_type!r}, found {len(vec_idxs)}",
                ctx={"path": path, "found": len(vec_idxs)},
            )
        else:
            idx = vec_idxs[0]
            vec_axis = axes[idx]
            # spec (0.6rc0 changelog): the displacement/coordinate axis is now
            # required to set `discrete: true`.
            if not getattr(vec_axis, "discrete", False):
                result.add_error(
                    StorageErrorType.vector_field_invalid,
                    (*loc, "path"),
                    f"The {kind} field's {vec_type!r} axis ({vec_axis.name!r}) "
                    "must set 'discrete': true",
                    ctx={"path": path, "axis": vec_axis.name},
                )
            # the length along the vector axis must equal M (coordinates) or
            # N (displacements). check against the highest-resolution level.
            expected_len = n_in if kind == "displacements" else n_out
            if expected_len is not None and isinstance(target, ZarrGroup):
                arr = target.get(multiscale.datasets[0].path)
                if isinstance(arr, ZarrArray) and (shape := arr.metadata.shape):
                    if len(shape) == len(axes) and shape[idx] != expected_len:
                        result.add_error(
                            StorageErrorType.vector_field_invalid,
                            (*loc, "path"),
                            f"The {kind} field at '{path}' has length "
                            f"{shape[idx]} along its {vec_type!r} axis, "
                            f"but the transform requires {expected_len}",
                            ctx={
                                "path": path,
                                "found": shape[idx],
                                "expected": expected_len,
                            },
                        )
        return result

    def _load_image_target(
        self, zarr_group: ZarrGroup, path: str, loc: Loc, result: ValidationResult
    ) -> Image | None:
        """Resolve `path` to a multiscale image group, recording errors."""
        target = zarr_group.get(path)
        if target is None:
            result.add_error(
                StorageErrorType.transform_target_not_found,
                loc,
                f"Path '{path}' was not found in the zarr group",
                ctx={"fs_path": _build_fs_path(zarr_group, path)},
            )
            return None
        if not isinstance(target, ZarrGroup):
            result.add_error(
                StorageErrorType.transform_target_invalid,
                loc,
                f"Path '{path}' is not a zarr group",
                ctx={"path": path, "expected": "group", "found": "array"},
            )
            return None
        meta = self._child_metadata(target, loc, result)
        if not isinstance(meta, Image):
            ctx: dict = {"path": path}
            if isinstance(meta, Exception):
                ctx["error"] = str(meta)
            else:
                ctx["type"] = type(meta).__name__
            result.add_error(
                StorageErrorType.transform_target_invalid,
                loc,
                f"Path '{path}' does not contain valid Image ('multiscales') metadata",
                ctx=ctx,
            )
            return None
        return meta

    def visit_plate(
        self, zarr_group: ZarrGroup, plate_model: Plate, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate a plate group and its wells."""
        result = ValidationResult()

        well_paths = [well.path for well in plate_model.plate.wells]

        # Prefetch all metadata in one go to minimize network round trips
        self._prefetch_plate_hierarchy(zarr_group, well_paths)

        # Validate each well path
        for well_idx, well in enumerate(plate_model.plate.wells):
            well_loc = (*loc_prefix, "plate", "wells", well_idx)

            if (well_group := zarr_group.get(well.path)) is None:
                result.add_error(
                    StorageErrorType.well_path_not_found,
                    (*well_loc, "path"),
                    f"Well path '{well.path}' not found in plate group",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, well.path),
                        "expected": "zarr group",
                    },
                )
                continue

            if not isinstance(well_group, ZarrGroup):
                result.add_error(
                    StorageErrorType.well_path_not_group,
                    (*well_loc, "path"),
                    f"Well path '{well.path}' is not a zarr group",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, well.path),
                        "expected": "group",
                        "found": "array",
                    },
                )
                continue

            # Validate well metadata
            well_model = self._child_metadata(well_group, well_loc, result)
            if isinstance(well_model, Well):
                result = result.merge(
                    self._validate_well_acquisitions(plate_model, well_model, well_loc)
                )
                result = result.merge(self.visit_well(well_group, well_model, well_loc))
            else:
                ctx: dict = {"path": well.path}
                if isinstance(well_model, Exception):
                    ctx["error"] = well_model
                else:
                    ctx["type"] = type(well_model).__name__
                result.add_error(
                    StorageErrorType.well_invalid,
                    well_loc,
                    f"Well path '{well.path}' does not contain valid Well metadata",
                    ctx=ctx,
                )

        return result

    def _validate_well_acquisitions(
        self, plate_model: Plate, well_model: Well, loc_prefix: Loc
    ) -> ValidationResult:
        """Cross-check well field-of-view acquisition ids against the plate.

        Spec: if multiple acquisitions were performed in the plate, each field
        of view MUST contain an `acquisition` key whose value MUST match one of
        the acquisitions defined in the plate metadata.
        """
        result = ValidationResult()
        if (acquisitions := plate_model.plate.acquisitions) is None:
            return result
        acq_ids = {acq.id for acq in acquisitions}
        for field_idx, field_image in enumerate(well_model.well.images):
            field_loc = (*loc_prefix, "well", "images", field_idx, "acquisition")
            if field_image.acquisition is None:
                if len(acquisitions) > 1:
                    result.add_error(
                        StorageErrorType.well_acquisition_invalid,
                        field_loc,
                        f"Field '{field_image.path}' has no 'acquisition' key, "
                        "but the plate defines multiple acquisitions",
                        ctx={"path": field_image.path},
                    )
            elif field_image.acquisition not in acq_ids:
                result.add_error(
                    StorageErrorType.well_acquisition_invalid,
                    field_loc,
                    f"Field '{field_image.path}' references acquisition "
                    f"{field_image.acquisition}, which is not defined in the "
                    f"plate metadata (defined: {sorted(acq_ids)})",
                    ctx={
                        "path": field_image.path,
                        "acquisition": field_image.acquisition,
                        "defined": sorted(acq_ids),
                    },
                )
        return result

    def visit_well(
        self, zarr_group: ZarrGroup, well_model: Well, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate a well group and its field images."""
        result = ValidationResult()

        # Performance optimization: prefetch all field image metadata in one batch
        # Note: For plates, this is often already prefetched by visit_plate's
        # deep prefetch strategy, but we do it here too for standalone wells
        field_paths = [field.path for field in well_model.well.images]
        zarr_group.prefetch_children(field_paths)

        # Validate each field image path
        for field_idx, field_image in enumerate(well_model.well.images):
            field_loc = (*loc_prefix, "well", "images", field_idx)
            if (field_group := zarr_group.get(field_image.path)) is None:
                result.add_error(
                    StorageErrorType.field_path_not_found,
                    (*field_loc, "path"),
                    f"Field path '{field_image.path}' not found in well group",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, field_image.path),
                        "expected": "zarr group",
                    },
                )
                continue

            if not isinstance(field_group, ZarrGroup):
                result.add_error(
                    StorageErrorType.field_path_not_group,
                    (*field_loc, "path"),
                    f"Field path '{field_image.path}' is not a zarr group",
                    ctx={
                        "fs_path": _build_fs_path(zarr_group, field_image.path),
                        "expected": "group",
                        "found": "array",
                    },
                )
                continue

            # Validate field as image group
            field_group_model = self._child_metadata(field_group, field_loc, result)
            if isinstance(field_group_model, Image):
                result = result.merge(
                    self.visit_image(field_group, field_group_model, field_loc)
                )
            else:
                ctx: dict = {"fs_path": _build_fs_path(zarr_group, field_image.path)}
                if isinstance(field_group_model, Exception):
                    ctx["error"] = field_group_model
                else:
                    ctx["type"] = type(field_group_model).__name__
                result.add_error(
                    StorageErrorType.field_image_invalid,
                    field_loc,
                    f"Field path '{field_image.path}' does not contain "
                    "valid Image metadata",
                    ctx=ctx,
                )

        return result

    def visit_bioformats2raw(
        self, zarr_group: ZarrGroup, bf2raw_model: Bf2Raw, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate a bioformats2raw layout.

        According to spec:
        1. Check for OME subgroup with optional "series" metadata
        2. If series exists, validate those paths
        3. Otherwise, validate consecutively numbered directories (0/, 1/, 2/, ...)
        """
        result = ValidationResult()

        # First, check if there's an OME subgroup
        zarr_group.prefetch_children(["OME"])

        # Check for OME subgroup with series metadata
        ome_group = zarr_group.get("OME")
        if ome_group is not None and isinstance(ome_group, ZarrGroup):
            try:
                ome_attrs_model = validate_ome_object(ome_group.attrs, OMEAttributes)

                # If OME group has series metadata, use that to find images
                if isinstance(ome_attrs_model.ome, Series):
                    # Validate using the series paths
                    result = result.merge(
                        self.visit_series(
                            zarr_group, ome_attrs_model.ome, (*loc_prefix, "OME")
                        )
                    )
                    return result
            except Exception:
                # OME group exists but doesn't have valid OME metadata
                # Fall through to numbered directory validation
                pass  # pragma: no cover

        # No OME group with series, so validate numbered directories
        # Discover consecutively numbered directories (0, 1, 2, etc.)
        # FIXME: ... do better for searching
        numbered_paths = []
        for i in range(1000):  # reasonable upper limit
            if str(i) not in zarr_group:
                break
            numbered_paths.append(str(i))

        if not numbered_paths:
            result.add_error(
                StorageErrorType.bf2raw_no_images,
                loc_prefix,
                "Bioformats2raw group contains no numbered image directories",
            )
            return result

        # Prefetch all numbered path metadata
        zarr_group.prefetch_children(numbered_paths)

        # Validate each numbered directory as image group
        for path in numbered_paths:
            image_loc = (*loc_prefix, path)

            image_group = zarr_group.get(path)
            if not isinstance(image_group, ZarrGroup):
                result.add_error(
                    StorageErrorType.bf2raw_path_not_group,
                    image_loc,
                    f"Bioformats2raw path '{path}' is not a zarr group",
                    ctx={"path": path, "expected": "group", "found": "array"},
                )
                continue

            # Validate as image group
            image_group_meta = self._child_metadata(image_group, image_loc, result)
            if isinstance(image_group_meta, Image):
                result = result.merge(
                    self.visit_image(image_group, image_group_meta, image_loc)
                )
            else:
                ctx: dict = {"path": path}
                if isinstance(image_group_meta, Exception):
                    ctx["error"] = image_group_meta
                else:
                    ctx["type"] = type(image_group_meta).__name__
                result.add_error(
                    StorageErrorType.bf2raw_invalid_image,
                    image_loc,
                    f"Bioformats2raw path '{path}' does not contain "
                    "valid Image metadata",
                    ctx=ctx,
                )

        return result

    def visit_series(
        self, zarr_group: ZarrGroup, ome_model: Series, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate an OME group with series metadata.

        The series attribute is a list of paths to image groups. Each path
        should point to a valid image group with multiscales metadata.

        IMPORTANT! `zarr_group` here is the *parent* of the OME group, not the
        OME group itself.

        ```
        top_group.zarr      <-- what must be passed to `zarr_group` here
        ├── 0/
        │   ├── zarr.json   <-- contains multiscales metadata
        ├── OME/
        │   ├── zarr.json   <-- contains `ome_model` Series model
        └── zarr.json       <-- contains bioformats2raw metadata
        ```
        """
        result = ValidationResult()

        # Prefetch all series path metadata
        zarr_group.prefetch_children(ome_model.series)

        # Validate each series path
        for series_idx, series_path in enumerate(ome_model.series):
            series_loc = (*loc_prefix, "series", series_idx)

            series_group = zarr_group.get(series_path)
            if series_group is None:
                result.add_error(
                    StorageErrorType.series_path_not_found,
                    series_loc,
                    f"Series path '{series_path}' not found in series group",
                    ctx={"path": series_path, "expected": "zarr group"},
                )
                continue

            if not isinstance(series_group, ZarrGroup):
                result.add_error(
                    StorageErrorType.series_path_not_group,
                    series_loc,
                    f"Series path '{series_path}' is not a zarr group",
                    ctx={"path": series_path, "expected": "group", "found": "array"},
                )
                continue

            # Validate series as image group
            series_group_meta = self._child_metadata(series_group, series_loc, result)
            if isinstance(series_group_meta, Image):
                result = result.merge(
                    self.visit_image(series_group, series_group_meta, series_loc)
                )
            else:
                ctx: dict = {"path": series_path}
                if isinstance(series_group_meta, Exception):
                    ctx["error"] = series_group_meta
                else:
                    ctx["type"] = type(series_group_meta).__name__
                result.add_error(
                    StorageErrorType.series_invalid_image,
                    series_loc,
                    f"Series path '{series_path}' does not contain "
                    "valid Image metadata",
                    ctx=ctx,
                )

        return result

    def _prefetch_plate_hierarchy(
        self, zarr_group: ZarrGroup, well_paths: list[str]
    ) -> None:
        """Prefetch entire plate hierarchy to minimize network round trips.

        Strategy: Inspect first well/field to understand structure, then batch
        fetch all metadata across the entire plate (wells, fields, datasets).
        """
        if not well_paths:  # pragma: no cover
            return

        # Step 1: Prefetch all well metadata
        zarr_group.prefetch_children(well_paths)

        # Step 2: Get structure from first well
        field_paths = self._get_field_paths_from_first_well(zarr_group, well_paths[0])
        if not field_paths:
            return

        # Step 3: Prefetch all field images across all wells
        all_field_paths = ("/".join(grp) for grp in product(well_paths, field_paths))
        zarr_group.prefetch_children(all_field_paths)

        # Step 4: Get dataset structure from first field
        first_well = zarr_group.get(well_paths[0])
        if not isinstance(first_well, ZarrGroup):
            return  # pragma: no cover

        dataset_paths = self._get_dataset_paths_from_first_field(
            first_well, field_paths[0]
        )
        if not dataset_paths:
            return

        # Step 5: Prefetch all datasets across entire plate
        # Also prefetch labels metadata (optional, but common)
        ds_paths = (
            "/".join(grp) for grp in product(well_paths, field_paths, dataset_paths)
        )
        labels_paths = (
            "/".join(grp) + "/labels" for grp in product(well_paths, field_paths)
        )
        zarr_group.prefetch_children(chain(ds_paths, labels_paths))

    def _get_field_paths_from_first_well(
        self, zarr_group: ZarrGroup, first_well_path: str
    ) -> list[str]:
        """Extract field image paths from the first well."""
        first_well = zarr_group.get(first_well_path)
        if not isinstance(first_well, ZarrGroup):
            return []

        try:
            first_well_meta = validate_ome_object(first_well.attrs, OMEAttributes)
            if isinstance(first_well_meta.ome, Well):
                return [img.path for img in first_well_meta.ome.well.images]
        except Exception:
            pass
        return []

    def _get_dataset_paths_from_first_field(
        self, first_well: ZarrGroup, first_field_path: str
    ) -> list[str]:
        """Extract dataset paths from the first field image."""
        first_field = first_well.get(first_field_path)
        if not isinstance(first_field, ZarrGroup):
            return []  # pragma: no cover

        try:
            first_field_meta = validate_ome_object(first_field.attrs, OMEAttributes)
        except Exception:
            return []  # pragma: no cover

        if (
            not isinstance(first_field_meta.ome, Image)
            or not first_field_meta.ome.multiscales
        ):
            return []  # pragma: no cover

        return [ds.path for ds in first_field_meta.ome.multiscales[0].datasets]

    def _check_for_labels_group(
        self, zarr_group: ZarrGroup, loc_prefix: Loc
    ) -> LabelsCheckResult:
        """Check for labels group at same level as datasets and return result."""
        result = ValidationResult()

        if (labels_group := zarr_group.get("labels")) is None:
            return LabelsCheckResult(result=result, labels_info=None)

        labels_loc = (*loc_prefix, "labels")

        if not isinstance(labels_group, ZarrGroup):
            result.add_error(
                StorageErrorType.labels_not_group,
                labels_loc,
                f"Found 'labels' path but it is a {type(labels_group)}, "
                "not a zarr group",
                ctx={"expected": "group", "found": type(labels_group).__name__},
            )
            return LabelsCheckResult(result=result, labels_info=None)

        try:
            labels_attrs = validate_ome_object(labels_group.attrs, OMEAttributes)
            if isinstance(labels_attrs.ome, LabelsGroup):
                # Return the labels info directly
                return LabelsCheckResult(
                    result=result, labels_info=(labels_group, labels_attrs.ome)
                )
        except Exception as e:
            result.add_error(
                StorageErrorType.labels_metadata_invalid,
                labels_loc,
                f"Found a 'labels' subg-group inside of ome-zarr group {zarr_group}, "
                f"but metadata not valid LabelsGroup metadata: {e!s}",
                ctx={"error": str(e)},
            )

        return LabelsCheckResult(result=result, labels_info=None)

    def _validate_labels_image_source(
        self, zarr_group: ZarrGroup, src_img_rel_path: str, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate that label image source exists and is valid."""
        result = ValidationResult()

        # Resolve the source image path relative to the current zarr group
        try:
            image_source = _resolve_source_path(zarr_group, src_img_rel_path)
        except Exception:
            warnings.warn(
                "Unable to resolve source image path", UserWarning, stacklevel=3
            )
            return result

        try:
            img = validate_ome_uri(image_source, OMEZarrGroupJSON)
            if not isinstance(img.attributes.ome, Image):
                result.add_error(
                    StorageErrorType.label_image_source_invalid,
                    (*loc_prefix, "image_label", "source", "image"),
                    f"Label image source '{image_source}' does not contain "
                    "valid Image ('multiscales') metadata",
                    ctx={"source": image_source, "expected": "Image"},
                )
        except Exception as e:
            result.add_error(
                StorageErrorType.label_image_source_not_found,
                (*loc_prefix, "image_label", "source", "image"),
                f"Label image source '{image_source}' could not be opened: {e!s}",
                ctx={"source": image_source, "error": str(e)},
            )

        return result

    def _validate_label_data_types(
        self, image_model: LabelImage, zarr_group: ZarrGroup, loc_prefix: Loc
    ) -> ValidationResult:
        """Validate that label arrays contain only integer data types."""
        result = ValidationResult()

        # The "labels" group is not itself an image; it contains images.
        # The pixels of the label images MUST be integer data types, i.e. one of
        # [uint8, int8, uint16, int16, uint32, int32, uint64, int64].
        for ms_idx, multiscale in enumerate(image_model.multiscales):
            ms_loc = (*loc_prefix, "multiscales", ms_idx)

            for ds_idx, dataset in enumerate(multiscale.datasets):
                ds_loc = (*ms_loc, "datasets", ds_idx, "path")
                if (arr := zarr_group.get(dataset.path)) is None:
                    # Path validation will catch this separately
                    continue  # pragma: no cover

                # check if integer dtype
                if isinstance(arr, ZarrArray):
                    dt = arr.dtype
                    if not _is_integer_dtype(dt):
                        result.add_error(
                            StorageErrorType.label_non_integer_dtype,
                            ds_loc,
                            f"Label array '{dataset.path}' has non-integer dtype "
                            f"'{dt}'. Labels must use integer types.",
                            ctx={
                                "path": dataset.path,
                                "dtype": str(
                                    dt,
                                ),
                            },
                        )

        return result


# ----------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------


def _is_relative_downward(path: str) -> bool:
    """Whether `path` stays inside the current group (validatable).

    Normalizes first so a path that only *looks* downward at the start but
    escapes via a later `..` segment (e.g. `"a/../../outside"`) is caught too,
    not just one starting with `"../"` or `"/"`.
    """
    if path.startswith("/"):
        return False
    normalized = posixpath.normpath(path)
    return normalized != ".." and not normalized.startswith("../")


def _find_image_cs(image: Image, name: str):
    """Find a coordinate system by name across an image's multiscales."""
    for multiscale in image.multiscales:
        for cs in multiscale.coordinateSystems:
            if cs.name == name:
                return cs
    return None


def _resolve_source_path(zarr_group: ZarrGroup, src_rel_path: str) -> str:
    """Resolve a relative source path against the zarr group's store location.

    Parameters
    ----------
    zarr_group : ZarrGroup
        The zarr group to resolve relative to
    src_rel_path : str
        The relative path to resolve (e.g., "../other",
        "../../images/source.zarr")

    Returns
    -------
    str
        The resolved absolute path
    """
    # Get the mapper's root path if available
    mapper = zarr_group._store
    path = zarr_group.path

    # Try to get the root path from the mapper
    if hasattr(mapper, "root"):
        root = mapper.root
    elif hasattr(mapper, "fs") and hasattr(mapper.fs, "root"):
        root = mapper.fs.root
    else:
        # Fall back to using the path directly
        root = ""

    # Handle URL paths
    if isinstance(root, str) and root.startswith(("http://", "https://")):
        from urllib.parse import urljoin

        # Ensure root ends with separator for proper urljoin behavior
        if not root.endswith("/"):
            root = root + "/"
        root = urljoin(root, path)
        if not root.endswith("/"):
            root = root + "/"
        return urljoin(root, src_rel_path)
    else:
        # For other filesystems, use posixpath for UNIX-style path joining
        # Most fsspec filesystems use forward slashes as separators
        return posixpath.normpath(posixpath.join(str(root), path, src_rel_path))


def _is_integer_dtype(dtype_str: str) -> bool:
    """Check if a dtype string represents an integer type.

    Parameters
    ----------
    dtype_str : str
        The dtype string to check (e.g., '<i2', 'uint8', 'int32')

    Returns
    -------
    bool
        True if the dtype represents an integer type, False otherwise
    """
    # Remove endianness markers
    dtype_clean = dtype_str.lstrip("<>=|")
    # Check for integer type indicators
    return dtype_clean.startswith(("int", "uint")) or (
        len(dtype_clean) >= 2
        and dtype_clean[0] in ("i", "u")
        and dtype_clean[1].isdigit()
    )
