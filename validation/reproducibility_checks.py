"""Reproducibility check: generate twice into temporary folders and compare rows and SHA-256 checksums."""

import json
import os
import tempfile
from typing import Any, Dict

import generator  # noqa: F401
from generator import config
from generator.generate import run


def run_reproducibility_check(size: config.DatasetSize = config.FULL_SIZE) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        first = run(os.path.join(a, "run"), size)["files"]
        second = run(os.path.join(b, "run"), size)["files"]
    rows = []
    for name in sorted(first):
        same = first[name] == second.get(name)
        rows.append({"file": name, "rows_run1": first[name]["rows"], "rows_run2": second.get(name, {}).get("rows"),
                     "sha256_run1": first[name]["sha256"], "sha256_run2": second.get(name, {}).get("sha256"),
                     "identical": same})
    return {"seed": config.SEED, "files": rows, "all_identical": all(r["identical"] for r in rows)}


if __name__ == "__main__":
    print(json.dumps(run_reproducibility_check(), indent=2))
