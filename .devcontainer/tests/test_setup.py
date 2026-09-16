"""Exercise provisioning without downloading models or changing the user's home."""

import importlib.util
import json
import tempfile
import threading
import unittest
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "course_setup", Path(__file__).resolve().parents[1] / "setup.py"
)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_config_install_is_idempotent_and_backs_up_edits(self):
        with tempfile.TemporaryDirectory(prefix="course with spaces ") as directory:
            home = Path(directory)
            with patch.object(setup.Path, "home", return_value=home):
                setup.install_config()
                setup.install_config()
                target = home / ".continue" / "config.yaml"
                self.assertEqual(target.read_bytes(), setup.CONFIG.read_bytes())
                self.assertEqual(list(target.parent.glob("*.backup-*")), [])
                target.write_text("name: Personal config\n")
                setup.install_config()
                backup = list(target.parent.glob("*.backup-*"))
                self.assertEqual(len(backup), 1)
                self.assertEqual(backup[0].read_text(), "name: Personal config\n")

    def test_models_match_course_config(self):
        self.assertIn("qwen3.5:4b", setup.models())
        self.assertIn("qwen3-vl:8b-instruct", setup.models())
        self.assertEqual(len(setup.models()), len(set(setup.models())))

    def test_http_provisioning_skips_existing_and_resumes_missing_models(self):
        installed = {setup.models()[0]}
        requested = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    json.dumps({"models": [{"name": m} for m in installed]}).encode()
                )

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                model = body["model"]
                requested.append(model)
                installed.add(model)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"pulling manifest"}\n')
                self.wfile.write(b'{"status":"success"}\n')

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(setup, "API", f"http://127.0.0.1:{server.server_port}"):
                with patch("sys.argv", ["setup.py", "check"]):
                    with self.assertRaisesRegex(RuntimeError, "setup.py pull"):
                        setup.main()
                with patch("sys.argv", ["setup.py", "pull"]):
                    setup.main()
                    setup.main()
                self.assertEqual(requested, setup.models()[1:])
                with patch("sys.argv", ["setup.py", "check"]):
                    setup.main()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_failed_or_truncated_download_is_not_reported_as_success(self):
        for payload in (
            [b'{"error":"model not found"}\n'],
            [b'{"status":"pulling manifest"}\n'],
        ):
            with patch.object(setup, "urlopen") as mock_open:
                mock_open.return_value.__enter__.return_value = payload
                with self.assertRaises(RuntimeError):
                    setup.pull_model("missing:4b")

    def test_transport_interruptions_are_retried(self):
        for error in (IncompleteRead(b"partial", 100), ConnectionResetError("reset")):
            with self.subTest(error=type(error).__name__):
                with (
                    patch.object(setup, "models", return_value=["test:4b"]),
                    patch.object(setup, "wait_for_ollama", return_value=set()),
                    patch.object(setup, "installed_models", return_value={"test:4b"}),
                    patch.object(
                        setup, "pull_model", side_effect=[error, None]
                    ) as pull,
                    patch.object(setup.time, "sleep"),
                    patch("sys.argv", ["setup.py", "pull"]),
                ):
                    setup.main()
                    self.assertEqual(pull.call_count, 2)


if __name__ == "__main__":
    unittest.main()
