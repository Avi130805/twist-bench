"""
agent_bridge.py — loopback control channel for the live simulation.

A newline-delimited JSON socket bound to 127.0.0.1 only: nothing leaves the
machine, so the benchmark stays airgapped. Client threads park on their request
until the render loop has actually executed it, so every reply describes real
on-screen state rather than a queued intention.
"""

import json
import queue
import socket
import threading

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8181


class Request:
    """One command in flight, owned by a client thread, executed by the app."""

    __slots__ = ("payload", "result", "_event")

    def __init__(self, payload: dict):
        self.payload = payload
        self.result = None
        self._event = threading.Event()

    @property
    def cmd(self) -> str:
        return str(self.payload.get("cmd", "")).lower()

    def get(self, key, default=None):
        return self.payload.get(key, default)

    def complete(self, result: dict):
        if not self._event.is_set():
            self.result = result
            self._event.set()

    def fail(self, message: str):
        self.complete({"ok": False, "error": message})

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)


class AgentBridge:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, log=print):
        self.host = host
        self.port = port
        self.log = log
        self.requests: "queue.Queue[Request]" = queue.Queue()
        self.clients = 0
        self._sock = None
        self._running = False

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(8)
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self.log(f"[bridge] listening on {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def _accept_loop(self):
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._client_loop, args=(conn,), daemon=True).start()

    def _client_loop(self, conn: socket.socket):
        self.clients += 1
        try:
            stream = conn.makefile("rwb")
            for raw in stream:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise ValueError("payload must be a JSON object")
                except Exception as exc:
                    self._send(stream, {"ok": False, "error": f"bad request: {exc}"})
                    continue

                req = Request(payload)
                timeout = float(payload.get("timeout", 120))
                self.requests.put(req)
                if req.wait(timeout):
                    self._send(stream, req.result)
                else:
                    req.complete({"ok": False, "error": "timeout"})
                    self._send(stream, {"ok": False, "error": "timeout"})
        except OSError:
            pass
        finally:
            self.clients -= 1
            try:
                conn.close()
            except OSError:
                pass

    @staticmethod
    def _send(stream, obj):
        stream.write((json.dumps(obj) + "\n").encode("utf-8"))
        stream.flush()

    def poll(self) -> list:
        """Drain everything that arrived since the last frame."""
        out = []
        while True:
            try:
                out.append(self.requests.get_nowait())
            except queue.Empty:
                return out
