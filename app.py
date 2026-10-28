
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
    initial_sidebar_state="collapsed"
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


def calculate_prediction(home_matches, away_matches, home_id, away_id, expected_override=None):
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

    if expected_override is not None:
        home_xg, away_xg = expected_override
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




def advanced_expected_goals(home_matches, away_matches, home_id, away_id, league_history=None):
    """Venue-aware recency-weighted scoring rates, normalized by prior league scoring.

    Inputs MUST be completed matches before the target kickoff. The historical
    league reference is never computed from the match being evaluated.
    """
    home_all = team_statistics(home_matches, home_id)
    away_all = team_statistics(away_matches, away_id)
    hv = team_statistics(home_matches, home_id, "Home")
    av = team_statistics(away_matches, away_id, "Away")
    if (not home_all or not away_all or not hv or not av or
            min(home_all['played'], away_all['played']) < 5 or
            min(hv['played'], av['played']) < 3):
        return None, "Insufficient historical matches for advanced model."

    # A league average requires at least 20 previously completed matches.
    # Otherwise use an explicit neutral prior, not a claimed measured average.
    finished = [m for m in (league_history or []) if
                m.get('status') == 'FINISHED' and
                (m.get('score') or {}).get('fullTime', {}).get('home') is not None and
                (m.get('score') or {}).get('fullTime', {}).get('away') is not None]
    if len(finished) >= 20:
        league_home = sum(m['score']['fullTime']['home'] for m in finished) / len(finished)
        league_away = sum(m['score']['fullTime']['away'] for m in finished) / len(finished)
        source = f"{len(finished)} earlier league matches"
    else:
        league_home, league_away = 1.45, 1.15
        source = "assumed 1.45 home / 1.15 away goals (insufficient league data)"
    league_home = max(0.4, league_home)
    league_away = max(0.4, league_away)

    def weighted_rate(matches, team_id, venue, key, prior):
        recent = sorted((m for m in matches if team_result(m, team_id) and
                         team_result(m, team_id)['venue'] == venue),
                        key=lambda m: m.get('utcDate', ''), reverse=True)[:15]
        # Exponential recency decay: most recent matches count more.
        weights = [0.88 ** i for i in range(len(recent))]
        total = sum(weights)
        observed = sum(w * team_result(m, team_id)[key] for w, m in zip(weights, recent))
        return (observed + 4.0 * prior) / (total + 4.0)

    home_attack = weighted_rate(home_matches, home_id, 'Home', 'gf', league_home)
    home_defense = weighted_rate(home_matches, home_id, 'Home', 'ga', league_away)
    away_attack = weighted_rate(away_matches, away_id, 'Away', 'gf', league_away)
    away_defense = weighted_rate(away_matches, away_id, 'Away', 'ga', league_home)
    # Multiplicative attack/defense strength relative to the venue-specific baseline.
    home_xg = league_home * (home_attack / league_home) * (away_defense / league_home)
    away_xg = league_away * (away_attack / league_away) * (home_defense / league_away)
    return (max(0.15, min(4.0, home_xg)), max(0.15, min(4.0, away_xg)), source), None


def calculate_advanced_prediction(home_matches, away_matches, home_id, away_id, league_history=None):
    rates, error = advanced_expected_goals(home_matches, away_matches, home_id, away_id, league_history)
    if error:
        return None, error
    result, error = calculate_prediction(home_matches, away_matches, home_id, away_id,
                                         expected_override=rates[:2])
    if result is not None:
        result['league_reference'] = rates[2]
        result['model_version'] = 'advanced_recency_v1'
    return result, error

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
    # Retrieve league matches before kickoff for a real, venue-specific baseline.
    # This is cached and does not expose the API token in client-side code.
    comp = (match.get('competition') or {}).get('code')
    league_history = []
    if comp and FOOTBALL_API_KEY:
        kickoff_day = datetime.fromisoformat(kickoff.replace('Z', '+00:00')).date()
        start_day = kickoff_day - timedelta(days=180)
        historical, api_error = fetch_fixtures(comp, start_day.isoformat(), kickoff_day.isoformat(), FOOTBALL_API_KEY)
        if not api_error:
            league_history = [m for m in historical if completed_before(m, kickoff)]
    return calculate_advanced_prediction(hm, am, home_id, away_id, league_history)


# ==========================================
# WALK-FORWARD BACKTESTING & CALIBRATION
# ==========================================

