"""Verify the running development environment without downloading any AI models."""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen

import workspace

assert Path(sys.prefix) == Path("/opt/venv"), f"Wrong Python: {sys.prefix}"
assert os.getuid() != 0, "Run as vscode"
assert os.access("/opt/venv", os.W_OK), "Python environment is not writable"
workspace.check()
assert (Path.home() / ".continue/config.yaml").read_bytes() == (
    workspace.ROOT / ".continue/config.yaml"
).read_bytes()
with urlopen("http://ollama:11434/api/version", timeout=10) as response:
    print("Ollama:", json.load(response)["version"])
with urlopen("http://127.0.0.1:11435/health", timeout=10) as response:
    assert json.load(response)["status"] == "ok"
print("Python, host workspace, Continue configuration, and Ollama network: OK")
