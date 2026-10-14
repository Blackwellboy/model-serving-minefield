"""Optional bounded raw HTTP execution context for framework-neutral callers.

No environment proxies, redirects, retries, credential discovery or model
fallback. A context is single-run; callers retain it to cancel and inspect usage.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class ExecutionStopped(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ExecutionStopped("REDIRECT_REJECTED")


_current = ContextVar("minefield_execution", default=None)


def checkpoint():
    control = _current.get()
    if control is not None:
        control.checkpoint()


def usage():
    control = _current.get()
    return (control.http, control.generations) if control else (0, 0)


def progress(probe_id, state):
    control = _current.get()
    if control and control.on_progress:
        control.on_progress({"probe_id": probe_id, "state": state,
                             "http": control.http, "generations": control.generations})


def verify_model(model):
    control = _current.get()
    if control and control.expected_model is not None and model != control.expected_model:
        raise ExecutionStopped("MODEL_DRIFT")


def open_request(request, timeout):
    control = _current.get()
    if control is None:
        return urllib.request.urlopen(request, timeout=timeout)
    return control.open(request, timeout)


class ExecutionControl:
    def __init__(self, *, origin, max_http, max_generations, timeout=10, deadline=30,
                 max_response_bytes=1048576, max_output_tokens=256, paths=(), requests=None, on_progress=None,
                 expected_model=None):
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("invalid origin")
        for value in (max_http, max_generations, max_response_bytes, max_output_tokens):
            if type(value) is not int or value < 0:
                raise ValueError("invalid execution ceiling")
        if not 0 < timeout <= deadline <= 300:
            raise ValueError("invalid timeout/deadline")
        self.origin = (parsed.scheme, parsed.hostname, parsed.port)
        self.paths = frozenset(paths)
        if not self.paths or any(not isinstance(p, str) or not p.startswith("/") for p in paths):
            raise ValueError("explicit allowed paths required")
        self.max_http, self.max_generations = max_http, max_generations
        self.max_response_bytes, self.max_output_tokens = max_response_bytes, max_output_tokens
        self.timeout, self.duration = timeout, deadline
        self.requests = json.loads(json.dumps(requests)) if requests is not None else None
        self._request_cursor = 0
        self.on_progress = on_progress
        self.expected_model = expected_model
        self.expires = None
        self.http = self.generations = 0
        self.cancelled = threading.Event()
        self._lock = threading.Lock()
        self._used = False
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def cancel(self):
        self.cancelled.set()

    def checkpoint(self):
        if self.cancelled.is_set():
            raise ExecutionStopped("CANCELLED")
        if self.expires is not None and time.monotonic() >= self.expires:
            raise ExecutionStopped("DEADLINE")

    @contextmanager
    def bind(self):
        with self._lock:
            if self._used:
                raise ValueError("execution control already used")
            self._used = True
            self.expires = time.monotonic() + self.duration
        token = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(token)

    def open(self, request, timeout):
        self.checkpoint()
        parsed = urlsplit(request.full_url)
        if ((parsed.scheme, parsed.hostname, parsed.port) != self.origin or
                parsed.path not in self.paths or parsed.query or parsed.fragment or
                parsed.username or parsed.password or request.get_method() not in {"GET", "POST"}):
            raise ExecutionStopped("DESTINATION_REJECTED")
        generation = parsed.path.endswith(("/chat/completions", "/completions"))
        actual_body = json.loads(request.data) if request.data is not None else None
        if generation:
            body = json.loads(request.data)
            cap = body.get("max_tokens")
            if type(cap) is not int or not 1 <= cap <= self.max_output_tokens:
                raise ExecutionStopped("OUTPUT_CAP_REJECTED")
        with self._lock:
            self.checkpoint()
            if self.requests is not None:
                actual = {"path": parsed.path, "method": request.get_method(), "body": actual_body}
                remaining = self.requests[self._request_cursor:]
                try:
                    index = remaining.index(actual)
                except ValueError:
                    raise ExecutionStopped("REQUEST_DRIFT") from None
                self._request_cursor += index + 1
            if self.http >= self.max_http or (generation and self.generations >= self.max_generations):
                raise ExecutionStopped("BUDGET_EXHAUSTED")
            self.http += 1
            self.generations += int(generation)
        timeout = min(timeout, self.timeout, max(0.001, self.expires - time.monotonic()))
        try:
            response = self._opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        return _BoundedResponse(response, self)


class _BoundedResponse:
    def __init__(self, response, control):
        self.response, self.control = response, control
        self.status = response.code
        self.remaining = control.max_response_bytes

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.response.close()

    def _read(self, method, size=-1):
        self.control.checkpoint()
        data = method(min(size, self.remaining + 1) if size >= 0 else self.remaining + 1)
        self.remaining -= len(data)
        self.control.checkpoint()
        if self.remaining < 0:
            raise ExecutionStopped("RESPONSE_LIMIT")
        return data

    def read(self, size=-1):
        return self._read(self.response.read, size)

    def __iter__(self):
        while True:
            line = self._read(self.response.readline)
            if not line:
                break
            yield line
