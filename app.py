
import streamlit as st
import base64
from pathlib import Path
from supabase import create_client
from supabase_auth.errors import AuthApiError
import hashlib
import logging
import secrets
import sqlite3
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import math
import html
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

# ==========================================
# YANIDOLLARZ
# Football Predictions & Analytics
# ==========================================

st.set_page_config(
    page_title="YANIDOLLARZ",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 1. SUPABASE CONNECTION
# ==========================================

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# The publicly accessible Streamlit address, without a trailing slash.
APP_URL = st.secrets.get(
    "APP_URL",
    "https://prediction-xxhh3jviypuhfphhukjfs.streamlit.app"
).rstrip("/")


def get_supabase():
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )


# ==========================================
# 2. SESSION STATE
# ==========================================

if "page" not in st.session_state:
    st.session_state.page = "home"

if "user" not in st.session_state:
    st.session_state.user = None

if "auth_session" not in st.session_state:
    st.session_state.auth_session = None


def navigate(page):
    st.session_state.page = page
    st.rerun()


def logout():
    """End the current Supabase session."""
    session = st.session_state.auth_session

    if session is not None:
        try:
            client = get_supabase()
            client.auth.set_session(
                session.access_token,
                session.refresh_token
            )
            client.auth.sign_out()
        except Exception:
            # Clear the local session even if the
            # remote sign-out request fails.
            pass

    st.session_state.user = None
    st.session_state.auth_session = None
    st.query_params.clear()
    navigate("home")


# ==========================================
# GOOGLE OAUTH CALLBACK AND SIGN-IN
# ==========================================

# OAuth PKCE state is kept on the server because Streamlit session state
# can be reset when the browser leaves the app to sign in with Google.
# This SQLite store is appropriate for a single-instance deployment.
OAUTH_DB = Path("/tmp/yanidollarz_oauth_state.sqlite3")
OAUTH_TTL_SECONDS = 600
logger = logging.getLogger("yanidollarz.auth")


