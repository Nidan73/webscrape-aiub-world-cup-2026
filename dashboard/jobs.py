"""Single-flight background refresh: run scraper + projection off the request thread."""
import subprocess
import sys
import threading
import time


class RefreshJob:
    def __init__(self, runner=None):
        self._runner = runner or self._default_runner
        self._lock = threading.Lock()
        self._thread = None
        self._state = "idle"
        self._started_at = None
        self._finished_at = None
        self._error = None

    @staticmethod
    def _default_runner():
        subprocess.run([sys.executable, "-m", "scraper.run"], check=True)
        subprocess.run([sys.executable, "-m", "projection.run"], check=True)

    def start(self):
        with self._lock:
            if self._state == "running":
                return False
            self._state = "running"
            self._started_at = time.time()
            self._finished_at = None
            self._error = None
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            return True

    def _run(self):
        try:
            self._runner()
            state, error = "done", None
        except Exception as exc:
            state, error = "error", str(exc)
        with self._lock:
            self._state = state
            self._error = error
            self._finished_at = time.time()

    def status(self):
        with self._lock:
            return {"state": self._state, "started_at": self._started_at,
                    "finished_at": self._finished_at, "error": self._error}
