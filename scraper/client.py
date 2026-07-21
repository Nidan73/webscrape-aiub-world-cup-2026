"""HTTP client: polite, retrying access to the tournament site."""
import logging
import time

import requests

from scraper import config

log = logging.getLogger(__name__)


class Client:
    def __init__(self, base_url=config.BASE_URL, delay=config.DEFAULT_DELAY,
                 timeout=config.DEFAULT_TIMEOUT, retries=config.DEFAULT_RETRIES,
                 user_agent=config.USER_AGENT):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "X-Requested-With": "XMLHttpRequest"}
        )

    def _get(self, url):
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("GET %s failed (%d/%d): %s", url, attempt, self.retries, exc)
                if attempt < self.retries:
                    time.sleep(self.delay * attempt)
        raise last_exc

    def fetch_tab(self, name):
        if self.delay:
            time.sleep(self.delay)
        url = f"{self.base_url}/tab-api.php?tab={name}"
        return self._get(url).json().get("html", "")

    def fetch_page(self, path):
        if self.delay:
            time.sleep(self.delay)
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        return self._get(url).text
