"""Serialize scraped entities to data/latest/ + a timestamped snapshot + manifest."""
import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

_DHAKA = ZoneInfo("Asia/Dhaka")


def _default(obj):
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"not serializable: {type(obj)!r}")


def _dump(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, default=_default, ensure_ascii=False, indent=2)


def write_all(entities: dict, out_root: str, source: str) -> dict:
    latest = os.path.join(out_root, "latest")
    os.makedirs(latest, exist_ok=True)
    # Snapshot dir name is filesystem-safe; scraped_at keeps Dhaka offset.
    now = datetime.now(_DHAKA)
    ts = now.strftime("%Y-%m-%dT%H-%M-%S%z")  # e.g. 2026-07-22T01-49-00+0600
    snap = os.path.join(out_root, "snapshots", ts)
    os.makedirs(snap, exist_ok=True)

    manifest = {"scraped_at": ts, "source": source, "entities": {}, "snapshot_dir": snap}
    for name, result in entities.items():
        if result.get("ok"):
            _dump(result["data"], os.path.join(latest, f"{name}.json"))
            _dump(result["data"], os.path.join(snap, f"{name}.json"))
        manifest["entities"][name] = {
            "count": result.get("count"),
            "source_url": result.get("source_url"),
            "ok": bool(result.get("ok")),
            "error": result.get("error"),
        }
    _dump(manifest, os.path.join(latest, "manifest.json"))
    _dump(manifest, os.path.join(snap, "manifest.json"))
    return manifest
