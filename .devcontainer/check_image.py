"""Check the distributable image without a workspace, Ollama, or model downloads."""

import os
import sys
from importlib.metadata import version
from pathlib import Path

assert sys.version_info[:2] == (3, 13), sys.version
assert Path(sys.prefix) == Path("/opt/venv"), sys.prefix
assert os.getuid() != 0, "Run as vscode"
assert os.access("/opt/venv", os.W_OK), "Virtual environment must be writable"
assert Path("/usr/local/bin/python").is_file(), "System Python is required for rebuilds"
for line in (
    Path("/usr/local/share/classroom/requirements-dev.txt").read_text().splitlines()
):
    package, expected = line.split("==")
    assert version(package) == expected, (package, version(package), expected)
print("Classroom image: Python 3.13, non-root permissions, and package versions OK")
