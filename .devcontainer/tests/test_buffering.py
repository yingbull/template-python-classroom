"""Real socket tests for checked HTTP delivery, cancellation and time budgets."""

import http.client
import json
import sys
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tutor_gateway as gateway
from test_checks import answer, call, tool


class QuietGateway(gateway.Handler):
    def log_message(self, *_args):
        pass


@contextmanager
def servers(handler):
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    proxy = ThreadingHTTPServer(("127.0.0.1", 0), QuietGateway)
    threads = [
        threading.Thread(target=s.serve_forever, daemon=True) for s in [upstream, proxy]
    ]
    for thread in threads:
        thread.start()
    try:
        with patch.object(
            gateway, "UPSTREAM", f"http://127.0.0.1:{upstream.server_port}"
        ):
            yield proxy
    finally:
        for server in [proxy, upstream]:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join()


def body(stream=True):
    return {
        "model": gateway.GEMMA,
        "messages": [{"role": "user", "content": "Help me start"}],
        "tools": [tool()],
        "stream": stream,
    }


class BufferingTests(unittest.TestCase):
    def test_no_draft_bytes_or_tools_escape_and_repair_keeps_mode(self):
        entered, release, received = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )
        requests, output, failures = [], [], []

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                request = json.loads(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )
                requests.append(request)
                if len(requests) == 1:
                    entered.set()
                    release.wait(2)
                    result = answer("I have updated exercise.py.")
                else:
                    result = answer("I will add a scaffold.", calls=[call()])
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

        with servers(Upstream) as proxy:

            def client():
                connection = http.client.HTTPConnection(
                    "127.0.0.1", proxy.server_port, timeout=4
                )
                try:
                    connection.request("POST", "/tutor/api/chat", json.dumps(body()))
                    response = connection.getresponse()
                    received.set()
                    output.extend(
                        [
                            response.status,
                            dict(response.headers),
                            response.read().decode(),
                        ]
                    )
                except Exception as error:
                    failures.append(error)
                finally:
                    connection.close()

            client_thread = threading.Thread(target=client)
            client_thread.start()
            self.assertTrue(entered.wait(2))
            self.assertFalse(
                received.wait(0.1), "Headers/draft were released before validation"
            )
            release.set()
            client_thread.join(4)
            self.assertFalse(failures)
            self.assertEqual(output[0], 200)
            self.assertEqual(output[1]["X-Course-Repairs"], "1")
            self.assertNotIn("I have updated", output[2])
            chunks = [json.loads(line) for line in output[2].splitlines()]
            self.assertEqual(len(chunks), 2)
            self.assertEqual(chunks[0]["message"]["tool_calls"], [call()])
            self.assertTrue(chunks[-1]["done"])
            self.assertNotIn("tool_calls", chunks[-1]["message"])
            self.assertEqual(len(requests), 2)
            self.assertFalse(requests[0]["stream"])
            self.assertIn("remains TUTOR", requests[1]["messages"][-1]["content"])

    def test_second_bad_reply_is_withheld(self):
        requests = []

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                requests.append(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        answer("REJECTED DRAFT", calls=[call(name="invented")])
                    ).encode()
                )

        with servers(Upstream) as proxy:
            connection = http.client.HTTPConnection(
                "127.0.0.1", proxy.server_port, timeout=4
            )
            connection.request("POST", "/tutor/api/chat", json.dumps(body(False)))
            response = connection.getresponse()
            text = response.read().decode()
            connection.close()
            self.assertEqual(response.status, 502)
            self.assertNotIn("REJECTED DRAFT", text)
            self.assertNotIn("tool_calls", text)
            self.assertEqual(len(requests), 2)

    def test_json_and_legacy_completion_and_shortcut(self):
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    json.dumps(answer("A clear conceptual answer.")).encode()
                )

        with servers(Upstream) as proxy:
            for endpoint, payload in [
                ("chat", body(False)),
                (
                    "generate",
                    {
                        "model": gateway.GEMMA,
                        "prompt": "Explain return",
                        "raw": True,
                        "stream": False,
                    },
                ),
            ]:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", proxy.server_port, timeout=4
                )
                connection.request(
                    "POST", f"/direct/api/{endpoint}", json.dumps(payload)
                )
                response = connection.getresponse()
                result = json.load(response)
                connection.close()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-Course-Mode"], "direct")
                self.assertIn("message" if endpoint == "chat" else "response", result)
                self.assertTrue(result["done"])
            payload = body(False)
            payload["messages"][0]["content"] = (
                gateway.OVERRIDE.upper() + "\nExplain this."
            )
            connection = http.client.HTTPConnection(
                "127.0.0.1", proxy.server_port, timeout=4
            )
            connection.request("POST", "/tutor/api/chat", json.dumps(payload))
            response = connection.getresponse()
            response.read()
            connection.close()
            self.assertEqual(response.headers["X-Course-Mode"], "direct")

    def test_deadline_and_disconnect_close_upstream_without_retry(self):
        for cancel in [False, True]:
            entered, closed = threading.Event(), threading.Event()
            calls = []

            class Upstream(BaseHTTPRequestHandler):
                def log_message(self, *_args):
                    pass

                def do_POST(self):
                    self.rfile.read(int(self.headers["Content-Length"]))
                    calls.append(1)
                    entered.set()
                    self.connection.settimeout(3)
                    if self.connection.recv(1) == b"":
                        closed.set()

            with (
                self.subTest(cancel=cancel),
                servers(Upstream) as proxy,
                patch.object(gateway, "DEADLINE_SECONDS", 0.4),
            ):
                connection = http.client.HTTPConnection(
                    "127.0.0.1", proxy.server_port, timeout=3
                )
                connection.request("POST", "/tutor/api/chat", json.dumps(body()))
                self.assertTrue(entered.wait(2))
                if cancel:
                    connection.close()
                else:
                    response = connection.getresponse()
                    response.read()
                    self.assertEqual(response.status, 504)
                    connection.close()
                self.assertTrue(
                    closed.wait(2),
                    "Upstream was left generating after cancellation/deadline",
                )
                self.assertEqual(len(calls), 1)

    def test_upstream_error_and_client_schema_error(self):
        calls = []

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                calls.append(self.rfile.read(int(self.headers["Content-Length"])))
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error":"model missing"}')

        with servers(Upstream) as proxy:
            for malformed in [False, True]:
                payload = body(False)
                if malformed:
                    payload["tools"][0]["function"]["parameters"] = {
                        "type": "not-a-type"
                    }
                connection = http.client.HTTPConnection(
                    "127.0.0.1", proxy.server_port, timeout=4
                )
                connection.request("POST", "/tutor/api/chat", json.dumps(payload))
                response = connection.getresponse()
                result = json.load(response)
                connection.close()
                self.assertEqual(response.status, 400 if malformed else 404)
                self.assertIn("error", result)
            self.assertEqual(
                len(calls), 1, "Invalid client schemas must not start inference"
            )


if __name__ == "__main__":
    unittest.main()
