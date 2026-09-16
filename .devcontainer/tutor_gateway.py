"""Local Ollama adapter: select tutor/direct policy outside the language model."""

import copy
import http.client
import json
import os
import queue
import re
import select
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import yaml
from tutor_checks import (
    DEADLINE_SECONDS,
    GEMMA,
    CheckFailure,
    checked_response,
    request_facts,
    tool_validators,
)

POLICY = Path(__file__).with_name("tutor_policy.yaml")
UPSTREAM = os.environ.get("OLLAMA_HOST", "http://ollama:11434").rstrip("/")
OVERRIDE = "Override tutor mode: give me the complete solution"


def selected_mode(body, mode):
    """A literal first-line shortcut applies only to the latest user turn."""
    if mode not in {"tutor", "direct"}:
        raise ValueError("Choose tutor or direct")
    if not isinstance(body, dict):
        raise ValueError("Expected a JSON object")
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("A nonempty messages array is required")
    if any(not isinstance(message, dict) for message in messages):
        raise ValueError("Each message must be an object")
    if mode == "direct":
        return mode
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, str) and content.strip():
                first_line = content.strip().splitlines()[0]

                def normalize(value):
                    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

                # Do not interpret quotes, Markdown blocks, embedded text or urgency.
                if first_line[:1].isalnum() and normalize(first_line) == normalize(
                    OVERRIDE
                ):
                    return "direct"
            break
    return "tutor"


def apply_policy(body, mode, policy, *, include_facts=True):
    """Preserve client instructions/tools; add only the explicitly selected policy."""
    mode = selected_mode(body, mode)
    result = copy.deepcopy(body)
    messages = result.get("messages")
    if not isinstance(result.get("options", {}), dict):
        raise ValueError("options must be an object")
    instructions = policy["common"] + "\n" + policy[mode]
    if include_facts and body.get("model") == GEMMA:
        instructions += "\n\n" + request_facts(body, mode)
    if messages[0].get("role") == "system":
        messages[0]["content"] = messages[0].get("content", "") + "\n\n" + instructions
    else:
        messages.insert(0, {"role": "system", "content": instructions})
    # Continue's Ollama adapter does not forward every sampling option.
    result.setdefault("options", {}).setdefault("presence_penalty", 0)
    return result


class UpstreamError(Exception):
    def __init__(self, status, payload):
        self.status, self.payload = status, payload


