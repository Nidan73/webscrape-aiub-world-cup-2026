"""Cached read access to the scraped data/latest JSON files."""
import json
import os


class DataStore:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self._cache = {}
        self._stamp = object()      # sentinel != any mtime

    def _manifest_mtime(self):
        try:
            return os.path.getmtime(os.path.join(self.data_dir, "manifest.json"))
        except OSError:
            return None

    def _get(self, name, default):
        stamp = self._manifest_mtime()
        if stamp != self._stamp:
            self._cache.clear()
            self._stamp = stamp
        if name not in self._cache:
            try:
                with open(os.path.join(self.data_dir, f"{name}.json"), encoding="utf-8") as fh:
                    self._cache[name] = json.load(fh)
            except (OSError, json.JSONDecodeError):
                self._cache[name] = default
        return self._cache[name]

    def teams(self):        return self._get("teams", [])
    def rosters(self):      return self._get("rosters", [])
    def fixtures(self):     return self._get("fixtures", [])
    def standings(self):    return self._get("standings", [])
    def bracket(self):      return self._get("bracket", [])
    def scorers(self):      return self._get("scorers", [])
    def projections(self):  return self._get("projections", {})
    def manifest(self):     return self._get("manifest", {})

    def team(self, tid):
        return next((t for t in self.teams() if t.get("id") == tid), None)

    def roster(self, tid):
        return next((r for r in self.rosters() if r.get("team_id") == tid), None)
