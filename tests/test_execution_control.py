import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from minefield.api import plan_checks, run_checks
from minefield.execution import ExecutionControl, ExecutionStopped


@pytest.fixture
def endpoint():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/models")
                self.end_headers()
                return
            self.send_response(200 if self.path == "/v1/models" else 404)
            self.end_headers()
            self.wfile.write(json.dumps({"data": [{"id": "fixture"}]}).encode())

        def do_POST(self):
            calls.append(self.path)
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"synthetic rejection"}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def control(base, **kwargs):
    return ExecutionControl(origin=base, max_http=kwargs.pop("max_http", 5),
        max_generations=1, paths=("/v1/models", "/api/version", "/props", "/version",
                                  "/v1/chat/completions", "/redirect"), **kwargs)


def test_actual_discovery_counts_and_hard_ceiling(endpoint):
    base, calls = endpoint
    plan = plan_checks(base_url=base + "/v1", model="fixture", detect=False, max_requests=1)
    guard = control(base, max_http=2)
    result = run_checks(plan, execution=guard)
    assert len(calls) == result.http_requests_executed == 2
    assert result.error == "BUDGET_EXHAUSTED"
    assert result.wire_generations_executed == 0
    assert not result.findings


def test_cancel_and_redirect_never_follow(endpoint):
    base, calls = endpoint
    guard = control(base)
    with guard.bind():
        with pytest.raises(ExecutionStopped, match="REDIRECT_REJECTED"):
            guard.open(urllib.request.Request(base + "/redirect"), 1)
        guard.cancel()
        with pytest.raises(ExecutionStopped, match="CANCELLED"):
            guard.open(urllib.request.Request(base + "/v1/models"), 1)
    assert calls == ["/redirect"]
    with pytest.raises(ValueError, match="already used"):
        with guard.bind():
            pass


def test_wrong_origin_output_cap_and_bool_budget_rejected(endpoint):
    base, calls = endpoint
    with pytest.raises(ValueError):
        control(base, max_http=True)
    guard = control(base)
    with guard.bind():
        with pytest.raises(ExecutionStopped, match="DESTINATION_REJECTED"):
            guard.open(urllib.request.Request("http://192.0.2.1/v1/models"), 1)
        with pytest.raises(ExecutionStopped, match="OUTPUT_CAP_REJECTED"):
            guard.open(urllib.request.Request(base + "/v1/chat/completions", b'{"max_tokens":9999}'), 1)
    assert calls == []
