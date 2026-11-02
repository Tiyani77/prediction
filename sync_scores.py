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


def bsd_headers():
    return {
        "Authorization": f"Token {BZZOIRO_KEY}",
        "Accept": "application/json",
        "User-Agent": "YANIDOLLARZ/1.0 (score-sync)",
    }


def unwrap_bsd_event(payload, event_id):
    """Accept detail responses or paginated list envelopes, but verify event ID."""
    if isinstance(payload, dict):
        if str(payload.get("id", "")) == str(event_id):
            return payload
        for field in ("event", "data", "results", "events", "items"):
            value = payload.get(field)
            found = unwrap_bsd_event(value, event_id)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = unwrap_bsd_event(item, event_id)
            if found:
                return found
    return None


def fetch_bsd_match(match_id):
    if not BZZOIRO_KEY:
        raise RuntimeError("BZZOIRO_API_KEY is missing from GitHub Actions secrets")
    event_id = abs(int(match_id))
    # BSD's /events/ collection is already used by the Streamlit application.
    # Try the REST detail URL first; fall back to the collection if unsupported.
    try:
        payload = request_json(f"{BSD_BASE}/events/{event_id}/", bsd_headers())
        event = unwrap_bsd_event(payload, event_id)
        if event:
            return event
    except APIError as exc:
        if exc.status not in (400, 404, 405):
            raise
    # Collection fallback uses the documented list endpoint shape of the app.
    # Filter locally by exact event ID so unrelated events can never be written.
    for params in ({"id": event_id, "limit": 100}, {"event_id": event_id, "limit": 100}):
        payload = request_json(f"{BSD_BASE}/events/?{urlencode(params)}", bsd_headers())
        event = unwrap_bsd_event(payload, event_id)
        if event:
            return event
    LOG.warning("Bzzoiro event %s was not returned by the API; leaving pending", event_id)
    return None


def fetch_match(match_id):
    if int(match_id) < 0:
        return fetch_bsd_match(match_id)
    if not FOOTBALL_KEY:
        raise RuntimeError("FOOTBALL_API_KEY is missing from GitHub Actions secrets")
    return request_json(
        f"https://api.football-data.org/v4/matches/{int(match_id)}",
        {"X-Auth-Token": FOOTBALL_KEY, "Accept": "application/json"},
    )


def numeric_score(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def match_result(match_id, match):
    """Return status and verified full-time scores, never fabricate missing values."""
    if not isinstance(match, dict):
        return None, None, None
    if int(match_id) > 0:
        status = str(match.get("status") or "").upper()
        full = (match.get("score") or {}).get("fullTime") or {}
        home, away = numeric_score(full.get("home")), numeric_score(full.get("away"))
        return status, home, away

    raw_status = str(match.get("status") or "").strip().lower().replace(" ", "_")
    statuses = {
        "finished": "FINISHED", "ft": "FINISHED", "full_time": "FINISHED",
        "completed": "FINISHED", "ended": "FINISHED",
        "cancelled": "CANCELLED", "canceled": "CANCELLED",
        "postponed": "POSTPONED", "suspended": "SUSPENDED",
    }
    status = statuses.get(raw_status, raw_status.upper())
    home = match.get("home_score")
    away = match.get("away_score")
    score = match.get("score")
    if isinstance(score, dict):
        full = score.get("fullTime") or score.get("full_time") or score
        if isinstance(full, dict):
            if home is None:
                home = full.get("home")
            if away is None:
                away = full.get("away")
    return status, numeric_score(home), numeric_score(away)


def update_records(match_id, changes):
    query = urlencode({"match_id": f"eq.{int(match_id)}", "status": "eq.Pending"})
    request_json(
        f"{URL}/rest/v1/prediction_history?{query}",
        supabase_headers(), method="PATCH", payload=changes,
    )


# Highlightly match statistics are matched by date, BOTH team names and final score.
# An uncertain match is skipped, never guessed.
HIGHLIGHTLY_KEY = secret("HIGHLIGHTLY_API_KEY")
HIGHLIGHTLY_BASE = "https://soccer.highlightly.net"
MAX_HIGHLIGHTLY_REQUESTS = 30  # conservative per-workflow cap


def finished_missing_stats():
    """Fetch only finished records still lacking either verified statistic."""
    if not HIGHLIGHTLY_KEY:
        return []
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=14)).isoformat()
    query = urlencode({
        "select": "id,match_id,kickoff,home,away,score_home,score_away,final_corners_total,final_yellow_cards_total",
        "status": "eq.Finished",
        "and": f"(kickoff.gte.{start},kickoff.lte.{now.isoformat()})",
        "or": "(final_corners_total.is.null,final_yellow_cards_total.is.null)",
        "order": "kickoff.desc", "limit": "50",
    })
    return request_json(f"{URL}/rest/v1/prediction_history?{query}", supabase_headers()) or []


