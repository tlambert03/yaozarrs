# Vendored NGFF spec sources

Unmodified copies of the NGFF specification source files, and of the JSON schemas that
rules cite, at the commits pinned in
`src/yaozarrs/_rules/rules.toml` (`[spec.*]`). `tests/test_rules.py` uses them to
check that every rule's quote is at the recorded lines, without network access.

Refresh with `uv run python scripts/ngff_rules.py fetch`.

Copyright © the OME-NGFF contributors. The 0.4 and 0.5 files are licensed under the
[W3C Software and Document License](https://www.w3.org/Consortium/Legal/2015/copyright-software-and-document);
see <https://github.com/ome/ngff/blob/main/LICENSE.md>. The 0.6 file states its terms in
its "License" section.
