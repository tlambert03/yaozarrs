"""Writing machinery shared by more than one OME-NGFF spec version.

CONTRACT: same as `yaozarrs._common`.  Everything here is used by *every* writer
version, so changing behavior here changes how older versions are written too.

- Backends, chunking, group creation and the builder logic live here; each
  `yaozarrs.write.vNN` module supplies its own model classes (as class attributes
  of the builder subclasses) and its own public docstrings.
- Never branch on version (no version string literals here).
- Never import from version packages (`yaozarrs.v05`, `yaozarrs.write.v05`, ...).

Guarded by tests/write/v05/ and tests/test_architecture.py.
"""
