"""Fail if `oztest` results differ from `known_failures.txt`.

Each case not listed there is expected to pass, so this exits nonzero for new
failures, and for listed cases that now pass or fail differently (update the list).
`oztest run` itself exits 0 regardless of the results.
"""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

KNOWN_FAILURES = Path(__file__).with_name("known_failures.txt")
DINGUS = Path(__file__).with_name("dingus.py")


def _reason(slug: str) -> str:
    """Re-run the dingus on a case, as `oztest` drops its output from the results."""
    path = Path(str(files("oztest.cases"))) / slug
    case = next(path.parent.glob(f"{path.name}.*"))
    cmd = [sys.executable, str(DINGUS), str(case)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode:
        return proc.stderr.strip().splitlines()[-1]
    return json.loads(proc.stdout).get("message", "accepted as valid")[:500]


def main(result_files: list[str]) -> int:
    known = {}
    for line in KNOWN_FAILURES.read_text().splitlines():
        if entry := line.partition("#")[0].split():
            status, slug = entry
            known[slug] = status

    results = {}
    for file in result_files:
        data = json.loads(Path(file).read_text())
        results.update({r["slug"]: r["result"] for r in data["results"]})

    passed = sum(result == "pass" for result in results.values())
    print(f"{passed}/{len(results)} passed, {len(known)} known failures")

    unexpected = 0
    for slug in sorted(known | results):
        expected = known.get(slug, "pass")
        actual = results.get(slug, "missing")
        if actual != expected:
            print(f"UNEXPECTED: {slug}: expected {expected}, got {actual}")
            if actual in ("fail", "error"):
                print(f"    {_reason(slug)}")
            unexpected += 1
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
