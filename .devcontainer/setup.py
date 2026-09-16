"""Install Continue's local config and provision its models in the Ollama service."""

import argparse
import json
import os
import shutil
import sys
import time
from http.client import HTTPException
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".continue" / "config.yaml"
API = os.environ.get("OLLAMA_HOST", "http://ollama:11434").rstrip("/")


def install_config():
    destination = Path.home() / ".continue" / "config.yaml"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() == CONFIG.read_bytes():
            print("Continue config already installed.", flush=True)
            return
        backup = destination.with_name(f"config.yaml.backup-{time.time_ns()}")
        shutil.copy2(destination, backup)
        print(f"Previous config saved to {backup}", flush=True)
    shutil.copy2(CONFIG, destination)
    print(f"Installed {destination}. Select Classroom Local Python in Continue.")


def models():
    config = yaml.safe_load(CONFIG.read_text())
    return list(
        dict.fromkeys(
            entry["model"]
            for entry in config["models"]
            if entry["provider"] == "ollama"
        )
    )


def installed_models():
    with urlopen(f"{API}/api/tags", timeout=10) as response:
        return {entry["name"] for entry in json.load(response)["models"]}


def wait_for_ollama():
    for attempt in range(30):
        try:
            return installed_models()
        except (OSError, HTTPException):
            if attempt == 29:
                raise
            print(f"Waiting for Ollama at {API}...", flush=True)
            time.sleep(2)


def pull_model(model):
    request = Request(
        f"{API}/api/pull",
        data=json.dumps({"model": model, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    print(f"Downloading {model} (existing partial downloads resume)...", flush=True)
    last_report = 0.0
    succeeded = False
    with urlopen(request, timeout=600) as response:
        for line in response:
            event = json.loads(line)
            if "error" in event:
                raise RuntimeError(event["error"])
            status = event.get("status", "")
            if time.monotonic() - last_report >= 10 or status == "success":
                total = event.get("total", 0)
                progress = (
                    f" {100 * event.get('completed', 0) / total:.0f}%" if total else ""
                )
                print(f"  {model}: {status}{progress}", flush=True)
                last_report = time.monotonic()
            succeeded = status == "success"
    if not succeeded:
        raise RuntimeError(f"Download stream ended before {model} finished")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["config", "pull", "check"])
    args = parser.parse_args()
    if args.action == "config":
        install_config()
        return
    present = wait_for_ollama()
    missing = [model for model in models() if model not in present]
    if args.action == "check":
        for model in models():
            print(f"{model}: {'MISSING' if model in missing else 'ready'}")
        if missing:
            raise RuntimeError("Run: python .devcontainer/setup.py pull")
        return
    for model in missing:
        for attempt in range(3):
            try:
                pull_model(model)
                break
            except (OSError, HTTPException, RuntimeError, ValueError) as error:
                if attempt == 2:
                    raise
                print(f"Retrying after: {error}", flush=True)
                time.sleep(3)
    remaining = set(models()) - installed_models()
    if remaining:
        raise RuntimeError(f"Models still missing: {sorted(remaining)}")
    print("All course models are ready in Ollama.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, HTTPException, RuntimeError, ValueError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        print("Retry with: python .devcontainer/setup.py pull", file=sys.stderr)
        sys.exit(1)
