"""Host-side probe container: generate isolated Compose settings for this checkout."""

import hashlib
import json
import os
import sys
from pathlib import Path


def workspace_identity(host_path):
    if not host_path or "\x00" in host_path:
        raise ValueError("The host checkout path is required")
    # Interpret Windows input independently of the probe container's Linux OS.
    normalized = host_path.replace("\\", "/").rstrip("/")
    if len(normalized) > 1 and normalized[1] == ":":
        normalized = normalized.casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def runtime_override(host_path, is_podman, uid_map):
    identity = workspace_identity(host_path)
    options = {
        "environment": {"CLASSROOM_WORKSPACE_ID": identity},
        "labels": {"classroom.workspace.id": identity},
    }
    rootless = uid_map.splitlines()[0].split()[2] == "1"
    if is_podman and rootless:
        options["userns_mode"] = "keep-id"
    # Alphanumeric names survive older Compose providers' name normalization.
    return {"name": f"classroom{identity}", "services": {"python": options}}


def write_owned(path, value, owner):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.chown(temporary, owner.st_uid, owner.st_gid)
    temporary.replace(path)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Expected the host checkout path as the only argument")
    host_path = sys.argv[1]
    directory = Path("/config")
    if not (directory / "devcontainer.json").is_file():
        raise SystemExit(
            "The host devcontainer folder is missing; refusing an empty mount"
        )
    config = runtime_override(
        host_path,
        Path("/run/.containerenv").exists(),
        Path("/proc/self/uid_map").read_text(),
    )
    owner = directory.stat()
    write_owned(directory / "compose.runtime.yaml", config, owner)
    write_owned(
        directory / "workspace.local.json",
        {"id": workspace_identity(host_path), "host_path": host_path},
        owner,
    )
    print(f"Workspace on host: {host_path}")
    print(f"Isolated container project: {config['name']}")


if __name__ == "__main__":
    main()