def norm_name(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", value.lower())


def highlightly_headers():
    return {"x-rapidapi-key": HIGHLIGHTLY_KEY,
            "x-rapidapi-host": "soccer.highlightly.net", "Accept": "application/json"}


def highlightly_json(path, params=None):
    url = HIGHLIGHTLY_BASE + path
    if params:
        url += "?" + urlencode(params)
    return request_json(url, highlightly_headers(), retries=2)


def match_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "matches", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def score_pair(match):
    state = match.get("state") or {}
    score = state.get("score") or {}
    for candidate in (score.get("current"), score.get("fullTime"), score.get("full_time")):
        if isinstance(candidate, str):
            found = re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*", candidate)
            if found:
                return int(found.group(1)), int(found.group(2))
        if isinstance(candidate, dict):
            h = numeric_score(candidate.get("home"))
            a = numeric_score(candidate.get("away"))
            if h is not None and a is not None:
                return h, a
    return None


def verified_match(row, candidate):
    if norm_name((candidate.get("homeTeam") or {}).get("name")) != norm_name(row.get("home")):
        return False
    if norm_name((candidate.get("awayTeam") or {}).get("name")) != norm_name(row.get("away")):
        return False
    state = (candidate.get("state") or {}).get("description") or ""
    if str(state).strip().lower() not in ("finished", "finished after extra time", "finished after penalties"):
        return False
    actual = score_pair(candidate)
    return actual == (numeric_score(row.get("score_home")), numeric_score(row.get("score_away")))


def stat_total(detail, token):
    """Require two distinct team statistic groups and explicit numeric values."""
    groups = detail.get("statistics") or []
    if not isinstance(groups, list):
        return None
    teams = (detail.get("homeTeam") or {}, detail.get("awayTeam") or {})
    totals = []
    for team in teams:
        matching = [g for g in groups if isinstance(g, dict) and
                    str((g.get("team") or {}).get("id")) == str(team.get("id")) and team.get("id") is not None]
        if len(matching) != 1:
            return None
        values = []
        for entry in matching[0].get("statistics") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("displayName") or "").strip().lower()
            if token == "corners" and name in ("corner kicks", "corners"):
                values.append(numeric_score(entry.get("value")))
            elif token == "yellow" and name in ("yellow cards", "yellow card"):
                values.append(numeric_score(entry.get("value")))
        if len(values) != 1 or values[0] is None:
            return None
        totals.append(values[0])
    return sum(totals) if len(totals) == 2 else None


