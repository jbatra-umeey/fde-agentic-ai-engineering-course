"""Verify this upgrade retains original teaching content from an explicit Git base."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    paths = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            args.base,
            "docs/illustrations",
            "docs/modules",
            "examples",
            "course",
            "docs/ARCHITECTURE.md",
        ],
        text=True,
    ).splitlines()
    records = []
    for name in paths:
        original = subprocess.check_output(["git", "show", f"{args.base}:{name}"])
        current = Path(name).read_bytes()
        # New teaching sections may be appended; existing illustration bytes are immutable.
        assert (
            current == original
            if name.startswith("docs/illustrations/")
            else current.startswith(original)
        ), name
        records.append(
            {
                "path": name,
                "original_sha256": hashlib.sha256(original).hexdigest(),
                "preserved": True,
            }
        )
    result = {"base": args.base, "files": records, "passed": True}
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(f"Preserved {len(records)} original course, example and illustration files")


if __name__ == "__main__":
    main()