def buffered_invoke(base, body, deadline, cancelled=lambda: False):
    """Read one Ollama JSON reply with a total deadline and cancellable socket."""
    endpoint = urlsplit(base)
    if endpoint.scheme not in {"http", "https"}:
        raise ValueError("Ollama endpoint must use HTTP or HTTPS")
    connection_type = (
        http.client.HTTPSConnection
        if endpoint.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(
        endpoint.hostname, endpoint.port, timeout=max(0.1, deadline - time.monotonic())
    )
    stopped = threading.Event()
    completed = queue.Queue(maxsize=1)
    state_lock = threading.Lock()
    active_socket = [None]

    def close():
        stopped.set()
        with state_lock:
            if active_socket[0]:
                try:
                    active_socket[0].shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                active_socket[0].close()
                active_socket[0] = None
        connection.close()

    def worker():
        try:
            connection.connect()
            with state_lock:
                if stopped.is_set():
                    return
                # SSLSocket cannot be duplicated. Keep its object alive so
                # shutdown also interrupts a response-owned TLS socket.
                active_socket[0] = (
                    connection.sock
                    if isinstance(connection.sock, ssl.SSLSocket)
                    else connection.sock.dup()
                )
            connection.request(
                "POST",
                endpoint.path.rstrip("/") + "/api/chat",
                body=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("Ollama reply exceeds 8 MiB")
            if response.status != 200:
                raise UpstreamError(response.status, data)
            completed.put((json.loads(data), None))
        except Exception as error:
            completed.put(
                (
                    None,
                    URLError(error)
                    if isinstance(error, OSError)
                    and not isinstance(error, TimeoutError)
                    else error,
                )
            )
        finally:
            connection.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        while True:
            if cancelled():
                raise ConnectionAbortedError("Client disconnected")
            if time.monotonic() >= deadline:
                raise TimeoutError("The checked answer exceeded its time limit")
            try:
                result, error = completed.get(
                    timeout=min(0.05, max(0.001, deadline - time.monotonic()))
                )
            except queue.Empty:
                continue
            if error:
                raise error
            return result
    finally:
        close()
        thread.join(timeout=0.1)


class Handler(BaseHTTPRequestHandler):
    def client_cancelled(self):
        readable, _, _ = select.select([self.connection], [], [], 0)
        if not readable:
            return False
        try:
            return self.connection.recv(1, socket.MSG_PEEK) == b""
        except OSError:
            return True

    def checked(self, body, mode, translate):
        tool_validators(body)
        started = time.monotonic()
        attempts = []

        def record(attempt, _answer, issues):
            attempts.append([issue.code for issue in issues])

        try:
            result, repairs = checked_response(
                body,
                mode,
                lambda request, deadline: buffered_invoke(
                    UPSTREAM, request, deadline, self.client_cancelled
                ),
                deadline=started + DEADLINE_SECONDS,
                on_attempt=record,
            )
        finally:
            # Operational metadata only: never log prompts, drafts or tool arguments.
            print(
                json.dumps(
                    {
                        "event": "course_check",
                        "mode": mode,
                        "seconds": round(time.monotonic() - started, 3),
                        "checks": attempts,
                    }
                ),
                flush=True,
            )
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/x-ndjson" if body.get("stream", True) else "application/json",
        )
        self.send_header("X-Course-Mode", mode)
        self.send_header("X-Course-Repairs", str(repairs))
        self.send_header("Connection", "close")
        self.end_headers()
        message = result["message"]
        if body.get("stream", True):
            # One accepted message event, then the terminal event. Do not replay
            # token timing or leak any rejected draft or proposed action.
            first = {
                key: result[key] for key in ["model", "created_at"] if key in result
            }
            first["done"] = False
            first["response" if translate else "message"] = (
                message.get("content", "") if translate else message
            )
            self.wfile.write(json.dumps(first).encode() + b"\n")
            result = {key: value for key, value in result.items() if key != "message"}
            result["response" if translate else "message"] = (
                "" if translate else {"role": "assistant", "content": ""}
            )
        elif translate:
            result = dict(result)
            result["response"] = result.pop("message").get("content", "")
        self.wfile.write(json.dumps(result).encode() + b"\n")
        self.wfile.flush()

    def send_json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        headers_sent = False
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
            return
        pieces = self.path.split("/", 2)
        if len(pieces) != 3 or pieces[1] not in {"tutor", "direct"}:
            self.send_json(404, {"error": "Use /tutor/ or /direct/ as the API base"})
            return
        mode, endpoint = pieces[1:]
        allowed = {
            "api/chat",
            "api/generate",
            "api/show",
            "api/tags",
            "api/ps",
            "api/version",
        }
        if endpoint not in allowed:
            self.send_json(
                404, {"error": "Endpoint not supported by the tutor adapter"}
            )
            return
        try:
            data = None
            translate = endpoint == "api/generate"
            if self.command == "POST":
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 32 * 1024 * 1024:
                    raise ValueError("Expected a JSON request smaller than 32 MiB")
                data = self.rfile.read(size)
                if endpoint in {"api/chat", "api/generate"}:
                    policy = yaml.safe_load(POLICY.read_text())
                    body = json.loads(data)
                    if translate:
                        # Continue's completion/Edit path may use generate. Send
                        # it through chat so raw=true cannot bypass the policy.
                        # FIM autocomplete has a separate direct Ollama entry.
                        if not isinstance(body, dict) or not isinstance(
                            body.get("prompt"), str
                        ):
                            raise ValueError("A text prompt is required")
                        if body.get("suffix") or body.get("context"):
                            raise ValueError(
                                "Use the autocomplete endpoint for FIM/legacy context"
                            )
                        prompt = body.pop("prompt")
                        system = body.pop("system", "")
                        for key in ["raw", "template", "suffix", "context"]:
                            body.pop(key, None)
                        body["messages"] = [{"role": "user", "content": prompt}]
                        if system:
                            body["messages"].insert(
                                0, {"role": "system", "content": system}
                            )
                        if "images" in body:
                            body["messages"][-1]["images"] = body.pop("images")
                        body.setdefault("think", False)
                        endpoint = "api/chat"
                    mode = selected_mode(body, mode)
                    body = apply_policy(body, mode, policy)
                    if body.get("model") == GEMMA:
                        self.checked(body, mode, translate)
                        return
                    data = json.dumps(body).encode()
            request = Request(
                UPSTREAM + "/" + endpoint,
                data=data,
                method=self.command,
                headers={"Content-Type": "application/json"},
            )
            try:
                response = urlopen(request, timeout=600)
            except HTTPError as error:
                response = error
            with response:
                self.send_response(response.status)
                self.send_header(
                    "Content-Type",
                    response.headers.get("Content-Type", "application/json"),
                )
                self.send_header("X-Course-Mode", mode)
                self.send_header("Connection", "close")
                self.end_headers()
                headers_sent = True
                for line in response:
                    if translate and response.status == 200:
                        chunk = json.loads(line)
                        message = chunk.pop("message", {})
                        chunk["response"] = message.get("content", "")
                        line = json.dumps(chunk).encode() + b"\n"
                    self.wfile.write(line)
                    self.wfile.flush()
        except CheckFailure as error:
            self.send_json(
                502,
                {"error": str(error), "checks": [issue.code for issue in error.issues]},
            )
        except UpstreamError as error:
            self.send_json(
                error.status,
                {
                    "error": "Ollama rejected the request",
                    "detail": error.payload.decode(errors="replace"),
                },
            )
        except ConnectionAbortedError:
            pass
        except TimeoutError:
            if not headers_sent:
                self.send_json(
                    504,
                    {
                        "error": "The checked answer exceeded its time limit. No proposed tools were released."
                    },
                )
        except (ValueError, TypeError, KeyError) as error:
            if not headers_sent:
                self.send_json(400, {"error": str(error)})
        except (URLError, http.client.HTTPException) as error:
            if not headers_sent:
                self.send_json(502, {"error": str(error)})
            # After streaming starts, close the incomplete response. Never send
            # a second HTTP response or fabricate a successful done event.
        except (BrokenPipeError, ConnectionResetError):
            pass  # Closing the upstream response also cancels generation.


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 11435), Handler).serve_forever()