def backtest_competition(matches):
    """Replay completed fixtures chronologically, never training on the target or later games.

    Only matches returned for the selected competition/date window are used.
    This makes the test conservative: early fixtures often have insufficient history.
    """
    finished = []
    for m in matches:
        score = (m.get("score") or {}).get("fullTime") or {}
        if (m.get("status") == "FINISHED" and m.get("utcDate")
                and score.get("home") is not None and score.get("away") is not None
                and (m.get("homeTeam") or {}).get("id")
                and (m.get("awayTeam") or {}).get("id")):
            finished.append(m)
    finished.sort(key=lambda m: (m["utcDate"], m.get("id") or 0))
    # A shared pool only contains games strictly earlier than each evaluated kickoff.
    # Do not use a same-time match as history, even if it was processed earlier.
    rows = []
    for m in finished:
        kickoff = m["utcDate"]
        home_id = m["homeTeam"]["id"]
        away_id = m["awayTeam"]["id"]
        history = [prior for prior in finished if prior["utcDate"] < kickoff]
        home_history = [prior for prior in history
                        if home_id in ((prior.get("homeTeam") or {}).get("id"),
                                       (prior.get("awayTeam") or {}).get("id"))]
        away_history = [prior for prior in history
                        if away_id in ((prior.get("homeTeam") or {}).get("id"),
                                       (prior.get("awayTeam") or {}).get("id"))]
        # Match the production history limit and newest-first ordering.
        home_history = home_history[-30:][::-1]
        away_history = away_history[-30:][::-1]
        baseline, error = calculate_prediction(home_history, away_history, home_id, away_id)
        if error:
            continue
        prediction, error = calculate_advanced_prediction(home_history, away_history,
                            home_id, away_id, history)
        if error:
            continue
        score = m["score"]["fullTime"]
        actual = 0 if score["home"] > score["away"] else 1 if score["home"] == score["away"] else 2
        probabilities = [prediction["home_win"], prediction["draw"], prediction["away_win"]]
        rows.append({
            "Baseline Home": baseline['home_win'],
            "Baseline Draw": baseline['draw'],
            "Baseline Away": baseline['away_win'],
            "Baseline Over 2.5": baseline['overs'][2.5],
            "Baseline BTTS": baseline['btts'],
            "Date": kickoff[:10], "Match ID": m.get("id"),
            "Home team ID": home_id, "Away team ID": away_id,
            "Match": f'{m["homeTeam"].get("shortName") or m["homeTeam"].get("name")} vs {m["awayTeam"].get("shortName") or m["awayTeam"].get("name")}',
            "Home": probabilities[0], "Draw": probabilities[1], "Away": probabilities[2],
            "Actual": ["Home", "Draw", "Away"][actual],
            "Correct": int(max(range(3), key=lambda i: probabilities[i]) == actual),
            "Brier": sum((probabilities[i] - int(i == actual)) ** 2 for i in range(3)),
            "Log loss": -math.log(max(probabilities[actual], 1e-12)),
            "Confidence": max(probabilities),
            "Baseline Correct": int(max(range(3), key=lambda i: [baseline['home_win'], baseline['draw'], baseline['away_win']][i]) == actual),
            "Baseline Brier": sum((v - int(i == actual)) ** 2 for i, v in enumerate([baseline['home_win'], baseline['draw'], baseline['away_win']])),
            "Baseline Log loss": -math.log(max([baseline['home_win'], baseline['draw'], baseline['away_win']][actual], 1e-12)),
            "Over 2.5": prediction["overs"][2.5],
            "Over 2.5 actual": int(score["home"] + score["away"] >= 3),
            "BTTS": prediction["btts"],
            "BTTS actual": int(score["home"] > 0 and score["away"] > 0),
        })
    return finished, pd.DataFrame(rows)


def backtest_diagnostics(matches):
    """Explain coverage using strictly earlier results and the production sample rules."""
    valid = []
    invalid = 0
    for m in matches:
        score = ((m.get("score") or {}).get("fullTime") or {})
        if m.get("status") != "FINISHED":
            continue
        if (not m.get("utcDate") or score.get("home") is None or
            score.get("away") is None or not (m.get("homeTeam") or {}).get("id") or
            not (m.get("awayTeam") or {}).get("id")):
            invalid += 1
        else:
            valid.append(m)
    valid.sort(key=lambda m: (m["utcDate"], m.get("id") or 0))
    reasons = {"Insufficient team history (<5 each)": 0,
               "Insufficient venue history (<3 each)": 0,
               "Evaluated": 0, "Other model limitation": 0}
    for match in valid:
        kickoff = match["utcDate"]
        hid, aid = match["homeTeam"]["id"], match["awayTeam"]["id"]
        earlier = [m for m in valid if m["utcDate"] < kickoff]
        hm = [m for m in earlier if hid in ((m.get("homeTeam") or {}).get("id"), (m.get("awayTeam") or {}).get("id"))][-30:][::-1]
        am = [m for m in earlier if aid in ((m.get("homeTeam") or {}).get("id"), (m.get("awayTeam") or {}).get("id"))][-30:][::-1]
        if min(len(hm), len(am)) < 5:
            reasons["Insufficient team history (<5 each)"] += 1
        elif min(sum((m.get("homeTeam") or {}).get("id") == hid for m in hm),
                 sum((m.get("awayTeam") or {}).get("id") == aid for m in am)) < 3:
            reasons["Insufficient venue history (<3 each)"] += 1
        else:
            original, err1 = calculate_prediction(hm, am, hid, aid)
            advanced, err2 = calculate_advanced_prediction(hm, am, hid, aid, earlier)
            reasons["Evaluated" if original and advanced and not err1 and not err2 else "Other model limitation"] += 1
    if invalid:
        reasons["Incomplete result / missing team ID"] = invalid
    return reasons