def settle_stats():
    if not HIGHLIGHTLY_KEY:
        LOG.info("HIGHLIGHTLY_API_KEY absent; skipping optional corner/card settlement")
        return 0
    rows = finished_missing_stats()
    LOG.info("Finished records needing market stats: %s", len(rows))
    # Fetch each calendar day once, then details for uniquely verified matches.
    by_day = {}
    requests_used = 0
    settled = 0
    for row in rows:
        if requests_used >= MAX_HIGHLIGHTLY_REQUESTS:
            LOG.info("Highlightly request safety cap reached")
            break
        try:
            kickoff = datetime.fromisoformat(str(row["kickoff"]).replace("Z", "+00:00"))
            day = kickoff.date().isoformat()
            if day not in by_day:
                requests_used += 1
                by_day[day] = match_list(highlightly_json("/matches", {"date": day, "limit": 100}))
            candidates = [m for m in by_day[day] if isinstance(m, dict) and verified_match(row, m)]
            if len(candidates) != 1:
                LOG.info("No unique verified Highlightly match for saved row %s", row.get("id"))
                continue
            mid = candidates[0].get("id")
            if mid is None:
                continue
            requests_used += 1
            detail = highlightly_json(f"/matches/{int(mid)}")
            if isinstance(detail, list):
                detail = detail[0] if len(detail) == 1 else None
            if not isinstance(detail, dict) or not verified_match(row, detail):
                LOG.info("Detail mismatch for row %s; skipping", row.get("id"))
                continue
            changes = {}
            if row.get("final_corners_total") is None:
                value = stat_total(detail, "corners")
                if value is not None:
                    changes["final_corners_total"] = value
            if row.get("final_yellow_cards_total") is None:
                value = stat_total(detail, "yellow")
                if value is not None:
                    changes["final_yellow_cards_total"] = value
            if changes:
                changes["market_stats_source"] = "Highlightly"
                changes["market_stats_verified_at"] = datetime.now(timezone.utc).isoformat()
                query = urlencode({"id": f"eq.{row['id']}", "status": "eq.Finished"})
                request_json(f"{URL}/rest/v1/prediction_history?{query}",
                             supabase_headers(), method="PATCH", payload=changes)
                settled += 1
                LOG.info("Verified market statistics saved for row %s", row.get("id"))
        except APIError as exc:
            LOG.warning("Market statistics unavailable for row %s: %s", row.get("id"), exc)
            if exc.status in (401, 403, 429):
                break
        except Exception as exc:
            LOG.warning("Market statistics skipped for row %s: %s", row.get("id"), exc)
    LOG.info("Market stats rows updated: %s; Highlightly requests: %s", settled, requests_used)
    return settled


def main():
    if not URL.startswith("https://") or not SERVICE_KEY:
        LOG.error("Missing or invalid SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
        return 2
    rows = pending_matches()
    unique_ids = sorted({int(row["match_id"]) for row in rows if row.get("match_id") is not None})
    LOG.info("Pending predictions: %s; unique matches: %s", len(rows), len(unique_ids))

    updated = 0
    errors = 0
    skipped = 0
    for i, match_id in enumerate(unique_ids):
        try:
            match = fetch_match(match_id)
            if match is None:
                skipped += 1
                continue
            status, home, away = match_result(match_id, match)
            if status == "FINISHED" and home is not None and away is not None:
                update_records(match_id, {
                    "status": "Finished", "score_home": home, "score_away": away,
                })
                updated += 1
                LOG.info("Match %s finished: %s-%s", match_id, home, away)
            elif status in ("CANCELLED", "POSTPONED", "SUSPENDED"):
                update_records(match_id, {"status": status.title()})
                updated += 1
            else:
                skipped += 1
                LOG.info("Match %s not final (status=%s); remains pending", match_id, status or "unknown")
        except APIError as exc:
            # Missing/unavailable event is not a workflow-wide failure.
            if exc.status in (400, 404):
                skipped += 1
                LOG.warning("Match %s not available from provider (%s); remains pending", match_id, exc.status)
            else:
                errors += 1
                LOG.error("Match %s failed: %s", match_id, exc)
        except Exception as exc:
            errors += 1
            LOG.error("Match %s failed: %s", match_id, exc)
        finally:
            if i < len(unique_ids) - 1:
                time.sleep(2)

    LOG.info("Matches updated: %s; pending/skipped: %s; errors: %s", updated, skipped, errors)
    try:
        settle_stats()
    except Exception as exc:
        # Statistics failures must never break the working score updater.
        LOG.warning("Optional market-statistics settlement failed: %s", exc)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