def oauth_database():
    connection = sqlite3.connect(str(OAUTH_DB), timeout=10)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS oauth_attempts (
            state_hash TEXT PRIMARY KEY,
            verifier TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    return connection


def google_sign_in_url():
    """Start Supabase Google OAuth with a real PKCE challenge."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state.encode("ascii")).hexdigest()

    with oauth_database() as db:
        db.execute(
            "DELETE FROM oauth_attempts WHERE created_at < ?",
            (time.time() - OAUTH_TTL_SECONDS,)
        )
        db.execute(
            "INSERT INTO oauth_attempts (state_hash, verifier, created_at) VALUES (?, ?, ?)",
            (state_hash, verifier, time.time())
        )

    # The random state identifies the verifier in our server-side store.
    # Only the state, not the secret verifier, appears in the redirect URL.
    callback = APP_URL + "/?" + urlencode({"oauth_state": state})
    params = urlencode({
        "provider": "google",
        "redirect_to": callback,
        "code_challenge": challenge,
        "code_challenge_method": "s256",
    })
    return SUPABASE_URL.rstrip("/") + "/auth/v1/authorize?" + params


def handle_auth_callback():
    """Complete Google sign-in using the original one-time PKCE verifier."""
    error = st.query_params.get("error_description")
    if error or st.query_params.get("error"):
        st.session_state.oauth_error = (
            str(error) if error else "Google did not authorize sign-in."
        )
        st.query_params.clear()
        return

    code = st.query_params.get("code")
    if not code:
        return

    state = st.query_params.get("oauth_state")
    st.query_params.clear()
    if not state:
        st.session_state.oauth_error = "Google login expired or lost its state. Please try again."
        return

    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    try:
        with oauth_database() as db:
            record = db.execute(
                "SELECT verifier, created_at FROM oauth_attempts WHERE state_hash = ?",
                (state_hash,)
            ).fetchone()
            db.execute("DELETE FROM oauth_attempts WHERE state_hash = ?", (state_hash,))

        if not record or time.time() - record[1] > OAUTH_TTL_SECONDS:
            raise ValueError("OAuth attempt missing or expired")

        # Exchange the one-time code using Supabase's PKCE token endpoint.
        # The Python SDK's exchange_code_for_session() expects its own
        # in-memory verifier, which is lost across a Streamlit browser redirect.
        payload = json.dumps({
            "auth_code": code,
            "code_verifier": record[0],
        }).encode("utf-8")
        request = Request(
            SUPABASE_URL.rstrip("/") + "/auth/v1/token?grant_type=pkce",
            data=payload,
            headers={
                "apikey": SUPABASE_KEY,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            tokens = json.load(response)
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        if not access_token or not refresh_token:
            raise ValueError("No session tokens returned by Supabase")

        # Validate the resulting session and obtain a real Supabase user.
        client = get_supabase()
        auth_result = client.auth.set_session(access_token, refresh_token)
        if not auth_result.session or not auth_result.user:
            raise ValueError("Unable to establish Supabase session")

        st.session_state.auth_session = auth_result.session
        st.session_state.user = auth_result.user
        st.session_state.page = "dashboard"
        st.session_state.oauth_error = None
        st.rerun()
    except (HTTPError, URLError, ValueError, Exception):
        logger.exception("Google OAuth callback failed; check Supabase redirect and PKCE settings")
        st.session_state.oauth_error = (
            "Google sign-in could not be completed. Please try again with a new link. "
            "If it continues, check Streamlit Manage app → Logs."
        )


def google_button():
    """Google login via Supabase with PKCE verification."""
    try:
        url = google_sign_in_url()
        st.link_button("🌐 Continue with Google", url, use_container_width=True)
    except Exception:
        logger.exception("Unable to start Google OAuth")
        st.error("Google sign-in is temporarily unavailable.")

handle_auth_callback()

# ==========================================
# FOOTBALL-DATA.ORG FIXTURES
# ==========================================

FOOTBALL_API_KEY = st.secrets.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://api.football-data.org/v4"
SA_TIMEZONE = ZoneInfo("Africa/Johannesburg")
COMPETITIONS = {
    "Premier League": "PL",
    "Champions League": "CL",
    "La Liga": "PD",
    "Bundesliga": "BL1",
    "Serie A": "SA",
    "Ligue 1": "FL1",
    "Championship": "ELC",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
    "Brazil Serie A": "BSA",
}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_fixtures(competition_code, date_from, date_to, _api_key):
    """Get fixtures, cached 15 minutes to respect the free API quota."""
    url = (
        f"{FOOTBALL_API_BASE}/competitions/{competition_code}/matches?"
        + urlencode({"dateFrom": date_from, "dateTo": date_to})
    )
    request = Request(url, headers={"X-Auth-Token": _api_key})
    try:
        with urlopen(request, timeout=18) as response:
            data = json.load(response)
        return data.get("matches", []), None
    except HTTPError as exc:
        messages = {
            400: "Invalid competition or date range.",
            401: "API token rejected. Check FOOTBALL_API_KEY in Streamlit Secrets.",
            403: "This competition is not available on your API subscription.",
            404: "Competition not found.",
            429: "API rate limit reached. Please wait and try again.",
        }
        return [], messages.get(exc.code, f"Football API error (HTTP {exc.code}).")
    except (URLError, TimeoutError, ValueError, OSError):
        return [], "Could not reach football-data.org. Please try again later."


# ==========================================
# MATCH ANALYSIS — HISTORICAL RESULTS
# ==========================================

@st.cache_data(ttl=900, show_spinner=False)
def fetch_analysis_json(endpoint, _api_key):
    """Fetch a historical football-data.org endpoint, with a 15-minute cache."""
    request = Request(
        FOOTBALL_API_BASE + endpoint,
        headers={"X-Auth-Token": _api_key, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=18) as response:
            return json.load(response), None
    except HTTPError as exc:
        messages = {
            400: "The football data provider rejected this request.",
            401: "The football API token was rejected.",
            403: "Historical data for this match or team is restricted on your API plan.",
            404: "Historical match data was not found.",
            429: "The API request limit was reached. Please try again shortly.",
        }
        return None, messages.get(exc.code, f"Football API error (HTTP {exc.code}).")
    except (URLError, TimeoutError, ValueError, OSError):
        return None, "Football history could not be loaded. Please try again later."


def completed_before(match, kickoff_utc):
    if match.get("status") != "FINISHED":
        return False
    result = (match.get("score") or {}).get("fullTime") or {}
    if result.get("home") is None or result.get("away") is None:
        return False
    return bool(match.get("utcDate")) and match["utcDate"] < kickoff_utc


def team_result(match, team_id):
    home = (match.get("homeTeam") or {}).get("id") == team_id
    away = (match.get("awayTeam") or {}).get("id") == team_id
    if not (home or away):
        return None
    score = (match.get("score") or {}).get("fullTime") or {}
    h, a = score.get("home"), score.get("away")
    if h is None or a is None:
        return None
    gf, ga = (h, a) if home else (a, h)
    return {"outcome": "W" if gf > ga else "D" if gf == ga else "L",
            "gf": gf, "ga": ga, "venue": "Home" if home else "Away",
            "clean_sheet": ga == 0, "match": match}


def team_statistics(matches, team_id, venue=None):
    results = []
    for match in matches:
        item = team_result(match, team_id)
        if item and (venue is None or item["venue"] == venue):
            results.append(item)
    count = len(results)
    if not count:
        return None
    wins = sum(x["outcome"] == "W" for x in results)
    draws = sum(x["outcome"] == "D" for x in results)
    losses = count - wins - draws
    return {"played": count, "wins": wins, "draws": draws,
            "losses": losses, "win_rate": 100 * wins / count,
            "goals_for": sum(x["gf"] for x in results),
            "goals_against": sum(x["ga"] for x in results),
            "avg_goals": sum(x["gf"] for x in results) / count,
            "clean_sheets": sum(x["clean_sheet"] for x in results),
            "results": results}


def get_team_history(team_id, kickoff_utc, limit=30):
    if not team_id:
        return [], "The team has not been confirmed yet."
    if not FOOTBALL_API_KEY:
        return [], "FOOTBALL_API_KEY is missing from Streamlit Secrets."
    payload, error = fetch_analysis_json(
        f"/teams/{team_id}/matches?status=FINISHED&limit={limit}",
        FOOTBALL_API_KEY,
    )
    if error:
        return [], error
    matches = [m for m in payload.get("matches", []) if completed_before(m, kickoff_utc)]
    matches.sort(key=lambda m: m.get("utcDate", ""), reverse=True)
    return matches, None


def get_head_to_head(match_id, kickoff_utc):
    if not match_id:
        return [], "This fixture has no match ID."
    payload, error = fetch_analysis_json(
        f"/matches/{match_id}/head2head?limit=10", FOOTBALL_API_KEY
    )
    if error:
        return [], error
    matches = [m for m in payload.get("matches", []) if completed_before(m, kickoff_utc)]
    matches.sort(key=lambda m: m.get("utcDate", ""), reverse=True)
    return matches, None


def render_form(matches, team_id, heading):
    st.markdown(f"**{heading} — last five completed matches**")
    recent = [team_result(m, team_id) for m in matches[:5]]
    recent = [r for r in recent if r]
    if not recent:
        st.caption("No completed matches available.")
        return
    st.markdown(" ".join(
        f":{'green' if r['outcome']=='W' else 'orange' if r['outcome']=='D' else 'red'}-badge[{r['outcome']}]"
        for r in recent
    ))
    for r in recent:
        m = r["match"]
        home = (m.get("homeTeam") or {}).get("shortName") or (m.get("homeTeam") or {}).get("name") or "Home"
        away = (m.get("awayTeam") or {}).get("shortName") or (m.get("awayTeam") or {}).get("name") or "Away"
        sc = m["score"]["fullTime"]
        st.caption(f"{m['utcDate'][:10]} · {home} {sc['home']}–{sc['away']} {away} · {r['outcome']}")


def render_stat_block(stats, label):
    st.markdown(f"**{label}**")
    if not stats:
        st.caption("No results available for this sample.")
        return
    st.caption(f"Sample: {stats['played']} completed matches")
    a, b, c = st.columns(3)
    a.metric("Wins", stats["wins"])
    b.metric("Draws", stats["draws"])
    c.metric("Losses", stats["losses"])
    a, b, c = st.columns(3)
    a.metric("Win rate", f"{stats['win_rate']:.0f}%")
    b.metric("Goals for", stats["goals_for"])
    c.metric("Goals against", stats["goals_against"])
    a, b = st.columns(2)
    a.metric("Goals per match", f"{stats['avg_goals']:.2f}")
    b.metric("Clean sheets", stats["clean_sheets"])


def show_match_analysis(match):
    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}
    home_id, away_id = home_team.get("id"), away_team.get("id")
    home_name = home_team.get("name") or "Home team"
    away_name = away_team.get("name") or "Away team"
    kickoff = match.get("utcDate") or datetime.now(timezone.utc).isoformat()
    st.title("🔎 Match Analysis")
    st.caption("Historical results from football-data.org · No predicted outcomes")
    with st.container(border=True):
        a, mid, b = st.columns([5, 1, 5])
        with a:
            st.subheader(home_name)
            st.caption("HOME")
        with mid:
            st.markdown("### VS")
        with b:
            st.subheader(away_name)
            st.caption("AWAY")
        st.caption(f"{local_kickoff(match.get('utcDate'))} · {match.get('status','Scheduled').title()}")

    with st.spinner("Loading recent results and head-to-head records..."):
        home_matches, home_error = get_team_history(home_id, kickoff)
        away_matches, away_error = get_team_history(away_id, kickoff)
        h2h_matches, h2h_error = get_head_to_head(match.get("id"), kickoff)

    st.subheader("📈 Recent form")
    left, right = st.columns(2)
    with left:
        if home_error:
            st.warning(f"{home_name}: {home_error}")
        else:
            render_form(home_matches, home_id, home_name)
    with right:
        if away_error:
            st.warning(f"{away_name}: {away_error}")
        else:
            render_form(away_matches, away_id, away_name)

    st.subheader("📊 Team statistics")
    st.caption("Based on available completed matches before this fixture, up to 30 per team. Different teams may have different sample sizes.")
    left, right = st.columns(2)
    with left:
        render_stat_block(team_statistics(home_matches, home_id), home_name)
    with right:
        render_stat_block(team_statistics(away_matches, away_id), away_name)

    st.subheader("🏟️ Home vs away performance")
    st.caption("Home team at home compared with away team away; based on the same available historical sample.")
    left, right = st.columns(2)
    with left:
        render_stat_block(team_statistics(home_matches, home_id, "Home"), f"{home_name} · Home")
    with right:
        render_stat_block(team_statistics(away_matches, away_id, "Away"), f"{away_name} · Away")

    st.subheader("🤝 Head-to-head")
    if h2h_error:
        st.warning(h2h_error)
    elif not h2h_matches:
        st.info("No previous completed head-to-head meetings available for this fixture.")
    else:
        st.caption(f"{len(h2h_matches)} previous completed meeting(s) returned")
        for previous in h2h_matches:
            h = (previous.get("homeTeam") or {}).get("shortName") or (previous.get("homeTeam") or {}).get("name") or "Home"
            a = (previous.get("awayTeam") or {}).get("shortName") or (previous.get("awayTeam") or {}).get("name") or "Away"
            score = (previous.get("score") or {}).get("fullTime") or {}
            with st.container(border=True):
                st.markdown(f"**{h} {score.get('home')} – {score.get('away')} {a}**")
                st.caption(local_kickoff(previous.get("utcDate")))

    st.caption("Historical performance does not guarantee future results. Some datasets may be limited by the free API plan.")
    if match.get('status') in ('SCHEDULED', 'TIMED'):
        st.button('🎯 Predict this match →', key='analysis_predict',
                  on_click=open_match_prediction, args=(match,))


# ==========================================
# POISSON GOALS MODEL — HISTORICAL RESULTS ONLY
# ==========================================


def poisson_distribution(expected_goals, max_goals=12):
    """Stable Poisson probabilities, with the upper tail in the final bucket."""
    probs = [math.exp(-expected_goals)]
    for goals in range(1, max_goals):
        probs.append(probs[-1] * expected_goals / goals)
    probs.append(max(0.0, 1.0 - sum(probs)))
    return probs


def calculate_prediction(home_matches, away_matches, home_id, away_id):
    """Simple independent-Poisson model with venue-aware goal rates.

    Uses only finished historical matches strictly before the fixture.
    Rates are smoothed toward a neutral 1.35-goal prior to reduce small-sample
    volatility; this is an assumption, not a measured league-wide average.
    """
    home_all = team_statistics(home_matches, home_id)
    away_all = team_statistics(away_matches, away_id)
    if not home_all or not away_all or min(home_all['played'], away_all['played']) < 5:
        return None, 'At least five completed historical matches per team are required.'

    home_venue = team_statistics(home_matches, home_id, 'Home')
    away_venue = team_statistics(away_matches, away_id, 'Away')
    if not home_venue or not away_venue or min(home_venue['played'], away_venue['played']) < 3:
        return None, 'At least three home matches for the home team and three away matches for the away team are required.'

    # Smooth observed rates with 5 pseudo-matches to reduce overfitting.
    prior, weight = 1.35, 5.0
    def rate(stats, key):
        return (stats[key] + prior * weight) / (stats['played'] + weight)

    home_attack = rate(home_venue, 'goals_for')
    away_defence = rate(away_venue, 'goals_against')
    away_attack = rate(away_venue, 'goals_for')
    home_defence = rate(home_venue, 'goals_against')
    # Symmetric blend of attack and opposing defence (no odds or xG data).
    home_xg = max(0.15, min(4.0, (home_attack + away_defence) / 2))
    away_xg = max(0.15, min(4.0, (away_attack + home_defence) / 2))

    ph = poisson_distribution(home_xg)
    pa = poisson_distribution(away_xg)
    home_win = draw = away_win = btts = 0.0
    totals = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0}
    scorelines = []
    for h, hp in enumerate(ph):
        for a, ap in enumerate(pa):
            prob = hp * ap
            scorelines.append((h, a, prob))
            if h > a:
                home_win += prob
            elif h == a:
                draw += prob
            else:
                away_win += prob
            if h >= 1 and a >= 1:
                btts += prob
            for line in totals:
                if h + a > line:
                    totals[line] += prob

    scorelines.sort(key=lambda item: item[2], reverse=True)
    n_venue = min(home_venue['played'], away_venue['played'])
    peak = max(home_win, draw, away_win)
    # Descriptive uncertainty flag, NOT a calibrated probability of success.
    if n_venue < 6 or peak < 0.45:
        risk = 'High uncertainty'
    elif n_venue < 10 or peak < 0.58:
        risk = 'Moderate uncertainty'
    else:
        risk = 'Lower relative uncertainty'
    return {
        'home_xg': home_xg, 'away_xg': away_xg,
        'home_win': home_win, 'draw': draw, 'away_win': away_win,
        'btts': btts, 'overs': totals, 'scorelines': scorelines[:5],
        'home_sample': home_all['played'], 'away_sample': away_all['played'],
        'home_venue_sample': home_venue['played'],
        'away_venue_sample': away_venue['played'],
        'risk': risk, 'peak': peak,
    }, None


def get_match_prediction(match):
    home = match.get('homeTeam') or {}
    away = match.get('awayTeam') or {}
    home_id, away_id = home.get('id'), away.get('id')
    kickoff = match.get('utcDate')
    if not home_id or not away_id or not kickoff:
        return None, 'Fixture must have confirmed teams and a kickoff time.'
    if match.get('status') == 'FINISHED':
        return None, 'Predictions are available for upcoming matches, not finished fixtures.'
    with st.spinner('Calculating model probabilities from historical matches...'):
        hm, he = get_team_history(home_id, kickoff)
        am, ae = get_team_history(away_id, kickoff)
    if he or ae:
        return None, 'Historical data unavailable: ' + '; '.join(e for e in (he, ae) if e)
    return calculate_prediction(hm, am, home_id, away_id)


# ==========================================
# TEMPORARY SESSION-ONLY PREDICTION TRACKING
# ==========================================


def authenticated_history_client():
    """Use the logged-in user's JWT so Supabase RLS is enforced."""
    session = st.session_state.get("auth_session")
    user = st.session_state.get("user")
    if session is None or user is None:
        raise ValueError("Please log in to access your prediction history.")
    client = get_supabase()
    refreshed = client.auth.set_session(session.access_token, session.refresh_token)
    if not refreshed.session or not refreshed.user:
        raise ValueError("Your session has expired. Please log in again.")
    if str(refreshed.user.id) != str(user.id):
        raise ValueError("Authentication changed. Please log in again.")
    st.session_state.auth_session = refreshed.session
    st.session_state.user = refreshed.user
    return client


def load_prediction_history():
    """Load the current user's permanent history (RLS also filters records)."""
    client = authenticated_history_client()
    response = (client.table("prediction_history")
                .select("*")
                .order("kickoff", desc=True)
                .limit(1000)
                .execute())
    return response.data or []


def save_session_prediction(match, prediction):
    """Insert an immutable pre-kickoff snapshot; never overwrite an existing pick."""
    match_id, kickoff = match.get("id"), match.get("utcDate")
    if not match_id or not kickoff:
        return False, "This fixture has no match ID or kickoff time."
    try:
        kickoff_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except ValueError:
        return False, "Invalid kickoff time."
    if datetime.now(timezone.utc) >= kickoff_dt:
        return False, "Predictions can only be saved before kickoff."
    home, away = match.get("homeTeam") or {}, match.get("awayTeam") or {}
    try:
        client = authenticated_history_client()
        record = {
            "user_id": str(st.session_state.user.id),
            "match_id": int(match_id),
            "home": home.get("name") or "Home",
            "away": away.get("name") or "Away",
            "kickoff": kickoff,
            "home_win": float(prediction["home_win"]),
            "draw": float(prediction["draw"]),
            "away_win": float(prediction["away_win"]),
            "over_1_5": float(prediction["overs"][1.5]),
            "over_2_5": float(prediction["overs"][2.5]),
            "over_3_5": float(prediction["overs"][3.5]),
            "btts": float(prediction["btts"]),
            "home_xg": float(prediction["home_xg"]),
            "away_xg": float(prediction["away_xg"]),
            "risk": prediction["risk"],
        }
        client.table("prediction_history").insert(record).execute()
        return True, "Prediction saved permanently to your Supabase account."
    except Exception as exc:
        logger.exception("Could not save prediction")
        message = str(exc).lower()
        if "23505" in message or "duplicate key" in message:
            return False, "This fixture is already saved. Original probabilities are preserved."
        return False, "Save failed. Check the Supabase SQL setup, table permissions and connection."


def update_session_results(records):
    """Look up finished scores and persist them without changing probabilities."""
    updated, errors = 0, []
    client = authenticated_history_client()
    for record in records:
        if record["status"] in ("Finished", "Cancelled", "Postponed", "Suspended"):
            continue
        kickoff = datetime.fromisoformat(record["kickoff"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < kickoff:
            continue
        data, error = fetch_analysis_json(f'/matches/{record["match_id"]}', FOOTBALL_API_KEY)
        if error:
            errors.append(f'{record["home"]} vs {record["away"]}: {error}')
            continue
        match = data.get("match", data) if isinstance(data, dict) else {}
        score = (match.get("score") or {}).get("fullTime") or {}
        h, a = score.get("home"), score.get("away")
        status = match.get("status")
        changes = None
        if status == "FINISHED" and h is not None and a is not None:
            changes = {"score_home": int(h), "score_away": int(a), "status": "Finished"}
        elif status in ("CANCELLED", "POSTPONED", "SUSPENDED"):
            changes = {"status": status.title()}
        if changes:
            try:
                (client.table("prediction_history").update(changes)
                 .eq("id", record["id"])
                 .eq("user_id", str(st.session_state.user.id))
                 .eq("status", "Pending").execute())
                updated += 1
            except Exception:
                logger.exception("Failed to persist match result")
                errors.append(f'{record["home"]} vs {record["away"]}: database update failed')
    return updated, errors


def prediction_scores(record):
    """Return outcome and proper scoring rules for a finished match."""
    h, a = record["score_home"], record["score_away"]
    if h is None or a is None:
        return None
    actual = 0 if h > a else 1 if h == a else 2
    probs = [record["home_win"], record["draw"], record["away_win"]]
    # Multiclass Brier score: sum of squared errors across the 3 outcomes.
    brier = sum((p - int(i == actual)) ** 2 for i, p in enumerate(probs))
    logloss = -math.log(max(1e-12, probs[actual]))
    return {
        "actual": ["Home", "Draw", "Away"][actual],
        "correct": int(max(range(3), key=lambda i: probs[i]) == actual),
        "brier": brier,
        "logloss": logloss,
        "over_2_5_correct": int((record["over_2_5"] >= .5) == (h + a > 2.5)),
        "btts_correct": int((record["btts"] >= .5) == (h > 0 and a > 0)),
        "over_2_5_brier": (record["over_2_5"] - int(h + a > 2.5)) ** 2,
        "btts_brier": (record["btts"] - int(h > 0 and a > 0)) ** 2,
    }


def show_prediction_history():
    st.title("📊 Prediction History & Performance")
    st.caption("Private Supabase history · Automatic score checks via GitHub Actions every six hours.")
    try:
        records = load_prediction_history()
    except Exception:
        logger.exception("Failed to load prediction history")
        st.error("Unable to load prediction history. Run the supplied SQL in Supabase, then refresh this page.")
        return
    if not records:
        st.info("No predictions saved yet. Open Fixtures → Predict → Save prediction.")
        return
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("🔄 Check final scores", use_container_width=True):
            if not FOOTBALL_API_KEY:
                st.warning("FOOTBALL_API_KEY is missing from Streamlit Secrets.")
            else:
                with st.spinner("Checking saved fixtures..."):
                    fetch_analysis_json.clear()
                    try:
                        updated, errors = update_session_results(records)
                        records = load_prediction_history()
                        st.success(f"{updated} match status(es) updated.")
                        for error in errors[:5]:
                            st.warning(error)
                    except Exception:
                        logger.exception("Final-score refresh failed")
                        st.error("Could not update scores. Check Streamlit logs and Supabase permissions.")
    with c2:
        st.caption("GitHub Actions checks pending matches every six hours; you can also check scores manually here.")
    graded = [(r, prediction_scores(r)) for r in records if r["status"] == "Finished"]
    graded = [(r, score) for r, score in graded if score is not None]
    st.subheader("Model performance")
    a, b, c, d = st.columns(4)
    a.metric("Saved predictions", len(records))
    b.metric("Evaluated", len(graded))
    c.metric("Outcome accuracy", f"{sum(s['correct'] for _, s in graded) / len(graded):.1%}" if graded else "—")
    d.metric("Mean Brier score", f"{sum(s['brier'] for _, s in graded) / len(graded):.3f}" if graded else "—")
    if graded:
        c1, c2, c3 = st.columns(3)
        c1.metric("Mean log loss", f"{sum(s['logloss'] for _, s in graded)/len(graded):.3f}")
        c2.metric("Over 2.5 accuracy", f"{sum(s['over_2_5_correct'] for _, s in graded)/len(graded):.1%}")
        c3.metric("BTTS accuracy", f"{sum(s['btts_correct'] for _, s in graded)/len(graded):.1%}")
        st.caption("Outcome accuracy uses the most likely home/draw/away outcome. Goals and BTTS accuracy use a 50% threshold. These are descriptive metrics, not proof of predictive skill.")
        st.caption("Multiclass Brier is the sum of three squared probability errors (0 best); log loss penalises low probability assigned to the actual outcome.")
        ordered = sorted(graded, key=lambda item: item[0]["kickoff"])
        chart_rows, correct_count = [], 0
        for index, (_, score) in enumerate(ordered, 1):
            correct_count += score["correct"]
            chart_rows.append({"Evaluated matches": index, "Cumulative accuracy": 100 * correct_count / index})
        st.subheader("Accuracy over evaluated matches")
        st.line_chart(pd.DataFrame(chart_rows).set_index("Evaluated matches"), y="Cumulative accuracy")
    else:
        st.info("Performance charts will appear after saved matches finish and you check final scores.")
    st.subheader("Saved predictions")
    for record in records:
        score = prediction_scores(record)
        label = f'{record["home"]} vs {record["away"]} · {local_kickoff(record["kickoff"])}'
        with st.expander(label, expanded=False):
            st.write(f'**Status:** {record["status"]}')
            st.write(f'**Saved at:** {record["saved_at"][:16].replace("T", " ")} UTC')
            st.write(f'**Home / Draw / Away:** {record["home_win"]:.1%} / {record["draw"]:.1%} / {record["away_win"]:.1%}')
            st.write(f'**Over 2.5:** {record["over_2_5"]:.1%} · **BTTS:** {record["btts"]:.1%}')
            st.write(f'**Expected goals:** {record["home_xg"]:.2f} / {record["away_xg"]:.2f} · **Risk:** {record["risk"]}')
            if score:
                st.write(f'**Final score:** {record["score_home"]}–{record["score_away"]} · **Actual outcome:** {score["actual"]}')
                st.write(f'**Brier:** {score["brier"]:.3f} · **Log loss:** {score["logloss"]:.3f} · **Outcome pick correct:** {"Yes" if score["correct"] else "No"}')


def show_prediction(match, risk_only=False):
    home = (match.get('homeTeam') or {}).get('name') or 'Home'
    away = (match.get('awayTeam') or {}).get('name') or 'Away'
    st.title('🛡️ Risk Analysis' if risk_only else '🎯 Match Predictions')
    st.caption(f'{home} vs {away} · {local_kickoff(match.get("utcDate"))}')
    prediction, error = get_match_prediction(match)
    if error:
        st.warning(error)
        return
    p = prediction
    if not risk_only:
        match_key = str(match.get('id'))
        if st.button('💾 Save prediction to Supabase', key=f'save_prediction_{match_key}', type='primary'):
            saved, message = save_session_prediction(match, p)
            (st.success if saved else st.warning)(message)
    st.info('Experimental independent-Poisson model. Estimates are not calibrated, validated, or guarantees of match outcomes.')
    st.subheader('Match result probabilities')
    for label, value in [('Home win', p['home_win']), ('Draw', p['draw']), ('Away win', p['away_win'])]:
        st.markdown(f'**{label}: {value:.1%}**')
        st.progress(min(1.0, max(0.0, value)))
    a, b = st.columns(2)
    a.metric('Expected home goals', f"{p['home_xg']:.2f}")
    b.metric('Expected away goals', f"{p['away_xg']:.2f}")
    st.subheader('Goals markets')
    cols = st.columns(3)
    for col, (line, prob) in zip(cols, p['overs'].items()):
        col.metric(f'Over {line} goals', f'{prob:.1%}')
    cols = st.columns(2)
    cols[0].metric('Both teams to score — Yes', f"{p['btts']:.1%}")
    cols[1].metric('Both teams to score — No', f"{1-p['btts']:.1%}")
    if not risk_only:
        st.subheader('Most likely exact scorelines')
        for h, a, prob in p['scorelines']:
            st.write(f'{home} {h}–{a} {away} · {prob:.1%}')
    st.subheader('Model risk and data quality')
    st.markdown(f"**{p['risk']}**")
    st.caption('This risk label reflects sample size and how concentrated the model probabilities are. It is not a measured error rate or betting advice.')
    st.write(f"Historical sample: {p['home_sample']} {home} matches ({p['home_venue_sample']} at home), "
             f"{p['away_sample']} {away} matches ({p['away_venue_sample']} away).")
    st.caption('Method: home/away goals scored and conceded; five-match smoothing toward an assumed 1.35 goals per team; independent Poisson goals. No injuries, odds, xG, strength-of-schedule adjustment, or calibration. The final 12+ goal probability bucket is aggregated.')
    st.warning('Do not interpret these probabilities as proven accuracy. Historical backtesting is required before assessing model performance.')


def open_match_prediction(match):
    st.session_state.prediction_match = match
    st.session_state.dashboard_tab = 'Predictions'


def open_match_risk(match):
    st.session_state.prediction_match = match
    st.session_state.dashboard_tab = 'Risk Analysis'


def local_kickoff(utc_string):
    if not utc_string:
        return "Time TBC"
    try:
        kickoff = datetime.fromisoformat(utc_string.replace("Z", "+00:00"))
        return kickoff.astimezone(SA_TIMEZONE).strftime("%d %b %Y · %H:%M SAST")
    except ValueError:
        return "Time TBC"


def open_match_analysis(match):
    st.session_state.analysis_match = match
    st.session_state.dashboard_tab = "Match Analysis"


def change_dashboard_tab(tab):
    st.session_state.dashboard_tab = tab


def show_fixture(match, allow_analysis=False):
    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    home_name = home.get("shortName") or home.get("name") or "TBC"
    away_name = away.get("shortName") or away.get("name") or "TBC"
    status = match.get("status") or "UNKNOWN"
    score = (match.get("score") or {}).get("fullTime") or {}
    home_score, away_score = score.get("home"), score.get("away")
    if home_score is not None and away_score is not None:
        result = f"{home_score} – {away_score}"
    else:
        result = "vs"
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown(f"**{home_name}  {result}  {away_name}**")
            st.caption(local_kickoff(match.get("utcDate")))
        with right:
            st.caption(status.replace("_", " ").title())
            if allow_analysis and home.get("id") and away.get("id"):
                st.button(
                    "Analyse →", key=f"analyse_{match.get('id')}",
                    use_container_width=True, on_click=open_match_analysis, args=(match,)
                )
                if status in ('SCHEDULED', 'TIMED'):
                    st.button(
                        'Predict →', key=f"predict_{match.get('id')}",
                        use_container_width=True, on_click=open_match_prediction, args=(match,)
                    )


def get_competition_fixtures(competition, start_date, end_date):
    if not FOOTBALL_API_KEY:
        return [], "FOOTBALL_API_KEY is missing from Streamlit Secrets."
    return fetch_fixtures(
        COMPETITIONS[competition],
        start_date.isoformat(), end_date.isoformat(), FOOTBALL_API_KEY
    )


# ==========================================
# 3. LOAD STADIUM PNG
# ==========================================

image_path = (
    Path(__file__).parent
    / "assets"
    / "stadium.png"
)

if image_path.exists():

    image_base64 = base64.b64encode(
        image_path.read_bytes()
    ).decode("utf-8")

    stadium_background = (
        f"url('data:image/png;base64,{image_base64}')"
    )

else:
    stadium_background = "none"


# ==========================================
# 4. WEBSITE BACKGROUND
# ==========================================

if st.session_state.page == "home":

    background_css = f"""
        background-image:
            linear-gradient(
                90deg,
                rgba(5, 11, 21, 0.92) 0%,
                rgba(8, 17, 31, 0.78) 55%,
                rgba(9, 20, 35, 0.60) 100%
            ),
            {stadium_background};
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        background-repeat: no-repeat;
    """

else:

    background_css = """
        background: linear-gradient(
            120deg,
            #080D15 0%,
            #101C2B 55%,
            #17263A 100%
        );
    """


# ==========================================
# 5. WEBSITE STYLING
# ==========================================

css = """
<style>

/* Main background */
.stApp {
    __BACKGROUND_CSS__
    color: #F8FAFC;
}

/* Main container */
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Headings */
h1, h2, h3 {
    color: #F8FAFC !important;
}

/* Paragraphs */
p {
    color: #CBD5E1;
}

/* All buttons */
.stButton > button,
.stFormSubmitButton > button {
    background-color: #1B2A40;
    color: #FFFFFF !important;
    border: 1px solid #3B82F6;
    border-radius: 9px;
    font-weight: 600;
    min-height: 46px;
    transition: 0.2s ease;
}

/* Hover effects */
.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background-color: #263B58;
    color: #FFFFFF !important;
    border-color: #60A5FA;
}

/* Primary buttons */
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background-color: #2563EB;
    color: #FFFFFF !important;
    border: none;
}

/* Primary button hover */
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
    background-color: #1D4ED8;
    color: #FFFFFF !important;
}

/* Input fields */
.stTextInput input {
    background-color: #162337;
    color: #FFFFFF;
    border: 1px solid #334155;
    border-radius: 8px;
}

/* Input labels */
.stTextInput label {
    color: #E2E8F0 !important;
}

/* Forms */
[data-testid="stForm"] {
    background-color: rgba(20, 32, 49, 0.85);
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 25px;
}

/* Dividers */
hr {
    border-color: #334155;
}

/* Hide default footer */
footer {
    visibility: hidden;
}

</style>
"""

st.markdown(
    css.replace(
        "__BACKGROUND_CSS__",
        background_css
    ),
    unsafe_allow_html=True
)


# ==========================================
# 6. YANIDOLLARZ LOGO
# ==========================================

st.markdown("""
<h2 style="
    font-size:34px;
    font-weight:800;
    margin-bottom:0;
">
    YANI<span style="color:#3B82F6;">
    DOLLARZ</span>
</h2>

<p style="
    font-size:12px;
    letter-spacing:3px;
    color:#94A3B8;
    margin-top:5px;
">
    FOOTBALL PREDICTIONS & ANALYTICS
</p>
""", unsafe_allow_html=True)

st.divider()

if st.session_state.get("oauth_error"):
    st.error(st.session_state.oauth_error)
    st.session_state.oauth_error = None


# ==========================================
# 7. HOMEPAGE
# ==========================================

if st.session_state.page == "home":

    st.write("")
    st.write("")

    st.markdown("""
    <p style="
        color:#60A5FA;
        letter-spacing:4px;
        font-size:14px;
    ">
        FOOTBALL PREDICTIONS
    </p>

    <h1 style="
        font-size:52px;
        font-weight:800;
        line-height:1.35;
        text-shadow:0px 3px 15px rgba(0,0,0,0.5);
    ">
        SMARTER PREDICTIONS.<br>
        BETTER DECISIONS.
    </h1>

    <p style="
        font-size:18px;
        color:#E2E8F0;
        max-width:750px;
        line-height:1.8;
        text-shadow:0px 2px 8px rgba(0,0,0,0.7);
    ">
        Get detailed football match predictions,
        statistical analysis and risk insights
        for match results, goals, corners,
        bookings and more.
    </p>
    """, unsafe_allow_html=True)

    st.write("")

    if st.session_state.user is None:

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button(
                "Login →",
                type="primary",
                key="home_login",
                use_container_width=True
            ):
                navigate("login")

        with col2:
            if st.button(
                "Create Account",
                key="home_register",
                use_container_width=True
            ):
                navigate("register")

    else:

        if st.button(
            "Open Dashboard →",
            type="primary"
        ):
            navigate("dashboard")

    st.write("")
    st.write("")
    st.divider()

    st.subheader("What YANIDOLLARZ Offers")

    f1, f2, f3 = st.columns(3)

    with f1:
        st.markdown("### ⚽ Match Predictions")
        st.write(
            "Analyse match results, goals, "
            "corners and bookings."
        )

    with f2:
        st.markdown("### 🛡️ Risk Analysis")
        st.write(
            "Understand prediction probabilities "
            "and uncertainty."
        )

    with f3:
        st.markdown("### 📊 Performance Tracking")
        st.write(
            "Track previous predictions "
            "and model performance."
        )


# ==========================================
# 8. LOGIN PAGE
# ==========================================

elif st.session_state.page == "login":

    left, center, right = st.columns([1, 2, 1])

    with center:

        st.write("")

        st.markdown("""
        <h2 style="text-align:center;">
            Welcome Back
        </h2>

        <p style="
            text-align:center;
            color:#94A3B8;
        ">
            Login to access your football
            predictions and analysis.
        </p>
        """, unsafe_allow_html=True)

        with st.form("login_form"):

            email = st.text_input(
                "Email Address",
                placeholder="Enter your email"
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password"
            )

            login_submit = st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True
            )

            if login_submit:

                if not email or not password:

                    st.warning(
                        "Please enter your email "
                        "and password."
                    )

                else:

                    try:
                        supabase = get_supabase()

                        response = (
                            supabase.auth.sign_in_with_password({
                                "email": email.strip(),
                                "password": password
                            })
                        )

                        if (
                            response.user
                            and response.session
                        ):

                            st.session_state.user = (
                                response.user
                            )

                            st.session_state.auth_session = (
                                response.session
                            )

                            st.session_state.page = (
                                "dashboard"
                            )

                            st.rerun()

                        else:

                            st.error(
                                "Login failed. "
                                "Please try again."
                            )

                    except AuthApiError:

                        st.error(
                            "Login failed. Check your "
                            "email and password, and "
                            "make sure your email "
                            "is verified."
                        )

                    except Exception:

                        st.error(
                            "Unable to log in right now. "
                            "Please try again."
                        )

        st.write("")

        st.markdown(
            "<p style='text-align:center;'>OR</p>",
            unsafe_allow_html=True
        )

        google_button()

        st.write("")

        if st.button(
            "Create an Account",
            key="login_register",
            use_container_width=True
        ):
            navigate("register")

        if st.button(
            "← Back to Home",
            key="login_back",
            use_container_width=True
        ):
            navigate("home")


# ==========================================
# 9. CREATE ACCOUNT PAGE
# ==========================================

elif st.session_state.page == "register":

    left, center, right = st.columns([1, 2, 1])

    with center:

        st.write("")

        st.markdown("""
        <h2 style="text-align:center;">
            Create Your Account
        </h2>

        <p style="
            text-align:center;
            color:#94A3B8;
        ">
            Join YANIDOLLARZ and start
            analysing football matches.
        </p>
        """, unsafe_allow_html=True)

        with st.form("register_form"):

            username = st.text_input(
                "Username",
                placeholder="Choose a username"
            )

            email = st.text_input(
                "Email Address",
                placeholder="Enter your email"
            )

            password = st.text_input(
                "Create Password",
                type="password",
                placeholder="Create a password"
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Confirm your password"
            )

            register_submit = st.form_submit_button(
                "Create Account",
                type="primary",
                use_container_width=True
            )

            if register_submit:

                if not all([
                    username,
                    email,
                    password,
                    confirm_password
                ]):

                    st.warning(
                        "Please complete all fields."
                    )

                elif password != confirm_password:

                    st.error(
                        "Passwords do not match."
                    )

                elif len(password) < 8:

                    st.warning(
                        "Password must contain "
                        "at least 8 characters."
                    )

                else:

                    try:
                        supabase = get_supabase()

                        response = supabase.auth.sign_up({
                            "email": email.strip(),
                            "password": password,
                            "options": {
                                "data": {
                                    "username": username.strip()
                                }
                            }
                        })

                        if response.user:

                            st.success(
                                "Registration request "
                                "received! Please check "
                                "your email for a "
                                "verification link."
                            )

                        else:

                            st.info(
                                "Please check your email "
                                "for further instructions."
                            )

                    except AuthApiError as e:

                        st.error(
                            f"Registration failed: {e.message}"
                        )

                    except Exception:

                        st.error(
                            "Registration could not be "
                            "completed. Please try again."
                        )

        st.write("")

        st.markdown(
            "<p style='text-align:center;'>OR</p>",
            unsafe_allow_html=True
        )

        google_button()

        st.write("")

        if st.button(
            "Already have an account? Login",
            key="register_login",
            use_container_width=True
        ):
            navigate("login")

        if st.button(
            "← Back to Home",
            key="register_back",
            use_container_width=True
        ):
            navigate("home")


# ==========================================
# 10. USER DASHBOARD
# ==========================================

elif st.session_state.page == "dashboard":

    if (st.session_state.user is None
            or st.session_state.auth_session is None):
        st.warning("Please log in first.")
        if st.button("Go to Login"):
            navigate("login")
        st.stop()

    # Keep the same Supabase login validation as the original app.
    try:
        client = get_supabase()
        session = st.session_state.auth_session
        auth_result = client.auth.set_session(
            session.access_token, session.refresh_token
        )
        refreshed = client.auth.get_session()
        if refreshed is None:
            raise ValueError("Session expired")
        verified = client.auth.get_user(refreshed.access_token)
        if verified.user is None:
            raise ValueError("Invalid user")
        st.session_state.user = verified.user
        st.session_state.auth_session = refreshed
    except Exception:
        st.session_state.user = None
        st.session_state.auth_session = None
        st.warning("Your session has expired. Please log in again.")
        if st.button("Return to Login"):
            navigate("login")
        st.stop()

    user = st.session_state.user
    metadata = user.user_metadata or {}
    username = (
        metadata.get("username")
        or metadata.get("full_name")
        or (user.email.split("@")[0] if user.email else "Football Fan")
    )

    st.markdown("""
    <style>
      div[data-testid="stMetric"] {
        background: #16263b;
        border: 1px solid #2c425e;
        border-radius: 14px;
        padding: 18px 20px;
      }
      div[data-testid="stMetric"] label {color:#b8c9dd !important;}
      div[data-testid="stMetricValue"] {color:#f8fafc !important;}
      div[data-testid="stRadio"] > div {gap: 0.4rem;}
      div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #2c425e;
        border-radius: 14px;
      }

    /* STEP 16.2 — stadium hero, fixed sidebar and logo tiles */
    section[data-testid="stSidebar"] {background:linear-gradient(180deg,#031125 0%,#051c38 67%,#07316a 100%) !important;border-right:1px solid #13528b;}
    section[data-testid="stSidebar"] > div {background-image:linear-gradient(180deg,transparent 52%,rgba(3,15,33,.15) 64%,rgba(3,15,33,.15) 100%),url("data:image/webp;base64,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");background-size:100% 100%,100% auto;background-position:center,center bottom;background-repeat:no-repeat;}
    section[data-testid="stSidebar"] .stButton button {text-align:left;justify-content:flex-start;border:1px solid #15385d;background:#071e3a;color:#e9f4ff;border-radius:12px;font-weight:650;min-height:42px;}
    section[data-testid="stSidebar"] .stButton button:hover {background:#0865cf;border-color:#24a9ff;color:white;}
    .yani-sidebar-brand {font-size:22px;font-weight:900;color:#fff;letter-spacing:-.7px;margin:12px 0 2px;}
    .yani-sidebar-brand span {color:#1caaff;}
    .yani-sidebar-tag {font-size:9px;letter-spacing:1.6px;color:#59c4ff;margin-bottom:20px;}
    .yani-sidebar-slogan {border:1px solid #1385e4;background:rgba(1,20,48,.82);border-radius:15px;padding:17px 12px;margin-top:20px;font-weight:900;color:white;text-align:center;line-height:1.7;}
    .yani-sidebar-slogan span {color:#1ab6ff;}
    .yani-hero {background-image:linear-gradient(90deg,#06162c 0%,rgba(5,23,47,.95) 27%,rgba(5,23,47,.33) 66%,rgba(5,23,47,.06) 100%),url("data:image/webp;base64,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") !important;background-position:center,right center !important;background-size:cover,auto 100% !important;background-repeat:no-repeat !important;min-height:185px;}
    .yani-league img {height:42px;width:55px;object-fit:contain;display:block;margin:0 auto 8px;}
    .yani-league {height:100px;padding:12px 3px;}
    div[data-testid="stRadio"][aria-label="Dashboard navigation"] {display:none;}
    /* STEP 16 — vibrant dashboard, scoped to the logged-in view */
    .yani-hero {border:1px solid #1d5592; border-radius:20px; padding:28px 30px; margin:4px 0 20px;
      background:radial-gradient(ellipse at 84% 10%,rgba(27,157,255,.32),transparent 44%),linear-gradient(110deg,#07182f 10%,#0a3260 64%,#071526 100%);
      box-shadow:0 12px 32px rgba(0,0,0,.22);}
    .yani-hero-kicker{color:#71c7ff;font-size:11px;letter-spacing:2.3px;font-weight:800;}
    .yani-hero-title{font-size:clamp(27px,3.4vw,48px);font-weight:900;letter-spacing:-1.2px;line-height:1.3;color:white;}
    .yani-hero-title span{color:#24a8ff;}
    .yani-hero-sub{font-size:17px;color:#bfe5ff;margin-top:5px;}
    .yani-hero-foot{font-size:10px;color:#80b7e6;letter-spacing:1.3px;margin-top:16px;}
    .yani-hero-foot span{color:#32e7bb;padding:0 8px;}
    .yani-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:25px;}
    .yani-stat{min-width:0;border-radius:15px;padding:18px 17px;border:1px solid rgba(255,255,255,.17);box-shadow:0 8px 20px rgba(0,0,0,.15);}
    .yani-stat.blue{background:linear-gradient(125deg,#087cff,#08318a);}
    .yani-stat.green{background:linear-gradient(125deg,#00a96c,#054a3d);}
    .yani-stat.purple{background:linear-gradient(125deg,#8b36f7,#32147b);}
    .yani-stat.orange{background:linear-gradient(125deg,#f59e0b,#8e4107);}
    .yani-stat-top{font-size:12px;font-weight:700;color:#f4f8ff;display:flex;align-items:center;gap:8px;}
    .yani-stat-top span{font-size:25px;}
    .yani-stat-number{font-size:36px;line-height:1.35;font-weight:850;color:white;}
    .yani-stat-sub{font-size:11px;color:#e1eafa;}
    .yani-section-heading{font-size:20px;font-weight:800;color:#f4f8ff;margin:14px 0 1px;}
    .yani-empty{height:245px;display:flex;flex-direction:column;align-items:center;justify-content:center;
      border:1px solid #234565;border-radius:14px;background:linear-gradient(145deg,#0c2038,#102b48);gap:10px;text-align:center;}
    .yani-empty div{font-size:42px;}.yani-empty strong{color:#e8f3ff;}.yani-empty small{color:#9eb9d1;max-width:270px;}
    .yani-match{display:flex;align-items:center;justify-content:space-between;gap:10px;background:linear-gradient(120deg,#112b49,#0b1b32);
      border:1px solid #274461;border-radius:13px;padding:13px 14px;margin:8px 0;}
    .yani-match strong{font-size:13px;color:#f0f6ff;}.yani-match strong span{color:#55b5ff;padding:0 5px;}
    .yani-match small{display:block;font-size:11px;color:#9eb9d1;margin-top:5px;}
    .yani-pill{white-space:nowrap;border-radius:25px;padding:5px 9px;font-size:10px;font-weight:750;}
    .yani-pill.pending{color:#ffcb69;background:rgba(245,158,11,.14);border:1px solid rgba(245,158,11,.42);}
    .yani-pill.finished{color:#67e8ae;background:rgba(16,185,129,.14);border:1px solid rgba(16,185,129,.42);}
    .yani-breakdown{font-size:12px;color:#cbdff4;margin:8px 0 20px;}
    .yani-league{text-align:center;border:1px solid #254462;border-radius:14px;padding:16px 4px;
      background:linear-gradient(145deg,#13345a,#0c1b32);font-size:26px;min-height:90px;}
    .yani-league small{display:block;color:#e3f0ff;font-size:10px;margin-top:8px;}
    @media(max-width:850px){.yani-stats{grid-template-columns:repeat(2,minmax(0,1fr));}.yani-hero{padding:22px 18px;}}
    </style>
    """, unsafe_allow_html=True)

    # Sidebar navigation uses callbacks so dashboard_tab is updated before
    # the radio widget is instantiated (avoids Streamlit session-state errors).
    with st.sidebar:
        st.markdown('<div class="yani-sidebar-brand">⚽ YANI<span>DOLLARZ</span></div><div class="yani-sidebar-tag">PREDICTION INTELLIGENCE</div>', unsafe_allow_html=True)
        sidebar_links = [
            ("🏠 Dashboard", "Dashboard"),
            ("🎯 Make Predictions", "Predictions"),
            ("📅 Upcoming Matches", "Fixtures"),
            ("🕘 Prediction History", "History"),
            ("📈 Performance", "Dashboard"),
            ("🔍 Match Analysis", "Match Analysis"),
            ("⚠️ Risk Analysis", "Risk Analysis"),
        ]
        for i, (caption, tab_name) in enumerate(sidebar_links):
            st.button(caption, key=f"sidebar_nav_{i}", use_container_width=True,
                      on_click=change_dashboard_tab, args=(tab_name,))
        st.markdown('<div class="yani-sidebar-slogan">🏆 PREDICT<br>ANALYSE<br><span>TRACK<br>WIN</span></div>', unsafe_allow_html=True)
        st.caption("Live football data • YANIDOLLARZ")

    top_left, top_right = st.columns([5, 1])
    with top_left:
        st.caption("⚽ YANIDOLLARZ / FOOTBALL INTELLIGENCE")
    with top_right:
        if st.button("🚪 Logout", key="dashboard_logout", use_container_width=True):
            logout()

    tabs = ["Dashboard", "Fixtures", "Match Analysis", "Predictions", "Risk Analysis", "History"]
    selected = st.radio(
        "Dashboard navigation", tabs, horizontal=True,
        label_visibility="collapsed", key="dashboard_tab"
    )
    st.divider()

    if selected == "Dashboard":
        st.markdown("""
        <div class="yani-hero">
          <div class="yani-hero-kicker">⚽ FOOTBALL PREDICTION INTELLIGENCE</div>
          <div class="yani-hero-title">WELCOME TO <span>YANIDOLLARZ</span></div>
          <div class="yani-hero-sub">Analyse. Predict. Track. Win.</div>
          <div class="yani-hero-foot">LIVE FOOTBALL DATA <span>•</span> YOUR PERSONAL PERFORMANCE HUB</div>
        </div>
        """, unsafe_allow_html=True)

        try:
            dashboard_history = load_prediction_history()
            history_error = None
        except Exception:
            logger.exception("Dashboard history unavailable")
            dashboard_history = []
            history_error = "Your prediction history could not be loaded. Check your Supabase connection."
        if history_error:
            st.warning(history_error)

        finished = [(r, prediction_scores(r)) for r in dashboard_history if r.get("status") == "Finished"]
        finished = [(r, score) for r, score in finished if score is not None]
        pending = sum(r.get("status") == "Pending" for r in dashboard_history)
        correct = sum(score["correct"] for _, score in finished)
        incorrect = len(finished) - correct
        accuracy = (100 * correct / len(finished)) if finished else None

        stats = [
            ("📋", "TOTAL PREDICTIONS", str(len(dashboard_history)), "Saved matches", "blue"),
            ("🎯", "ACCURACY", f"{accuracy:.1f}%" if accuracy is not None else "—", "Completed outcomes only", "green"),
            ("🏆", "COMPLETED", str(len(finished)), "Evaluated matches", "purple"),
            ("🕒", "PENDING", str(pending), "Awaiting final results", "orange"),
        ]
        cards = "".join(
            f'<div class="yani-stat {color}"><div class="yani-stat-top"><span>{icon}</span>{label}</div>'
            f'<div class="yani-stat-number">{value}</div><div class="yani-stat-sub">{detail}</div></div>'
            for icon, label, value, detail, color in stats
        )
        st.markdown(f'<div class="yani-stats">{cards}</div>', unsafe_allow_html=True)

        left, right = st.columns([1.55, 1], gap="medium")
        with left:
            st.markdown('<div class="yani-section-heading">📈 Prediction Performance</div>', unsafe_allow_html=True)
            st.caption("Cumulative outcome accuracy across your completed predictions")
            if finished:
                ordered = sorted(finished, key=lambda pair: pair[0].get("kickoff", ""))
                running = 0
                chart_rows = []
                for idx, (_, result) in enumerate(ordered, 1):
                    running += result["correct"]
                    chart_rows.append({"Match": idx, "Accuracy (%)": 100 * running / idx})
                st.line_chart(pd.DataFrame(chart_rows).set_index("Match"), color="#38BDF8", height=245)
            else:
                st.markdown('<div class="yani-empty"><div>📊</div><strong>No completed matches yet</strong><small>Your accuracy chart will appear when saved matches finish.</small></div>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="yani-section-heading">🥧 Prediction Breakdown</div>', unsafe_allow_html=True)
            st.caption("Correct, incorrect and pending predictions")
            if dashboard_history:
                breakdown = pd.DataFrame({"Status": ["Correct", "Incorrect", "Pending"], "Count": [correct, incorrect, pending]})
                breakdown = breakdown[breakdown["Count"] > 0]
                st.bar_chart(breakdown.set_index("Status"), color="#38BDF8", height=245)
            else:
                st.info("Save a prediction to see your breakdown.")
            st.markdown(f'<div class="yani-breakdown">🟢 Correct: <b>{correct}</b> &nbsp; 🔴 Incorrect: <b>{incorrect}</b> &nbsp; 🟠 Pending: <b>{pending}</b></div>', unsafe_allow_html=True)

        left, right = st.columns([1.55, 1], gap="medium")
        with left:
            st.markdown('<div class="yani-section-heading">🕘 Recent Predictions</div>', unsafe_allow_html=True)
            st.caption("Your latest saved predictions from Supabase")
            if dashboard_history:
                for record in dashboard_history[:5]:
                    status = record.get("status", "Pending")
                    badge = "finished" if status == "Finished" else "pending"
                    title = html.escape(str(record.get("home", "Home"))) + " <span>VS</span> " + html.escape(str(record.get("away", "Away")))
                    when = html.escape(local_kickoff(record.get("kickoff")))
                    result = ""
                    if status == "Finished" and record.get("score_home") is not None and record.get("score_away") is not None:
                        result = f' · {record["score_home"]}–{record["score_away"]}'
                    st.markdown(f'<div class="yani-match"><div><strong>{title}</strong><small>{when}{result}</small></div><span class="yani-pill {badge}">{html.escape(status)}</span></div>', unsafe_allow_html=True)
            else:
                st.info("No saved predictions yet. Open Fixtures and save your first prediction.")
            st.button("📚 Open Prediction History", key="dash_history", on_click=change_dashboard_tab, args=("History",), use_container_width=True)
        with right:
            st.markdown('<div class="yani-section-heading">📅 Upcoming Matches</div>', unsafe_allow_html=True)
            st.caption("Premier League · Next 7 days · SAST")
            today = datetime.now(SA_TIMEZONE).date()
            upcoming_matches, upcoming_error = get_competition_fixtures("Premier League", today, today + timedelta(days=7))
            if upcoming_error:
                st.warning(upcoming_error)
            else:
                scheduled = sorted((m for m in upcoming_matches if m.get("status") in ("SCHEDULED", "TIMED")), key=lambda m: m.get("utcDate", ""))
                if scheduled:
                    for match in scheduled[:4]:
                        home = html.escape(str((match.get("homeTeam") or {}).get("shortName") or (match.get("homeTeam") or {}).get("name") or "Home"))
                        away = html.escape(str((match.get("awayTeam") or {}).get("shortName") or (match.get("awayTeam") or {}).get("name") or "Away"))
                        when = html.escape(local_kickoff(match.get("utcDate")))
                        st.markdown(f'<div class="yani-match"><div><strong>{home} <span>VS</span> {away}</strong><small>{when}</small></div><span class="yani-pill pending">Upcoming</span></div>', unsafe_allow_html=True)
                else:
                    st.info("No Premier League matches in the next 7 days.")
            st.button("⚽ Browse Fixtures", key="dash_fixtures", on_click=change_dashboard_tab, args=("Fixtures",), use_container_width=True)

        st.markdown('<div class="yani-section-heading">🏆 Explore Top Leagues</div>', unsafe_allow_html=True)
        league_cols = st.columns(6)
        league_tiles = [("PL", "Premier League"), ("PD", "La Liga"), ("SA", "Serie A"), ("BL1", "Bundesliga"), ("FL1", "Ligue 1"), ("CL", "Champions League")]
        for col, (code, league_name) in zip(league_cols, league_tiles):
            with col:
                # Official competition crests from football-data.org's crest CDN.
                emblem = f"https://crests.football-data.org/{code}.png"
                st.markdown(f'<div class="yani-league"><img src="{emblem}" alt="{league_name} logo" loading="lazy"><small>{league_name}</small></div>', unsafe_allow_html=True)
        st.caption("League tiles are visual shortcuts; use Fixtures to select competitions and analyse matches.")

    elif selected == "Fixtures":
        st.title("📅 Football Fixtures")
        st.caption("Real fixtures from football-data.org · Kickoff times in SAST")
        league = st.selectbox("Select competition", list(COMPETITIONS), key="fixture_league")
        today = datetime.now(SA_TIMEZONE).date()
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input("From", value=today, key="fixture_start")
        with date_col2:
            end_date = st.date_input("To", value=today + timedelta(days=7), key="fixture_end")
        if end_date < start_date:
            st.warning("The end date must be on or after the start date.")
        elif (end_date - start_date).days > 30:
            st.warning("Choose a date range of 30 days or less.")
        else:
            matches, error = get_competition_fixtures(league, start_date, end_date)
            if error:
                st.warning(error)
            else:
                matches.sort(key=lambda m: m.get("utcDate", ""))
                st.caption(f"{len(matches)} match(es) returned · {league}")
                if not matches:
                    st.info("No fixtures found for this competition and date range.")
                for match in matches:
                    show_fixture(match, allow_analysis=True)
        if st.button("🔄 Refresh fixtures", key="refresh_fixtures"):
            fetch_fixtures.clear()
            st.rerun()

    elif selected == "Match Analysis":
        match = st.session_state.get("analysis_match")
        if match:
            st.button("← Back to Fixtures", key="analysis_back", on_click=change_dashboard_tab, args=("Fixtures",))
            show_match_analysis(match)
        else:
            st.title("🔎 Match Analysis")
            st.info("Go to Fixtures and click Analyse → beside a match to view its statistics.")
            st.button("Browse Fixtures", key="analysis_browse", on_click=change_dashboard_tab, args=("Fixtures",))

    elif selected == "Predictions":
        match = st.session_state.get('prediction_match')
        if match:
            st.button('← Back to Fixtures', key='pred_back',
                      on_click=change_dashboard_tab, args=('Fixtures',))
            show_prediction(match)
        else:
            st.title('🎯 Match Predictions')
            st.info('Open Fixtures and click Predict → next to an upcoming match.')
            st.button('Browse Fixtures', key='pred_browse',
                      on_click=change_dashboard_tab, args=('Fixtures',))

    elif selected == "Risk Analysis":
        match = st.session_state.get('prediction_match')
        if match:
            st.button('← Back to Fixtures', key='risk_back',
                      on_click=change_dashboard_tab, args=('Fixtures',))
            show_prediction(match, risk_only=True)
        else:
            st.title('🛡️ Risk Analysis')
            st.info('Select an upcoming fixture using Predict → to view model uncertainty.')

    elif selected == "History":
        show_prediction_history()


# ==========================================
# 11. FOOTER
# ==========================================

st.write("")
st.write("")

st.markdown("""
<div style="
    text-align:center;
    color:#64748B;
    font-size:12px;
    padding:20px;
">
    © 2026 YANIDOLLARZ |
    Football Predictions & Analytics
</div>
""", unsafe_allow_html=True)