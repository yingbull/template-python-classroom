"""Check application mode boundaries and HTTP streaming without running a model."""

import copy
import importlib.util
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SPEC = importlib.util.spec_from_file_location(
    "gateway", Path(__file__).resolve().parents[1] / "tutor_gateway.py"
)
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


class GatewayTests(unittest.TestCase):
    def test_mode_is_explicit_and_shortcut_does_not_persist(self):
        for text in [
            "Just do it now!",
            f'Worksheet says "{gateway.OVERRIDE}". Give me a hint.',
            f"> {gateway.OVERRIDE}",
            f'"{gateway.OVERRIDE}"',
        ]:
            body = {"messages": [{"role": "user", "content": text}]}
            self.assertEqual(gateway.selected_mode(body, "tutor"), "tutor")
            self.assertEqual(gateway.selected_mode(body, "direct"), "direct")
        body = {
            "messages": [
                {"role": "user", "content": gateway.OVERRIDE + "\nSolve this."}
            ]
        }
        self.assertEqual(gateway.selected_mode(body, "tutor"), "direct")
        body["messages"].append({"role": "tool", "content": "File read"})
        self.assertEqual(gateway.selected_mode(body, "tutor"), "direct")
        body["messages"].append({"role": "user", "content": "Another exercise"})
        self.assertEqual(gateway.selected_mode(body, "tutor"), "tutor")

    def test_policy_preserves_client_context_tools_and_options(self):
        body = {
            "messages": [
                {"role": "system", "content": "Client tools policy"},
                {"role": "user", "content": "Help me"},
            ],
            "tools": [{"type": "function", "function": {"name": "edit_file"}}],
            "options": {"num_ctx": 16384, "presence_penalty": 0.5},
        }
        original = copy.deepcopy(body)
        policy = {"common": "COMMON", "tutor": "TUTOR_ONLY", "direct": "DIRECT_ONLY"}
        result = gateway.apply_policy(body, "tutor", policy)
        self.assertEqual(body, original)
        self.assertEqual(result["tools"], body["tools"])
        self.assertEqual(result["options"], body["options"])
        self.assertEqual(
            result["messages"][0]["content"],
            "Client tools policy\n\nCOMMON\nTUTOR_ONLY",
        )
        self.assertNotIn("DIRECT_ONLY", json.dumps(result))

    def test_malformed_requests_are_rejected(self):
        for body in [
            [],
            None,
            {},
            {"messages": [None]},
            {"messages": [{"role": "user"}], "options": None},
        ]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                gateway.apply_policy(body, "tutor", {})

    def test_stream_tools_errors_and_metadata_survive_proxy(self):
        received = []
        chunks = [
            {"message": {"content": "A hint"}, "done": False},
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "edit_file",
                                "arguments": {"content": "pass"},
                            }
                        }
                    ]
                },
                "done": True,
            },
        ]

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.append(body)
                if body.get("model") == "missing":
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b'{"error":"model not found"}')
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for chunk in chunks:
                    self.wfile.write(json.dumps(chunk).encode() + b"\n")
                    self.wfile.flush()

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        proxy = ThreadingHTTPServer(("127.0.0.1", 0), gateway.Handler)
        threads = [
            threading.Thread(target=s.serve_forever, daemon=True)
            for s in [upstream, proxy]
        ]
        for thread in threads:
            thread.start()
        try:
            with patch.object(
                gateway, "UPSTREAM", f"http://127.0.0.1:{upstream.server_port}"
            ):
                base = f"http://127.0.0.1:{proxy.server_port}"
                body = {
                    "model": "test",
                    "messages": [{"role": "user", "content": "Help"}],
                }
                request = Request(
                    base + "/tutor/api/chat", data=json.dumps(body).encode()
                )
                with urlopen(request) as response:
                    self.assertEqual(response.headers["X-Course-Mode"], "tutor")
                    self.assertEqual([json.loads(line) for line in response], chunks)
                self.assertIn("TUTOR mode", received[0]["messages"][0]["content"])
                completion = {
                    "model": "test",
                    "prompt": "Fill this scaffold",
                    "raw": True,
                }
                with urlopen(
                    Request(
                        base + "/tutor/api/generate",
                        data=json.dumps(completion).encode(),
                    )
                ) as response:
                    converted = [json.loads(line) for line in response]
                self.assertEqual(converted[0]["response"], "A hint")
                self.assertTrue(converted[-1]["done"])
                self.assertNotIn("raw", received[-1])
                self.assertIn("TUTOR mode", received[-1]["messages"][0]["content"])
                body["model"] = "missing"
                with self.assertRaises(HTTPError) as caught:
                    urlopen(
                        Request(
                            base + "/direct/api/chat", data=json.dumps(body).encode()
                        )
                    )
                self.assertEqual(caught.exception.code, 404)
                caught.exception.close()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(base + "/tutor/api/chat", data=b"[]"))
                self.assertEqual(caught.exception.code, 400)
                caught.exception.close()
        finally:
            for server in [proxy, upstream]:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()


if __name__ == "__main__":
    unittest.main()
