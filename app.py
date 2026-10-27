
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
    </style>
    """, unsafe_allow_html=True)

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
        with col2:
            st.metric("🎯 Predictions", "Available", help="Experimental Poisson model; select an upcoming fixture")
        with col3:
            st.metric("📊 Model Accuracy", "—", help="No predictions evaluated yet")

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
        st.title("📊 Prediction History")
        st.info("Your saved predictions and actual match outcomes will appear here.")


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