def historical_outcome_baseline(matches):
    """Walk-forward home/draw/away frequencies, smoothed using uniform priors.

    Only prior matches from the SAME competition are included. Returns metrics
    keyed by fixture ID; no future result is used for an earlier prediction.
    """
    finished = [m for m in matches if m.get("status") == "FINISHED" and
                m.get("utcDate") and (m.get("id") is not None) and
                ((m.get("score") or {}).get("fullTime") or {}).get("home") is not None and
                ((m.get("score") or {}).get("fullTime") or {}).get("away") is not None]
    out = {}
    for match in finished:
        earlier = [m for m in finished if m["utcDate"] < match["utcDate"]]
        if not earlier:
            continue
        counts = [1.0, 1.0, 1.0]  # Laplace smoothing
        for m in earlier:
            sc = m["score"]["fullTime"]
            idx = 0 if sc["home"] > sc["away"] else 1 if sc["home"] == sc["away"] else 2
            counts[idx] += 1
        probs = [v / sum(counts) for v in counts]
        sc = match["score"]["fullTime"]
        actual = 0 if sc["home"] > sc["away"] else 1 if sc["home"] == sc["away"] else 2
        out[match["id"]] = {
            "Frequency baseline accuracy": int(max(range(3), key=lambda i: probs[i]) == actual),
            "Frequency baseline Brier": sum((v - int(i == actual)) ** 2 for i, v in enumerate(probs)),
            "Frequency baseline log loss": -math.log(max(probs[actual], 1e-12)),
        }
    return out


def backtest_clubs(matches):
    """Return confirmed teams from API results, not a manually maintained club list."""
    clubs = {}
    for match in matches:
        for side in ("homeTeam", "awayTeam"):
            team = match.get(side) or {}
            if team.get("id") is not None:
                clubs[int(team["id"])] = team.get("name") or team.get("shortName") or str(team["id"])
    return dict(sorted(clubs.items(), key=lambda item: item[1].casefold()))


def show_backtesting():
    st.title("🧪 Historical Backtesting & Calibration")
    st.info("Advanced recency-weighted Poisson vs original baseline, tested on identical fixtures. Model selection based on this sample is not independent validation.")
    st.caption("Walk-forward evaluation of the Poisson model using only earlier finished matches. Individual-club mode evaluates the selected club's matches, but still uses earlier league matches for training.")
    st.info("Backtesting runs only when you click Run. It does not save or modify your Supabase prediction history.")
    today = datetime.now(SA_TIMEZONE).date()
    league = st.selectbox("Competition", list(COMPETITIONS), index=0, key="backtest_league")
    left, right = st.columns(2)
    with left:
        start = st.date_input("Historical period — from", value=today - timedelta(days=240), key="backtest_start")
    with right:
        end = st.date_input("Historical period — to", value=today - timedelta(days=1), key="backtest_end")
    mode = st.radio("Backtest scope", ["Entire League", "Individual Club"], horizontal=True, key="backtest_scope")
    st.caption("The model needs at least 5 previous matches per team, including 3 at the relevant home/away venue. Earlier fixtures may be skipped.")
    if start >= end or end > today:
        st.error("Choose a valid historical period ending no later than today.")
        return

    # Fetch only when requested; cache the results in Streamlit session state.
    # Avoid an API request on every widget rerun and preserve the free-plan quota.
    source_key = (league, start.isoformat(), end.isoformat())
    cached = st.session_state.get("backtest_source")
    if st.button("🔄 Load clubs and matches", key="load_backtest_clubs"):
        with st.spinner("Loading clubs from football-data.org..."):
            matches, error = get_competition_fixtures(league, start, end)
        if error:
            st.error(error)
        else:
            cached = {"key": source_key, "matches": matches}
            st.session_state["backtest_source"] = cached
    source_matches = cached["matches"] if cached and cached["key"] == source_key else None
    clubs = backtest_clubs(source_matches) if source_matches is not None else {}
    club_id = None
    if mode == "Individual Club":
        if source_matches is None:
            st.info("Click **Load clubs and matches** to retrieve the available clubs for this competition and date range.")
        elif not clubs:
            st.warning("No clubs were found in the returned fixtures. Try a wider date range.")
        else:
            club_id = st.selectbox("Select club", list(clubs), format_func=lambda x: clubs[x], key="backtest_club")
            st.caption(f"Selected club: {clubs[club_id]}. Only its matches will count toward the performance results.")
    if st.button("▶ Run historical backtest", type="primary", key="run_backtest"):
        if mode == "Individual Club" and club_id is None:
            st.warning("Load the clubs and select one before running an individual-club backtest.")
            return
        if source_matches is None:
            with st.spinner("Fetching historical results..."):
                source_matches, error = get_competition_fixtures(league, start, end)
            if error:
                st.error(error)
                return
            st.session_state["backtest_source"] = {"key": source_key, "matches": source_matches}
        with st.spinner("Replaying historical predictions without future results..."):
            finished, all_results = backtest_competition(source_matches)
        if mode == "Individual Club":
            club_finished = [m for m in finished if club_id in (
                (m.get("homeTeam") or {}).get("id"),
                (m.get("awayTeam") or {}).get("id"))]
            results = all_results[(all_results["Home team ID"] == club_id) |
                                  (all_results["Away team ID"] == club_id)].copy() if not all_results.empty else all_results
            count_finished = len(club_finished)
            name = clubs[club_id]
        else:
            results, count_finished, name = all_results, len(finished), "Entire League"
        st.session_state["backtest_report"] = {
            "league": league, "start": start.isoformat(), "end": end.isoformat(),
            "scope": mode, "club": name, "finished": count_finished, "results": results,
        }
    report = st.session_state.get("backtest_report")
    if not report:
        st.info("Choose a competition, dates and scope, then run a backtest.")
        return
    st.caption(f'Latest run: {report["league"]} · {report["club"]} · {report["start"]} to {report["end"]}')
    results = report["results"]
    if results.empty:
        st.warning(f'{report["finished"]} finished matches found for this scope, but none had enough earlier match data. Try a longer date range. Your free API plan may restrict older seasons.')
        return
    n = len(results)
    a, b, c, d = st.columns(4)
    a.metric("Finished matches", report["finished"])
    b.metric("Evaluated", n)
    c.metric("Outcome accuracy", f'{results["Correct"].mean():.1%}')
    d.metric("Mean Brier", f'{results["Brier"].mean():.3f}')
    a, b, c = st.columns(3)
    a.metric("Mean log loss", f'{results["Log loss"].mean():.3f}')
    b.metric("Over 2.5 accuracy", f'{((results["Over 2.5"] >= 0.5).astype(int) == results["Over 2.5 actual"]).mean():.1%}')
    c.metric("BTTS accuracy", f'{((results["BTTS"] >= 0.5).astype(int) == results["BTTS actual"]).mean():.1%}')
    st.caption(f'Coverage: {n}/{report["finished"]} finished matches ({n / report["finished"]:.1%}). Historical training uses this competition only; live predictions may use multiple competitions.')
    st.caption("Lower Brier and log loss are better. Retrospective performance is not a guarantee of future results.")
    st.subheader("Original vs improved Poisson model")
    comparison = pd.DataFrame([
        {"Model": "Original Poisson", "Outcome accuracy": results["Baseline Correct"].mean(),
         "Mean Brier": results["Baseline Brier"].mean(), "Mean log loss": results["Baseline Log loss"].mean()},
        {"Model": "Advanced recency Poisson", "Outcome accuracy": results["Correct"].mean(),
         "Mean Brier": results["Brier"].mean(), "Mean log loss": results["Log loss"].mean()},
    ])
    st.dataframe(comparison.style.format({"Outcome accuracy": "{:.1%}", "Mean Brier": "{:.3f}", "Mean log loss": "{:.3f}"}), use_container_width=True, hide_index=True)
    st.caption("Both models use the same strictly earlier matches. Lower Brier/log loss is better. A separate future holdout is needed to establish an improvement.")
    st.subheader("Performance over time")
    ordered = results.sort_values("Date").reset_index(drop=True)
    performance = pd.DataFrame({
        "Matches evaluated": range(1, n + 1),
        "Cumulative accuracy (%)": (ordered["Correct"].cumsum() / pd.Series(range(1, n + 1)) * 100).values,
    })
    st.line_chart(performance.set_index("Matches evaluated"))
    st.subheader("Calibration: predicted confidence vs actual frequency")
    st.caption("For each confidence range, compare the average predicted probability with how often the predicted outcome actually happened. Small samples are noisy.")
    bins = [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 1.00001)]
    calibration = []
    for lo, hi in bins:
        sample = results[(results["Confidence"] >= lo) & (results["Confidence"] < hi)]
        if len(sample):
            calibration.append({"Confidence band": f"{lo:.0%}–{min(hi,1):.0%}",
                                "Matches": len(sample),
                                "Mean predicted (%)": round(sample["Confidence"].mean() * 100, 1),
                                "Observed correct (%)": round(sample["Correct"].mean() * 100, 1)})
    st.dataframe(pd.DataFrame(calibration), use_container_width=True, hide_index=True)
    if n < 50:
        st.warning("Small evaluation sample: these metrics may vary substantially. Don't tune the model and claim the same sample is independent validation.")
    st.subheader("Evaluated matches")
    display = results[["Date", "Match", "Actual", "Home", "Draw", "Away", "Correct", "Brier"]].copy()
    for key in ("Home", "Draw", "Away"):
        display[key] = (display[key] * 100).round(1)
    display["Brier"] = display["Brier"].round(3)
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.download_button("Download backtest results (CSV)", results.to_csv(index=False).encode("utf-8"),
                       file_name="yanidollarz_club_backtest.csv" if report["scope"] == "Individual Club" else "yanidollarz_league_backtest.csv", mime="text/csv")


