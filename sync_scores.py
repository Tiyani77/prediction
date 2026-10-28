"""YANIDOLLARZ automatic final-score updater (GitHub Actions).

Required repository secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
FOOTBALL_API_KEY.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger("score-sync")

URL = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip().strip('"').strip("'")
FOOTBALL_KEY = os.environ.get("FOOTBALL_API_KEY", "").strip().strip('"').strip("'")


def safe_endpoint(url):
    """Only log host/path; never query parameters or credentials."""
    parts = urlsplit(url)
    return f"{parts.hostname or 'unknown-host'}{parts.path}"


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

            raw_error = exc.read().decode("utf-8", errors="replace")
            # Extract a limited set of safe diagnostic fields; do not log the
            # full response, which might echo request details or credentials.
            try:
                parsed = json.loads(raw_error)
            except ValueError:
                parsed = {}
            if isinstance(parsed, dict):
                code = str(parsed.get("code", ""))[:80]
                message = str(parsed.get("message", ""))[:350]
                hint = str(parsed.get("hint", ""))[:200]
                # Mask secret values if a server echoes one unexpectedly.
                for secret in (SERVICE_KEY, FOOTBALL_KEY):
                    if secret:
                        code = code.replace(secret, "[REDACTED]")
                        message = message.replace(secret, "[REDACTED]")
                        hint = hint.replace(secret, "[REDACTED]")
                LOG.error("API response: code=%r message=%r hint=%r", code, message, hint)
            else:
                LOG.error("API returned HTTP %s with a non-JSON response", exc.code)
            raise RuntimeError(f"HTTP {exc.code} from {safe_endpoint(url)}") from exc
        except (URLError, TimeoutError) as exc:
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError(f"Network request failed for {safe_endpoint(url)}") from exc


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


def fetch_match(match_id):
    return request_json(
        f"https://api.football-data.org/v4/matches/{int(match_id)}",
        {"X-Auth-Token": FOOTBALL_KEY, "Accept": "application/json"},
    )


def update_records(match_id, changes):
    query = urlencode({"match_id": f"eq.{int(match_id)}", "status": "eq.Pending"})
    request_json(
        f"{URL}/rest/v1/prediction_history?{query}",
        supabase_headers(), method="PATCH", payload=changes,
    )


def main():
    if not all((URL.startswith("https://"), SERVICE_KEY, FOOTBALL_KEY)):
        LOG.error("Missing or invalid required GitHub secrets")
        return 2

    rows = pending_matches()
    unique_ids = sorted({int(row["match_id"]) for row in rows if row.get("match_id")})
    LOG.info("Pending predictions: %s; unique matches: %s", len(rows), len(unique_ids))

    updated = 0
    errors = 0
    for i, match_id in enumerate(unique_ids):
        try:
            match = fetch_match(match_id)
            status = match.get("status")
            score = (match.get("score") or {}).get("fullTime") or {}
            home, away = score.get("home"), score.get("away")
            if status == "FINISHED" and home is not None and away is not None:
                update_records(match_id, {
                    "status": "Finished", "score_home": int(home), "score_away": int(away),
                })
                updated += 1
            elif status in ("CANCELLED", "POSTPONED", "SUSPENDED"):
                update_records(match_id, {"status": status.title()})
                updated += 1
        except Exception as exc:
            errors += 1
            LOG.error("Match %s failed: %s", match_id, exc)
        if i < len(unique_ids) - 1:
            time.sleep(7)

    LOG.info("Matches updated: %s; errors: %s", updated, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
