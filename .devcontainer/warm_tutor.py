"""Explicitly load the tutor for 15 minutes; never downloads or generates an answer."""

import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

base = os.environ.get("OLLAMA_HOST", "http://ollama:11434").rstrip("/")
config = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / ".continue/config.yaml").read_text()
)
model = next(
    entry for entry in config["models"] if entry["name"].startswith("Tutor - Gemma")
)
options = model["defaultCompletionOptions"]
body = {
    "model": model["model"],
    "keep_alive": options["keepAlive"],
    "stream": False,
    "options": {"num_ctx": options["contextLength"]},
}
with urlopen(
    Request(
        base + "/api/generate",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    ),
    timeout=270,
) as response:
    result = json.load(response)
if result.get("error") or not result.get("done"):
    raise RuntimeError(result)
print(
    f"Gemma is loaded for {options['keepAlive']} seconds. Another model selection may unload it."
)
