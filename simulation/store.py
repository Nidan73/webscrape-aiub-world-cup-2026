"""Server-side JSON persistence for simulator state and history."""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

_DEFAULT_CURRENT = {
    "whatif": {"groups": {}, "ko": {}},
    "mc": {"n": 1000, "bias": 0.0, "use_current_picks": True},
}
_AUTO_CAP = 50
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_HISTORY_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


class SimStore:
    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        self.history_dir = self.root / "history"
        self._lock_path = self.root / "store.lock"
        self._lock = threading.Lock()
        self.ensure()

    @contextmanager
    def _store_lock(self):
        """Thread lock plus fcntl flock for cross-process read-modify-write."""
        with self._lock:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_fd = open(self._lock_path, "a")
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()

    def _history_path(self, id: str) -> Path | None:
        if not id or not _HISTORY_ID_RE.match(id):
            return None
        path = (self.history_dir / f"{id}.json").resolve()
        history_resolved = self.history_dir.resolve()
        if not path.is_relative_to(history_resolved):
            return None
        return path

    def _ensure_body(self) -> None:
        """Create dirs and default files. Caller must hold _store_lock()."""
        self.history_dir.mkdir(parents=True, exist_ok=True)
        if not (self.root / "ratings.json").exists():
            self._atomic_write(self.root / "ratings.json", {})
        if not (self.root / "current.json").exists():
            self._atomic_write(self.root / "current.json", _DEFAULT_CURRENT)
        if not (self.root / "index.json").exists():
            self._atomic_write(self.root / "index.json", [])

    def ensure(self) -> None:
        with self._store_lock():
            self._ensure_body()

    def _atomic_write(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _read(self, path: Path, default):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return default

    def get_ratings(self) -> dict:
        with self._store_lock():
            self._ensure_body()
            data = self._read(self.root / "ratings.json", {})
            return data if isinstance(data, dict) else {}

    def put_ratings(self, data: dict) -> dict:
        with self._store_lock():
            self._ensure_body()
            clean = {str(k): float(v) for k, v in (data or {}).items()}
            self._atomic_write(self.root / "ratings.json", clean)
            return clean

    def get_current(self) -> dict:
        with self._store_lock():
            self._ensure_body()
            data = self._read(self.root / "current.json", _DEFAULT_CURRENT)
            if not isinstance(data, dict):
                return json.loads(json.dumps(_DEFAULT_CURRENT))
            data.setdefault("whatif", {"groups": {}, "ko": {}})
            data["whatif"].setdefault("groups", {})
            data["whatif"].setdefault("ko", {})
            data.setdefault("mc", dict(_DEFAULT_CURRENT["mc"]))
            return data

    def put_current(self, data: dict) -> dict:
        with self._store_lock():
            self._ensure_body()
            cur = {
                "whatif": (data or {}).get("whatif") or {"groups": {}, "ko": {}},
                "mc": {**_DEFAULT_CURRENT["mc"], **((data or {}).get("mc") or {})},
            }
            self._atomic_write(self.root / "current.json", cur)
            return cur

    def list_history(self) -> list:
        with self._store_lock():
            self._ensure_body()
            idx = self._read(self.root / "index.json", [])
            return idx if isinstance(idx, list) else []

    def _slug(self, title: str) -> str:
        s = _SLUG_RE.sub("-", (title or "scenario").lower()).strip("-") or "scenario"
        return s[:40]

    def save_history(self, *, type: str, title: str, payload: dict, team_id: str | None = None) -> dict:
        if type not in ("auto", "named"):
            raise ValueError("type must be auto or named")
        with self._store_lock():
            self._ensure_body()
            ts = time.strftime("%Y%m%d-%H%M%S")
            hid = f"{type}-{ts}-{uuid.uuid4().hex[:8]}"
            entry = {
                "id": hid,
                "type": type,
                "title": title or hid,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "team_id": team_id,
                "ratings": (payload or {}).get("ratings") or {},
                "whatif": (payload or {}).get("whatif") or {"groups": {}, "ko": {}},
                "mc": (payload or {}).get("mc") or dict(_DEFAULT_CURRENT["mc"]),
            }
            if "mc_summary" in (payload or {}):
                entry["mc_summary"] = payload["mc_summary"]
            fname = f"{hid}.json" if type == "auto" else f"named-{self._slug(title)}-{uuid.uuid4().hex[:6]}.json"
            # keep id as filename stem for lookup
            if type == "named":
                hid = Path(fname).stem
                entry["id"] = hid
            path = self.history_dir / f"{entry['id']}.json"
            self._atomic_write(path, entry)
            idx = self._read(self.root / "index.json", [])
            if not isinstance(idx, list):
                idx = []
            meta = {k: entry[k] for k in ("id", "type", "title", "created_at", "team_id")}
            idx.insert(0, meta)
            # cap autos
            autos = [h for h in idx if h.get("type") == "auto"]
            drop = autos[_AUTO_CAP:]
            drop_ids = {h["id"] for h in drop}
            idx = [h for h in idx if h["id"] not in drop_ids]
            for did in drop_ids:
                p = self.history_dir / f"{did}.json"
                if p.exists():
                    p.unlink()
            self._atomic_write(self.root / "index.json", idx)
            return entry

    def get_history(self, id: str):
        with self._store_lock():
            path = self._history_path(id)
            if path is None or not path.exists():
                return None
            data = self._read(path, None)
            return data if isinstance(data, dict) else None

    def restore(self, id: str) -> dict:
        with self._store_lock():
            path = self._history_path(id)
            if path is None:
                raise ValueError(f"invalid history id: {id!r}")
            data = self._read(path, None)
            if not isinstance(data, dict):
                raise KeyError(id)
            ratings = data.get("ratings") or {}
            current = {
                "whatif": data.get("whatif") or {"groups": {}, "ko": {}},
                "mc": {**_DEFAULT_CURRENT["mc"], **(data.get("mc") or {})},
            }
            self._atomic_write(self.root / "ratings.json", ratings)
            self._atomic_write(self.root / "current.json", current)
            return data

    def rename(self, id: str, title: str) -> dict:
        with self._store_lock():
            path = self._history_path(id)
            if path is None:
                raise ValueError(f"invalid history id: {id!r}")
            data = self._read(path, None)
            if not isinstance(data, dict):
                raise KeyError(id)
            data["title"] = title
            self._atomic_write(path, data)
            idx = self._read(self.root / "index.json", [])
            for h in idx if isinstance(idx, list) else []:
                if h.get("id") == id:
                    h["title"] = title
            self._atomic_write(self.root / "index.json", idx if isinstance(idx, list) else [])
            return data

    def delete(self, id: str) -> bool:
        with self._store_lock():
            path = self._history_path(id)
            if path is None or not path.exists():
                return False
            path.unlink()
            idx = self._read(self.root / "index.json", [])
            idx = [h for h in (idx if isinstance(idx, list) else []) if h.get("id") != id]
            self._atomic_write(self.root / "index.json", idx)
            return True
