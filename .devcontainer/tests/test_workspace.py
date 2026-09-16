"""Protect saved coursework across engines, differently named assignments, and clones."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / ".devcontainer" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load("configure_runtime")
workspace = load("workspace")


class RuntimeTests(unittest.TestCase):
    def test_each_checkout_has_a_distinct_stable_project(self):
        paths = [
            "/home/student/demo",
            "/home/student/assignment1",
            "/other/student/demo",
            "/Users/Student Name/demo",
            r"C:\Users\Student Name\demo",
        ]
        identities = [runtime.workspace_identity(p) for p in paths]
        self.assertEqual(len(identities), len(set(identities)))
        for path in paths:
            first = runtime.runtime_override(path, False, "0 0 4294967295\n")
            self.assertEqual(
                first, runtime.runtime_override(path, False, "0 0 4294967295\n")
            )
            self.assertRegex(first["name"], r"^classroom[0-9a-f]{20}$")
            self.assertEqual(
                first["services"]["python"]["environment"]["CLASSROOM_WORKSPACE_ID"],
                runtime.workspace_identity(path),
            )

    def test_windows_spelling_and_trailing_slash_are_normalized(self):
        self.assertEqual(
            runtime.workspace_identity(r"C:\Users\Student\demo"),
            runtime.workspace_identity("c:/users/student/demo/"),
        )

    def test_podman_keep_id_only_for_rootless_podman(self):
        for podman, uid_map, expected in [
            (True, "0 1000 1\n1 100000 65536\n", True),
            (True, "0 0 4294967295\n", False),
            (False, "0 1000 1\n", False),
        ]:
            options = runtime.runtime_override("/repo", podman, uid_map)["services"][
                "python"
            ]
            self.assertEqual("userns_mode" in options, expected)


class WorkspaceTests(unittest.TestCase):
    def test_mount_must_be_the_workspace_not_its_parent(self):
        mountinfo = "21 20 0:40 / / rw - overlay overlay rw\n22 21 0:50 /repo /workspace rw - ext4 /dev/sda rw\n"
        self.assertTrue(workspace.mounted_at(PurePosixPath("/workspace"), mountinfo))
        self.assertFalse(
            workspace.mounted_at(PurePosixPath("/workspace/assignment"), mountinfo)
        )
        self.assertFalse(workspace.mounted_at(PurePosixPath("/home/vscode"), mountinfo))

    def test_mount_paths_with_spaces(self):
        self.assertTrue(
            workspace.mounted_at(
                PurePosixPath("/workspace with spaces"),
                r"22 21 0:50 /repo /workspace\040with\040spaces rw - ext4 /dev/sda rw",
            )
        )

    def test_wrong_checkout_is_rejected_before_git_or_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".devcontainer").mkdir()
            (root / ".devcontainer/workspace.local.json").write_text(
                json.dumps({"id": "one", "host_path": "/host/one"})
            )
            with (
                patch.dict(os.environ, {"CLASSROOM_WORKSPACE_ID": "two"}),
                patch.object(workspace.subprocess, "run") as git,
            ):
                with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                    workspace.check(root)
            git.assert_not_called()

    def test_valid_mount_reports_untracked_student_work(self):
        with tempfile.TemporaryDirectory(prefix="classroom space ") as directory:
            root = Path(directory)
            (root / ".devcontainer").mkdir()
            (root / ".devcontainer/workspace.local.json").write_text(
                json.dumps({"id": "one", "host_path": "/host/one"})
            )
            result = subprocess.CompletedProcess([], 0, "?? homework.py\n", "")
            real_read = Path.read_text

            def read(path, *args, **kwargs):
                if path == Path("/proc/self/mountinfo"):
                    escaped = str(root).replace("\\", r"\134").replace(" ", r"\040")
                    return f"22 21 0:50 /repo {escaped} rw - ext4 /dev/sda rw\n"
                return real_read(path, *args, **kwargs)

            output = io.StringIO()
            with (
                patch.dict(os.environ, {"CLASSROOM_WORKSPACE_ID": "one"}),
                patch.object(Path, "read_text", read),
                patch.object(workspace.subprocess, "run", return_value=result),
                contextlib.redirect_stdout(output),
            ):
                workspace.check(root)
            self.assertIn("/host/one", output.getvalue())
            self.assertIn("homework.py", output.getvalue())

    def test_devcontainer_keeps_sources_at_root_and_does_not_download_models(self):
        config = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
        self.assertEqual(config["workspaceFolder"], "/workspace")
        self.assertEqual(
            config["dockerComposeFile"], ["compose.runtime.yaml", "compose.yaml"]
        )
        self.assertIn("${localWorkspaceFolder}", config["initializeCommand"])
        self.assertNotIn("pull", config["postStartCommand"])
        self.assertIn("workspace.py check", config["postStartCommand"])
        settings = json.loads((ROOT / ".vscode/settings.json").read_text())
        self.assertEqual(settings["files.autoSave"], "afterDelay")


if __name__ == "__main__":
    unittest.main()
