"""YANIDOLLARZ automatic final-score updater (GitHub Actions).

GitHub Actions secrets:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FOOTBALL_API_KEY,
    BZZOIRO_API_KEY (for negative/Bzzoiro match IDs),
    HIGHLIGHTLY_API_KEY (optional, for verified corners/yellow cards).

Positive match IDs belong to football-data.org; negative IDs encode Bzzoiro IDs.
"""

import json
import logging
import os
import sys
import time
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger("score-sync")


def secret(name):
    return os.environ.get(name, "").strip().strip('"').strip("'")


URL = secret("SUPABASE_URL").rstrip("/")
SERVICE_KEY = secret("SUPABASE_SERVICE_ROLE_KEY")
FOOTBALL_KEY = secret("FOOTBALL_API_KEY")
BZZOIRO_KEY = secret("BZZOIRO_API_KEY")
BSD_BASE = "https://sports.bzzoiro.com/api/v2"


def safe_endpoint(url):
    parts = urlsplit(url)
    return f"{parts.hostname or 'unknown-host'}{parts.path}"


class APIError(RuntimeError):
    def __init__(self, status, url):
        self.status = status
        super().__init__(f"HTTP {status} from {safe_endpoint(url)}")


def request_json(url, headers, method="GET", payload=None, retries=3):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    for attempt in range(retries):
        try:
            req = Request(url, data=body, headers=headers, method=method)
            with urlopen(req, timeout=25) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                delay = min(60, 3 * (attempt + 1))
                LOG.warning("HTTP %s from %s; retrying in %ss", exc.code, safe_endpoint(url), delay)
                time.sleep(delay)
                continue
            # Never log response bodies, URLs with query strings, or API keys.
            raise APIError(exc.code, url) from exc
        except (URLError, TimeoutError, OSError) as exc:
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"Network request failed for {safe_endpoint(url)}") from exc
        except (ValueError, TypeError) as exc:
            raise RuntimeError(f"Invalid JSON from {safe_endpoint(url)}") from exc


def supabase_headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def pending_matches():
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=30)).isoformat()
    end = now.isoformat()
    query = urlencode({
        "select": "id,match_id,kickoff,status",
        "status": "eq.Pending",
        "and": f"(kickoff.gte.{start},kickoff.lte.{end})",
        "order": "kickoff.asc",
        "limit": "250",
    })
    return request_json(f"{URL}/rest/v1/prediction_history?{query}", supabase_headers()) or []

