"""Verify host-backed workspace storage and show saved, uncommitted work."""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def mounted_at(root, mountinfo):
    def decode(value):
        return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)

    return any(
        len(fields := line.split()) > 4 and decode(fields[4]) == str(root)
        for line in mountinfo.splitlines()
    )


def check(root=ROOT):
    marker = json.loads((root / ".devcontainer/workspace.local.json").read_text())
    expected = os.environ.get("CLASSROOM_WORKSPACE_ID")
    if not expected or marker.get("id") != expected:
        raise RuntimeError(
            "Workspace identity mismatch. Reopen the intended HOST checkout and rebuild its container."
        )
    if not mounted_at(root, Path("/proc/self/mountinfo").read_text()):
        raise RuntimeError(
            f"{root} is not a separate mount. Do not store coursework here until the host bind mount is restored."
        )
    with tempfile.TemporaryFile(dir=root) as handle:
        handle.write(b"workspace write check")
    print(f"Saved files live on your host: {marker['host_path']}")
    print(
        f"Work inside {root}; files elsewhere may disappear when the container is replaced."
    )
    result = subprocess.run(
        ["git", "--no-optional-locks", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    if result.stdout.strip():
        print(
            "Saved changes not yet committed (untracked files included):\n"
            + result.stdout
        )
    else:
        print("Working tree is clean. Commit and push finished work regularly.")
    return marker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check"])
    parser.parse_args()
    check()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Workspace check failed: {error}") from error