def show_model_comparison():
    """Cross-league, walk-forward model comparison. Never modifies saved predictions."""
    st.title("📊 Model Comparison Dashboard")
    st.caption("Compare original and recency-weighted Poisson across multiple leagues and clubs using the same historical fixtures.")
    st.info("This is retrospective evaluation, not independent proof of future performance. Results are not saved to Supabase.")
    choices = st.multiselect("Competitions (up to 3 per run)", options=list(COMPETITIONS),
                             default=list(COMPETITIONS)[:2], max_selections=3,
                             key="comparison_leagues")
    today = datetime.now(SA_TIMEZONE).date()
    left, right = st.columns(2)
    with left:
        start = st.date_input("From", today - timedelta(days=240), key="comparison_from")
    with right:
        end = st.date_input("To", today - timedelta(days=1), key="comparison_to")
    st.caption("Each league is fetched once per run. The free football-data.org plan may limit historical availability or request volume.")
    if st.button("▶ Compare models", type="primary", key="run_model_comparison"):
        if not choices or start >= end or end > today:
            st.error("Select at least one league and a valid past date range.")
            return
        frames, issues, coverage, diagnostics = [], [], [], []
        progress = st.progress(0)
        for i, league in enumerate(choices):
            with st.spinner(f"Backtesting {league}..."):
                matches, error = get_competition_fixtures(league, start, end)
                if error:
                    issues.append(f"{league}: {error}")
                else:
                    finished, frame = backtest_competition(matches)
                    reasons = backtest_diagnostics(matches)
                    diagnostics.extend({"Competition": league, "Reason": reason, "Matches": count}
                                       for reason, count in reasons.items() if count)
                    frequency = historical_outcome_baseline(matches)
                    coverage.append({"Competition": league, "Finished": len(finished),
                                     "Evaluated": len(frame)})
                    if not frame.empty:
                        frame = frame.copy()
                        for column in ("Frequency baseline accuracy", "Frequency baseline Brier", "Frequency baseline log loss"):
                            frame[column] = frame["Match ID"].map(lambda mid: frequency.get(mid, {}).get(column, float("nan")))
                        frame["Competition"] = league
                        # Resolve names only from the returned match data.
                        names = backtest_clubs(matches)
                        frame["Home club"] = frame["Home team ID"].map(names)
                        frame["Away club"] = frame["Away team ID"].map(names)
                        frames.append(frame)
            progress.progress((i + 1) / len(choices))
        st.session_state["multi_model_report"] = {
            "data": pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(),
            "coverage": coverage, "diagnostics": diagnostics, "issues": issues,
            "period": f"{start.isoformat()} to {end.isoformat()}"}
    report = st.session_state.get("multi_model_report")
    if not report:
        st.info("Choose competitions and dates, then click Compare models.")
        return
    st.caption("Latest run: " + report["period"])
    for issue in report["issues"]:
        st.warning(issue)
    if report["coverage"]:
        st.subheader("Historical coverage")
        st.dataframe(pd.DataFrame(report["coverage"]), use_container_width=True, hide_index=True)
    st.subheader("Why were some matches skipped?")
    if report.get("diagnostics"):
        st.dataframe(pd.DataFrame(report["diagnostics"]), hide_index=True, use_container_width=True)
    st.caption("Diagnostics apply the current strict minimums: five earlier matches per team and three at the relevant venue. "
               "Matches at the same kickoff time are not used to train one another.")
    st.info("Historical training currently starts at the chosen From date. To improve coverage, "
            "choose an earlier start date where your API subscription permits it. "
            "The current live prediction and backtesting thresholds remain unchanged; "
            "we are not silently replacing missing team data with invented results.")
    df = report["data"]
    if df.empty:
        st.warning("No eligible completed matches. Try a longer period or different competitions.")
        return

    def summary(part):
        return {
            "Matches": len(part),
            "Original accuracy": part["Baseline Correct"].mean(),
            "Advanced accuracy": part["Correct"].mean(),
            "Original Brier": part["Baseline Brier"].mean(),
            "Advanced Brier": part["Brier"].mean(),
            "Original log loss": part["Baseline Log loss"].mean(),
            "Advanced log loss": part["Log loss"].mean(),
            "Frequency Brier": part["Frequency baseline Brier"].mean() if "Frequency baseline Brier" in part else float("nan"),
        }

    st.subheader("Overall model comparison")
    overall = summary(df)
    a, b, c = st.columns(3)
    a.metric("Evaluated matches", overall["Matches"])
    b.metric("Original mean Brier", f'{overall["Original Brier"]:.3f}')
    c.metric("Advanced mean Brier", f'{overall["Advanced Brier"]:.3f}')
    st.dataframe(pd.DataFrame([
        {"Model": "Original Poisson", "Accuracy": overall["Original accuracy"],
         "Mean Brier": overall["Original Brier"], "Mean log loss": overall["Original log loss"]},
        {"Model": "Advanced recency Poisson", "Accuracy": overall["Advanced accuracy"],
         "Mean Brier": overall["Advanced Brier"], "Mean log loss": overall["Advanced log loss"]},
    ]).style.format({"Accuracy": "{:.1%}", "Mean Brier": "{:.3f}", "Mean log loss": "{:.3f}"}),
        hide_index=True, use_container_width=True)
    st.caption("Lower Brier and log loss are better. Accuracy measures only the most likely 1X2 outcome.")
    if "Frequency baseline Brier" in df and df["Frequency baseline Brier"].notna().any():
        st.subheader("Simple historical-frequency benchmark")
        benchmark = df.dropna(subset=["Frequency baseline Brier"])
        st.dataframe(pd.DataFrame([{
            "Model": "Historical outcome frequencies (prior matches only)",
            "Accuracy": benchmark["Frequency baseline accuracy"].mean(),
            "Mean Brier": benchmark["Frequency baseline Brier"].mean(),
            "Mean log loss": benchmark["Frequency baseline log loss"].mean(),
        }]).style.format({"Accuracy": "{:.1%}", "Mean Brier": "{:.3f}",
                         "Mean log loss": "{:.3f}"}), hide_index=True, use_container_width=True)
        st.caption(f"Benchmark covers {len(benchmark)} evaluated fixtures. It estimates home/draw/away "
                   "frequencies from earlier matches in the same competition, with Laplace smoothing.")
    st.subheader("Sample-size reliability")
    for row in report.get("coverage", []):
        count = row["Evaluated"]
        if count < 30:
            st.warning(f"{row['Competition']}: only {count} evaluated matches. Too few for reliable conclusions.")
        elif count < 100:
            st.info(f"{row['Competition']}: {count} evaluated matches. Interpret differences cautiously.")

    st.subheader("By competition — separate comparisons")
    league_rows = [{"Competition": league, **summary(part)} for league, part in df.groupby("Competition")]
    st.dataframe(pd.DataFrame(league_rows).style.format({
        "Original accuracy": "{:.1%}", "Advanced accuracy": "{:.1%}",
        "Original Brier": "{:.3f}", "Advanced Brier": "{:.3f}",
        "Original log loss": "{:.3f}", "Advanced log loss": "{:.3f}", "Frequency Brier": "{:.3f}"}),
        hide_index=True, use_container_width=True)
    st.subheader("Individual club comparison")
    club_options = sorted(set(df["Home club"].dropna()) | set(df["Away club"].dropna()))
    selected_club = st.selectbox("Club", ["All clubs"] + club_options, key="comparison_club")
    if selected_club == "All clubs":
        club_rows = []
        for club in club_options:
            part = df[(df["Home club"] == club) | (df["Away club"] == club)]
            if len(part) >= 5:
                club_rows.append({"Club": club, **summary(part)})
        if club_rows:
            st.dataframe(pd.DataFrame(club_rows).sort_values("Matches", ascending=False).style.format({
                "Original accuracy": "{:.1%}", "Advanced accuracy": "{:.1%}",
                "Original Brier": "{:.3f}", "Advanced Brier": "{:.3f}",
                "Original log loss": "{:.3f}", "Advanced log loss": "{:.3f}"}),
                hide_index=True, use_container_width=True)
        st.caption("Club table shows teams with at least five evaluated matches; club results overlap and should not be added together.")
        plot_df = df
    else:
        plot_df = df[(df["Home club"] == selected_club) | (df["Away club"] == selected_club)]
        if not plot_df.empty:
            st.dataframe(pd.DataFrame([{"Club": selected_club, **summary(plot_df)}]),
                         hide_index=True, use_container_width=True)
    if not plot_df.empty:
        st.subheader("Cumulative probability error")
        ordered = plot_df.sort_values(["Date", "Competition", "Match"]).reset_index(drop=True)
        chart_data = pd.DataFrame({
            "Match number": range(1, len(ordered) + 1),
            "Original mean Brier": ordered["Baseline Brier"].expanding().mean().values,
            "Advanced mean Brier": ordered["Brier"].expanding().mean().values,
        })
        st.line_chart(chart_data.set_index("Match number"))
    if len(df) < 100:
        st.warning("Fewer than 100 eligible matches across the selected leagues. Differences may be unstable; test on a later untouched period before choosing a production model.")
    st.download_button("Download multi-league comparison CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="yanidollarz_model_comparison.csv", mime="text/csv")


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
    st.caption("Permanent history in Supabase, private to your signed-in account. Score checks run when requested.")
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
        st.caption("Results are fetched on demand; no background job is running.")
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


def _team_badge(team, fallback):
    """Display API-provided crest where available, without requiring extra assets."""
    crest = team.get('crest')
    if isinstance(crest, str) and crest.startswith('https://'):
        try:
            st.image(crest, width=66)
            return
        except Exception:
            pass
    st.markdown(f'### {fallback}')


def _probability_row(label, value, colour='#3b82f6'):
    """Accessible textual probability plus a Streamlit progress bar."""
    st.markdown(f'**{label}** · {value:.1%}')
    st.progress(min(1.0, max(0.0, float(value))))


def show_prediction(match, risk_only=False):
    """Professional match centre, preserving the existing prediction engine."""
    home_team = match.get('homeTeam') or {}
    away_team = match.get('awayTeam') or {}
    home = home_team.get('name') or 'Home'
    away = away_team.get('name') or 'Away'
    competition = (match.get('competition') or {}).get('name') or 'Football'
    st.title('🛡️ Match Risk Centre' if risk_only else '🎯 Match Prediction Centre')
    st.caption(f'{competition} · {local_kickoff(match.get("utcDate"))}')

    with st.container(border=True):
        home_col, middle_col, away_col = st.columns([4, 2, 4], vertical_alignment='center')
        with home_col:
            _team_badge(home_team, '🏠')
            st.markdown(f'### {home}')
            st.caption('HOME')
        with middle_col:
            st.markdown('## VS')
            st.caption((match.get('status') or 'UPCOMING').replace('_', ' ').title())
        with away_col:
            _team_badge(away_team, '✈️')
            st.markdown(f'### {away}')
            st.caption('AWAY')

    prediction, error = get_match_prediction(match)
    if error:
        st.warning(error)
        st.caption('Try another fixture with more completed historical matches.')
        return
    p = prediction
    st.info('Experimental independent-Poisson estimates based on historical results. Not calibrated, independently validated or guaranteed.')

    if not risk_only:
        save_col, analysis_col = st.columns([2, 2])
        with save_col:
            if st.button('💾 Save prediction to Supabase', key=f'pro_save_{match.get("id")}',
                         type='primary', use_container_width=True):
                saved, message = save_session_prediction(match, p)
                (st.success if saved else st.warning)(message)
        with analysis_col:
            st.button('🔎 View match analysis', key=f'pro_analyse_{match.get("id")}',
                      use_container_width=True, on_click=open_match_analysis, args=(match,))

    st.subheader('🏆 Match result probabilities')
    fav = max([('Home win', p['home_win']), ('Draw', p['draw']), ('Away win', p['away_win'])], key=lambda x: x[1])
    st.caption(f'Model favourite: {fav[0]} ({fav[1]:.1%}). This is the most likely single outcome, not a certainty.')
    win_cols = st.columns(3)
    for col, title, prob in zip(win_cols, [f'{home} win', 'Draw', f'{away} win'],
                                [p['home_win'], p['draw'], p['away_win']]):
        with col:
            with st.container(border=True):
                st.metric(title, f'{prob:.1%}')
                st.progress(float(prob))

    st.subheader('⚽ Expected goals')
    xg_home, xg_away, xg_total = st.columns(3)
    xg_home.metric(f'{home}', f"{p['home_xg']:.2f}")
    xg_away.metric(f'{away}', f"{p['away_xg']:.2f}")
    xg_total.metric('Combined expected goals', f"{p['home_xg'] + p['away_xg']:.2f}")
    st.caption('Expected goals here are Poisson scoring-rate estimates, not event-level xG statistics.')

    st.subheader('📊 Goals and BTTS markets')
    goals_cols = st.columns(3)
    for col, line in zip(goals_cols, [1.5, 2.5, 3.5]):
        with col:
            with st.container(border=True):
                st.metric(f'Over {line}', f"{p['overs'][line]:.1%}")
                st.caption(f"Under {line}: {1-p['overs'][line]:.1%}")
    btts_yes, btts_no = st.columns(2)
    btts_yes.metric('Both teams score · Yes', f"{p['btts']:.1%}")
    btts_no.metric('Both teams score · No', f"{1-p['btts']:.1%}")

    if not risk_only:
        st.subheader('🥅 Most likely scorelines')
        scores = p.get('scorelines', [])
        if scores:
            score_data = pd.DataFrame([{'Scoreline': f'{h}–{a}', 'Probability': round(float(prob)*100, 2)}
                                       for h, a, prob in scores])
            st.bar_chart(score_data.set_index('Scoreline'), y='Probability', horizontal=True,
                         x_label='Probability (%)', color='#3b82f6')
            st.caption('Only the five most probable exact scores are shown. Other scorelines remain possible.')

    st.subheader('🛡️ Risk and data quality')
    risk_col, samples_col = st.columns([1, 2])
    with risk_col:
        with st.container(border=True):
            st.markdown(f"**{p['risk']}**")
            st.caption('Heuristic uncertainty label, not a validated risk score.')
    with samples_col:
        with st.container(border=True):
            st.markdown('**Historical evidence**')
            st.write(f"{home}: {p['home_sample']} previous matches, including {p['home_venue_sample']} at home")
            st.write(f"{away}: {p['away_sample']} previous matches, including {p['away_venue_sample']} away")
    with st.expander('How this prediction is calculated'):
        st.write('Recency-weighted home/away attacking and defensive rates with smoothing, '
                 'followed by independent Poisson goal distributions. The model uses historical results '
                 'available before kickoff and does not use bookmaker odds, injuries or event-level xG.')
        st.write(f"League scoring reference: {p.get('league_reference', 'assumed venue rates')}")
        st.caption('Scoreline tail probabilities are grouped at 12+ goals. The model is experimental.')
    st.caption('Prediction history stores the model probabilities at save time. This page does not change existing saved snapshots.')


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
# STEP 14 — FOOTBALL MATCH CENTRE
# ==========================================

def show_match_centre():
    st.title("⚽ Football Match Centre")
    st.caption("Find clubs, browse fixtures and open match predictions or analysis · Times in SAST")

    today = datetime.now(SA_TIMEZONE).date()
    filter_col, search_col = st.columns([1, 2])
    with filter_col:
        competition = st.selectbox("Competition", list(COMPETITIONS), key="centre_competition")
    with search_col:
        club_search = st.text_input("Search for a club", placeholder="e.g. Arsenal, Chelsea, Barcelona", key="centre_search").strip().casefold()

    date_col1, date_col2, status_col = st.columns([1, 1, 1])
    with date_col1:
        start = st.date_input("From", value=today, key="centre_from")
    with date_col2:
        end = st.date_input("To", value=today + timedelta(days=14), key="centre_to")
    with status_col:
        match_filter = st.selectbox("Show matches", ["Upcoming", "All", "Finished", "Live"], key="centre_status")

    if end < start:
        st.warning("The end date must be on or after the start date.")
        return
    if (end - start).days > 30:
        st.warning("Choose a range of 30 days or less to protect the free API quota.")
        return
    if not FOOTBALL_API_KEY:
        st.warning("FOOTBALL_API_KEY is missing from Streamlit Secrets.")
        return

    matches, error = get_competition_fixtures(competition, start, end)
    if error:
        st.error(error)
        return

    def searchable_name(team):
        return " ".join(str(team.get(k) or "") for k in ("name", "shortName", "tla")).casefold()

    upcoming = {"SCHEDULED", "TIMED", "POSTPONED"}
    live = {"IN_PLAY", "PAUSED", "LIVE", "EXTRA_TIME", "PENALTY_SHOOTOUT"}
    filtered = []
    for match in matches:
        status = match.get("status") or ""
        if match_filter == "Upcoming" and status not in upcoming:
            continue
        if match_filter == "Finished" and status != "FINISHED":
            continue
        if match_filter == "Live" and status not in live:
            continue
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        if club_search and club_search not in searchable_name(home) and club_search not in searchable_name(away):
            continue
        filtered.append(match)
    filtered.sort(key=lambda m: m.get("utcDate") or "")

    metric1, metric2, metric3 = st.columns(3)
    with metric1:
        st.metric("Matches found", len(filtered))
    with metric2:
        st.metric("Upcoming", sum(m.get("status") in upcoming for m in filtered))
    with metric3:
        st.metric("Completed", sum(m.get("status") == "FINISHED" for m in filtered))

    if st.button("🔄 Refresh match centre", key="centre_refresh"):
        fetch_fixtures.clear()
        st.rerun()

    if not filtered:
        st.info("No matches match your filters. Try another club, date range or match status.")
        return

    st.caption(f"{competition} · {len(filtered)} matching fixtures · Data from football-data.org")
    for match in filtered:
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        home_name = home.get("shortName") or home.get("name") or "TBC"
        away_name = away.get("shortName") or away.get("name") or "TBC"
        status = match.get("status") or "UNKNOWN"
        final = (match.get("score") or {}).get("fullTime") or {}
        if final.get("home") is not None and final.get("away") is not None:
            score = f"{final['home']} – {final['away']}"
        else:
            score = "VS"
        match_id = match.get("id")
        with st.container(border=True):
            left, centre, right = st.columns([4, 1, 4], vertical_alignment="center")
            with left:
                badge = home.get("crest")
                if badge and badge.startswith("https://"):
                    st.image(badge, width=42)
                st.markdown(f"**{home_name}**")
                st.caption("HOME")
            with centre:
                st.markdown(f"### {score}")
            with right:
                badge = away.get("crest")
                if badge and badge.startswith("https://"):
                    st.image(badge, width=42)
                st.markdown(f"**{away_name}**")
                st.caption("AWAY")
            st.caption(f"{local_kickoff(match.get('utcDate'))} · {status.replace('_', ' ').title()}")
            buttons = st.columns(2)
            valid_teams = home.get("id") is not None and away.get("id") is not None
            with buttons[0]:
                st.button("🎯 Predict", key=f"centre_predict_{match_id}",
                          use_container_width=True,
                          disabled=not(valid_teams and status in upcoming),
                          on_click=open_match_prediction, args=(match,))
            with buttons[1]:
                st.button("🔎 Analyse", key=f"centre_analyse_{match_id}",
                          use_container_width=True, disabled=not valid_teams,
                          on_click=open_match_analysis, args=(match,))
    st.caption("Predictions are experimental and not guarantees. Match data availability depends on your API subscription.")

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
    </style>
    """, unsafe_allow_html=True)

    top_left, top_right = st.columns([5, 1])
    with top_left:
        st.caption("⚽ YANIDOLLARZ / FOOTBALL INTELLIGENCE")
    with top_right:
        if st.button("🚪 Logout", key="dashboard_logout", use_container_width=True):
            logout()

    tabs = ["Dashboard", "Match Centre", "Fixtures", "Match Analysis", "Predictions", "Risk Analysis", "History", "Backtesting", "Model Comparison"]
    selected = st.radio(
        "Dashboard navigation", tabs, horizontal=True,
        label_visibility="collapsed", key="dashboard_tab"
    )
    st.divider()

    if selected == "Dashboard":
        st.title(f"Welcome back, {username}! ⚽")
        st.caption("Your football insights at a glance")

        today = datetime.now(SA_TIMEZONE).date()
        default_league = "Premier League"
        today_matches, today_error = get_competition_fixtures(default_league, today, today)
        upcoming_matches, upcoming_error = get_competition_fixtures(
            default_league, today, today + timedelta(days=7)
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "📅 Today's Matches",
                str(len(today_matches)) if not today_error else "—",
                help="Premier League matches on today's SAST calendar date"
            )
        try:
            dashboard_history = load_prediction_history()
        except Exception:
            dashboard_history = []
            st.caption("Prediction history unavailable until the Supabase SQL setup is complete.")
        with col2:
            st.metric("🎯 Saved Predictions", str(len(dashboard_history)), help="Predictions saved permanently to Supabase")
        with col3:
            evaluated = [prediction_scores(r) for r in dashboard_history if r["status"] == "Finished"]
            evaluated = [x for x in evaluated if x]
            accuracy = (sum(x["correct"] for x in evaluated) / len(evaluated)) if evaluated else None
            st.metric("📊 Model Accuracy", f"{accuracy:.1%}" if accuracy is not None else "—", help="Highest-probability outcome accuracy on evaluated saved predictions only")

        st.write("")
        st.subheader("⚽ Upcoming Matches")
        st.caption("Premier League · Next 7 days · South African time")
        if upcoming_error:
            st.warning(upcoming_error)
        else:
            scheduled = [m for m in upcoming_matches if m.get("status") in
                         ("SCHEDULED", "TIMED", "POSTPONED")]
            scheduled.sort(key=lambda m: m.get("utcDate", ""))
            if scheduled:
                for match in scheduled[:6]:
                    show_fixture(match, allow_analysis=True)
            else:
                st.info("No upcoming Premier League fixtures in the next 7 days.")

        st.subheader("Prediction Markets")
        market_cols = st.columns(3)
        markets = [
            ("🏆 Match Winner", "Home / Draw / Away"),
            ("⚽ Total Goals", "Over / Under"),
            ("🚩 Corners", "Total and team corners"),
            ("🟨 Bookings", "Yellow and red cards"),
            ("🥅 Both Teams to Score", "Yes / No"),
            ("🛡️ Risk Assessment", "Probability and uncertainty"),
        ]
        for index, (heading, detail) in enumerate(markets):
            with market_cols[index % 3]:
                with st.container(border=True):
                    st.markdown(f"**{heading}**")
                    st.caption(detail)

    elif selected == "Match Centre":
        show_match_centre()

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

    elif selected == "Backtesting":
        show_backtesting()

    elif selected == "Model Comparison":
        show_model_comparison()


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