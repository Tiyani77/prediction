
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
import re
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

# Match Analysis styles must load on every page, not only the Predictions route.
st.markdown("""<style>
/* Step 24.4: polished analysis cards, responsive results and head-to-head. */
.ya-tab-kicker{font-size:11px;font-weight:800;letter-spacing:1.5px;color:#8fb6e5;margin:20px 0 8px}
.ya-form-panel,.ya-stats-panel{background:linear-gradient(145deg,#142840,#101d30);border:1px solid #2e4865;border-radius:17px;padding:18px;margin:8px 0 16px;min-width:0}
.ya-panel-head{display:flex;align-items:center;gap:12px;margin-bottom:18px;min-width:0}
.ya-panel-head img{object-fit:contain;flex-shrink:0}.ya-panel-head strong{display:block;color:#f4f8ff;font-size:17px;overflow-wrap:anywhere}.ya-panel-head small{display:block;color:#87a7c7;font-size:10px;letter-spacing:.08em;margin-top:4px}
.ya-form-chips{display:flex;gap:7px;margin-bottom:16px}.ya-form-chip{display:inline-flex;justify-content:center;align-items:center;min-width:27px;height:27px;border-radius:7px;font-weight:800;font-size:12px}
.ya-w{background:#124f42;color:#60e6b8}.ya-d{background:#56411b;color:#ffcf75}.ya-l{background:#552b3b;color:#ff8da5}
.ya-form-rows{border-top:1px solid #29425d}.ya-form-row{display:grid;grid-template-columns:86px minmax(0,1fr) 56px 28px;gap:8px;align-items:center;padding:11px 0;border-bottom:1px solid #253d55;color:#e9f1ff;font-size:13px}.ya-form-row .ya-form-date{color:#91abc5;font-size:11px}.ya-form-opponent{min-width:0;overflow-wrap:anywhere}.ya-form-opponent small{color:#88a8c7}.ya-form-row strong{white-space:nowrap;text-align:center}.ya-form-row .ya-form-chip{width:24px;min-width:24px;height:24px}.ya-empty{color:#a8bdd4;padding:12px 0}
.ya-stat-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ya-stat-tile,.ya-h2h-tile{background:#1a304a;border:1px solid #314d6b;border-radius:12px;padding:15px;min-width:0}.ya-stat-tile small,.ya-h2h-tile small{display:block;color:#a8c0da;font-size:12px;line-height:1.4;overflow-wrap:anywhere}.ya-stat-tile strong,.ya-h2h-tile strong{display:block;color:#f4f8ff;font-size:28px;line-height:1.35;margin-top:5px}.ya-accent-green{border-top:2px solid #3dd7b0}.ya-accent-red{border-top:2px solid #f38198}.ya-accent-blue{border-top:2px solid #55aaff}
.ya-h2h-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:15px 0 25px}.ya-h2h-tile strong{font-size:30px}
.ya-h2h-list{background:#13243a;border:1px solid #2b4561;border-radius:15px;padding:0 16px;margin:10px 0 22px}.ya-h2h-row{display:grid;grid-template-columns:minmax(0,1fr) 74px minmax(0,1fr);gap:10px;align-items:center;padding:15px 0;border-bottom:1px solid #2b415a}.ya-h2h-row:last-child{border-bottom:0}.ya-h2h-club{display:flex;gap:8px;align-items:center;min-width:0;color:#e9f1ff;font-size:13px}.ya-h2h-club span{overflow-wrap:anywhere}.ya-h2h-club img{flex-shrink:0;object-fit:contain}.ya-h2h-club.away{justify-content:flex-end;flex-direction:row-reverse;text-align:right}.ya-h2h-score{text-align:center;background:#203a57;border:1px solid #395978;border-radius:9px;padding:8px 3px;color:#fff;font-size:17px}.ya-h2h-row>small{grid-column:1/-1;color:#8ca9c7;font-size:11px;text-align:center;margin-top:-3px}
@media(max-width:700px){.ya-form-panel,.ya-stats-panel{padding:12px}.ya-panel-head strong{font-size:15px}.ya-form-row{grid-template-columns:68px minmax(0,1fr) 43px 24px;gap:5px;font-size:11px}.ya-form-row .ya-form-date{font-size:10px}.ya-stat-grid{gap:7px}.ya-stat-tile{padding:10px}.ya-stat-tile strong{font-size:23px}.ya-h2h-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.ya-h2h-tile{padding:11px}.ya-h2h-row{grid-template-columns:minmax(0,1fr) 58px minmax(0,1fr);gap:5px}.ya-h2h-club{font-size:11px;gap:4px}.ya-h2h-club img{width:20px!important;height:20px!important}.ya-h2h-score{font-size:14px}}


/* Cleaner match-centre result rows, similar to football score websites. */
.ya-form-row:nth-child(even){background:rgba(65,99,142,.10)}
.ya-form-row{padding:12px 9px;border-radius:7px}
.ya-form-row:hover,.ya-h2h-row:hover{background:rgba(73,123,181,.13)}
.ya-h2h-row{grid-template-columns:100px minmax(0,1fr) 72px minmax(0,1fr);border-radius:8px;padding:12px 9px}
.ya-h2h-row>small{grid-column:1;grid-row:1;text-align:left;margin:0;font-size:11px}
.ya-h2h-row>.ya-h2h-club:first-child{grid-column:2;grid-row:1}
.ya-h2h-row>.ya-h2h-score{grid-column:3;grid-row:1}
.ya-h2h-row>.ya-h2h-club.away{grid-column:4;grid-row:1}
.ya-h2h-row:nth-child(even){background:rgba(65,99,142,.10)}
.ya-h2h-list{padding:5px 12px}
.ya-form-panel,.ya-stats-panel{box-shadow:0 9px 24px rgba(0,0,0,.10)}
@media(max-width:700px){.ya-h2h-row{grid-template-columns:62px minmax(0,1fr) 47px minmax(0,1fr);gap:4px;padding:11px 2px}.ya-h2h-row>small{font-size:9px}.ya-h2h-score{padding:6px 1px}.ya-h2h-list{padding:3px 7px}}

</style>""", unsafe_allow_html=True)

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


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_standings(competition_code, _api_key):
    """Fetch the current season table; respect API permissions and quota."""
    request = Request(
        f"{FOOTBALL_API_BASE}/competitions/{competition_code}/standings",
        headers={"X-Auth-Token": _api_key, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=18) as response:
            data = json.load(response)
        tables = data.get("standings") or []
        # League competitions typically provide TOTAL, HOME and AWAY tables.
        total = next((t for t in tables if t.get("type") == "TOTAL"), None)
        if total is None:
            total = next((t for t in tables if t.get("table")), None)
        if total is None:
            return data, [], "No league table is available for this competition."
        return data, total.get("table") or [], None
    except HTTPError as exc:
        messages = {
            401: "Football API token rejected. Check FOOTBALL_API_KEY.",
            403: "Standings for this competition are not included in your football-data.org plan.",
            404: "No standings endpoint is available for this competition.",
            429: "Football API rate limit reached. Try again shortly.",
        }
        return {}, [], messages.get(exc.code, f"Football API returned HTTP {exc.code}.")
    except (URLError, TimeoutError, OSError, ValueError):
        return {}, [], "Couldn't load standings. Please try again later."


def render_league_standings():
    st.title("🏆 League Standings")
    st.caption("Current tables from football-data.org · Updated when the provider publishes new data")
    league = st.selectbox("Competition", list(COMPETITIONS), key="standings_league")
    if not FOOTBALL_API_KEY:
        st.error("FOOTBALL_API_KEY is missing from Streamlit Secrets.")
        return
    data, table, error = fetch_standings(COMPETITIONS[league], FOOTBALL_API_KEY)
    if error:
        st.info(error)
        return
    season = data.get("season") or {}
    st.caption(f"{league} · Season {str(season.get('startDate') or '')[:4]} · {len(table)} clubs")
    # A single semantic table avoids Streamlit's white number badges and
    # keeps every column aligned, including when club names wrap.
    table_rows = []
    for entry in table:
        team = entry.get("team") or {}
        name = html.escape(str(team.get("shortName") or team.get("name") or "Unknown"))
        crest = crest_markup(team, 30)
        pos = entry.get("position", "—")
        try:
            pos_int = int(pos)
        except (TypeError, ValueError):
            pos_int = 99
        zone = "top" if pos_int <= 4 else ("bottom" if pos_int >= max(1, len(table)-2) else "mid")
        stats = []
        for field in ("playedGames", "won", "draw", "lost", "goalsFor", "goalDifference", "points"):
            value = entry.get(field)
            stats.append(html.escape(str(value if value is not None else "—")))
        table_rows.append(
            f'<tr class="yani-rank-{zone}"><td class="yani-pos">{html.escape(str(pos))}</td>'
            f'<td><div class="yani-table-team">{crest}<span>{name}</span></div></td>'
            + ''.join(f'<td class="yani-stat">{v}</td>' for v in stats[:-1])
            + f'<td class="yani-points">{stats[-1]}</td></tr>'
        )
    st.markdown(
        '<div class="yani-table-scroll"><table class="yani-standings">'
        '<thead><tr><th>#</th><th>Club</th><th>P</th><th>W</th><th>D</th>'
        '<th>L</th><th>GF</th><th>GD</th><th>Pts</th></tr></thead><tbody>'
        + ''.join(table_rows) + '</tbody></table></div>'
        '<div class="yani-table-legend"><span>● Top four</span><span>● Bottom three</span>'
        '<span>P played · GF goals for · GD goal difference</span></div>',
        unsafe_allow_html=True,
    )
    st.divider()
    st.subheader("🔎 Club statistics")
    choices = {f"{(r.get('team') or {}).get('name', 'Unknown')}": r for r in table}
    selected_team = st.selectbox("Choose a club", list(choices), key="standings_club")
    row = choices[selected_team]
    metrics = st.columns(4)
    for col, title, field in zip(metrics, ["Position", "Points", "Goal difference", "Matches played"], ["position", "points", "goalDifference", "playedGames"]):
        col.metric(title, row.get(field, "—"))
    st.divider()
    st.subheader("📈 Recent club form & comparison")
    st.caption("Compare completed matches using football-data.org results. Form is historical, not a prediction.")
    team_names = list(choices)
    opponent_options = [name for name in team_names if name != selected_team]
    opponent = st.selectbox("Compare against", opponent_options, key=f"form_opponent_{COMPETITIONS[league]}")
    sample = st.slider("Recent completed matches", min_value=5, max_value=20, value=10, step=5, key="club_form_sample")
    left, right = st.columns(2)
    for panel, club_name in ((left, selected_team), (right, opponent)):
        club_row = choices[club_name]
        club = club_row.get("team") or {}
        club_id = club.get("id")
        with panel:
            st.markdown(f"#### {club_name}")
            if club.get("crest") and str(club["crest"]).startswith("https://"):
                st.image(club["crest"], width=55)
            if not club_id:
                st.info("No team ID available for recent form.")
                continue
            # Use a UTC cutoff after today so only completed fixtures are counted.
            history, history_error = get_team_history(club_id, datetime.now(timezone.utc).isoformat(), limit=sample)
            if history_error:
                st.info(history_error)
                continue
            history = history[:sample]
            stats = team_statistics(history, club_id)
            if stats:
                render_stat_block(stats, f"Last {stats['played']} matches")
            else:
                st.info("No completed matches available for this club.")
            render_form(history, club_id, "Recent form")
    st.caption("Match availability varies by competition and API plan. No simulated results are used.")
    st.caption("Standings reflect the provider's published results; they are not prediction-model estimates.")
    if st.button("🔄 Refresh league table", key="refresh_standings"):
        fetch_standings.clear()
        st.rerun()


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


@st.cache_data(ttl=75, show_spinner=False)
def fetch_match_centre(competition_code, date_from, date_to, _api_key):
    """Short-cache feed for Match Centre; only polls when that page is open."""
    return _fetch_match_centre_direct(competition_code, date_from, date_to, _api_key)


def _fetch_match_centre_direct(competition_code, date_from, date_to, api_key):
    url = (f"{FOOTBALL_API_BASE}/competitions/{competition_code}/matches?"
           + urlencode({"dateFrom": date_from, "dateTo": date_to}))
    try:
        with urlopen(Request(url, headers={"X-Auth-Token": api_key}), timeout=18) as response:
            return json.load(response).get("matches", []), None
    except HTTPError as exc:
        return [], {401: "Football API key rejected.", 403: "This league isn't included in your football API plan.",
                    429: "Football API rate limit reached. Try again shortly."}.get(exc.code, f"Football API HTTP {exc.code}.")
    except (URLError, TimeoutError, ValueError, OSError):
        return [], "Football data is temporarily unavailable."


def centre_score(match):
    status = str(match.get("status") or "UNKNOWN").upper()
    full = (match.get("score") or {}).get("fullTime") or {}
    live = (match.get("score") or {}).get("regularTime") or {}
    home = full.get("home") if full.get("home") is not None else live.get("home")
    away = full.get("away") if full.get("away") is not None else live.get("away")
    score = f"{home} – {away}" if home is not None and away is not None else "vs"
    label = {"IN_PLAY": "🔴 Live", "PAUSED": "🟠 Half-time", "FINISHED": "✅ Full-time",
             "TIMED": "🗓️ Upcoming", "SCHEDULED": "🗓️ Upcoming", "POSTPONED": "⚠️ Postponed",
             "CANCELLED": "⚠️ Cancelled"}.get(status, status.replace("_", " ").title())
    return score, label


def centre_open_prediction(match):
    """Navigate from a refreshing fragment to the full Predictions page."""
    open_match_prediction(match)
    st.rerun(scope="app")


def centre_open_analysis(match):
    """Navigate from a refreshing fragment to the full Match Analysis page."""
    open_match_analysis(match)
    st.rerun(scope="app")


def render_match_centre():
    st.title("🔴 Live Match Centre")
    st.caption("Scores from football-data.org · Times in SAST · Live updates depend on your API subscription")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        league = st.selectbox("Competition", list(COMPETITIONS), key="centre_league")
    with col2:
        day = st.date_input("Match date", value=datetime.now(SA_TIMEZONE).date(), key="centre_day")
    with col3:
        filter_status = st.selectbox("Show", ["All", "Live", "Upcoming", "Finished"], key="centre_status")
    search = st.text_input("Find a club", placeholder="Search Chelsea, Man United...", key="centre_search").strip().casefold()
    if not FOOTBALL_API_KEY:
        st.warning("Add FOOTBALL_API_KEY to Streamlit Secrets to load matches.")
        return

    if st.button("🔄 Refresh scores now", key="centre_manual_refresh"):
        fetch_match_centre.clear()
        st.rerun()

    # This fragment refreshes only the feed, not the whole app or its navigation.
    def centre_feed():
        matches, error = _fetch_centre_feed(league, day.isoformat(), FOOTBALL_API_KEY)
        if error:
            st.warning(error)
            return
        def accepted(m):
            status = str(m.get("status") or "").upper()
            if filter_status == "Live" and status not in ("IN_PLAY", "PAUSED"):
                return False
            if filter_status == "Upcoming" and status not in ("TIMED", "SCHEDULED"):
                return False
            if filter_status == "Finished" and status != "FINISHED":
                return False
            names = " ".join(str((m.get(k) or {}).get("name") or "") for k in ("homeTeam", "awayTeam"))
            return not search or search in names.casefold()
        filtered = sorted((m for m in matches if accepted(m)), key=lambda m: m.get("utcDate", ""))
        st.caption(f"{len(filtered)} matches · Last checked {datetime.now(SA_TIMEZONE).strftime('%H:%M:%S')} SAST · Refreshes approximately every 90 seconds while open")
        if not filtered:
            st.info("No matches match these filters. Try another date, league or status.")
        for m in filtered:
            score, label = centre_score(m)
            with st.container(border=True):
                left, right = st.columns([4, 1], vertical_alignment="center")
                with left:
                    render_fixture_teams(m)
                    st.markdown(f"**{score}** · {label}")
                    st.caption(local_kickoff(m.get("utcDate")))
                with right:
                    if (m.get("homeTeam") or {}).get("id") and (m.get("awayTeam") or {}).get("id"):
                        st.button("🔎 Analyse", key=f"centre_an_{m.get('id')}", use_container_width=True,
                                  on_click=centre_open_analysis, args=(m,))
                        if m.get("status") in ("TIMED", "SCHEDULED"):
                            st.button("🎯 Predict", key=f"centre_pr_{m.get('id')}", use_container_width=True,
                                      on_click=centre_open_prediction, args=(m,))
    if hasattr(st, "fragment"):
        st.fragment(run_every="90s")(centre_feed)()
    else:
        centre_feed()


@st.cache_data(ttl=75, show_spinner=False)
def _fetch_centre_feed(league, day, _api_key):
    return _fetch_match_centre_direct(COMPETITIONS[league], day, day, _api_key)


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


def team_crest_url(team):
    """Use a real football-data.org crest, never a guessed club identifier."""
    team = team or {}
    crest = team.get("crest")
    if crest and str(crest).startswith("https://"):
        return str(crest)
    if team.get("id"):
        return f'https://crests.football-data.org/{int(team["id"])}.png'
    return None


def crest_markup(team, size=40):
    url = team_crest_url(team)
    if not url:
        return '<span class="yani-crest-fallback">⚽</span>'
    return (f'<img class="yani-crest-img" src="{html.escape(url, quote=True)}" '
            f'alt="Club crest" loading="lazy" style="width:{size}px;height:{size}px">')


def render_fixture_teams(match, compact=False):
    home, away = match.get("homeTeam") or {}, match.get("awayTeam") or {}
    def label(team):
        return html.escape(str(team.get("shortName") or team.get("name") or "TBC"))
    score = (match.get("score") or {}).get("fullTime") or {}
    if score.get("home") is not None and score.get("away") is not None:
        middle = f'{int(score["home"])} – {int(score["away"])}'
    else:
        middle = 'VS'
    style = 'yani-fixture-teams compact' if compact else 'yani-fixture-teams'
    st.markdown(f'<div class="{style}"><div class="yani-fixture-club">{crest_markup(home)}<strong>{label(home)}</strong></div>'
                f'<div class="yani-fixture-vs">{middle}</div>'
                f'<div class="yani-fixture-club">{crest_markup(away)}<strong>{label(away)}</strong></div></div>',
                unsafe_allow_html=True)


def show_team_crest(team, size=48):
    """Show the actual team crest from the football-data.org match payload."""
    crest = (team or {}).get("crest")
    if not crest and (team or {}).get("id"):
        crest = f'https://crests.football-data.org/{int(team["id"])}.png'
    if crest and str(crest).startswith("https://"):
        st.image(crest, width=size)
    else:
        st.markdown("⚽")


def analysis_form_panel(matches, team_id, team):
    """Compact, styled result list with actual scores and form chips."""
    recent = [team_result(m, team_id) for m in matches[:5]]
    recent = [r for r in recent if r]
    name = html.escape(str(team.get("shortName") or team.get("name") or "Club"))
    chips = "".join(f'<span class="ya-form-chip ya-{r["outcome"].lower()}">{r["outcome"]}</span>' for r in recent)
    rows = []
    for r in recent:
        m = r["match"]
        opponent = (m.get("awayTeam") if (m.get("homeTeam") or {}).get("id") == team_id else m.get("homeTeam")) or {}
        opponent_name = html.escape(str(opponent.get("shortName") or opponent.get("name") or "Opponent"))
        date_label = html.escape(str(m.get("utcDate") or "")[:10])
        venue = "H" if r["venue"] == "Home" else "A"
        rows.append(f'<div class="ya-form-row"><span class="ya-form-date">{date_label}</span><span class="ya-form-opponent">{opponent_name} <small>({venue})</small></span><strong>{r["gf"]} – {r["ga"]}</strong><span class="ya-form-chip ya-{r["outcome"].lower()}">{r["outcome"]}</span></div>')
    if not recent:
        rows = ['<div class="ya-empty">No completed matches available.</div>']
    st.markdown(f'<section class="ya-form-panel"><div class="ya-panel-head">{crest_markup(team, 40)}<div><strong>{name}</strong><small>LAST {len(recent)} MATCHES · MOST RECENT FIRST</small></div></div><div class="ya-form-chips">{chips}</div><div class="ya-form-rows">{"".join(rows)}</div></section>', unsafe_allow_html=True)


def analysis_stat_panel(stats, team, subtitle=""):
    """Compact stats with consistent typography and meaningful colour accents."""
    name = html.escape(str(team.get("shortName") or team.get("name") or "Club"))
    if not stats:
        st.info(f"No completed match statistics available for {name}.")
        return
    cards = [
        ("Wins", stats["wins"], "green"), ("Draws", stats["draws"], "blue"),
        ("Losses", stats["losses"], "red"), ("Win rate", f'{stats["win_rate"]:.0f}%', "green"),
        ("Goals scored", stats["goals_for"], "blue"), ("Goals conceded", stats["goals_against"], "red"),
        ("Goals / match", f'{stats["avg_goals"]:.2f}', "blue"), ("Clean sheets", stats["clean_sheets"], "green")]
    tiles = "".join(f'<div class="ya-stat-tile ya-accent-{color}"><small>{label}</small><strong>{value}</strong></div>' for label,value,color in cards)
    st.markdown(f'<section class="ya-stats-panel"><div class="ya-panel-head">{crest_markup(team, 40)}<div><strong>{name}</strong><small>{html.escape(subtitle)} · {stats["played"]} COMPLETED MATCHES</small></div></div><div class="ya-stat-grid">{tiles}</div></section>', unsafe_allow_html=True)


# Step 25.1: free, attributed football RSS headlines (no API key needed).
# RSS is news reporting, NOT a verified injury database or a bookmaker feed.
YANIDOLLARZ_NEWS_FEEDS = (
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
    ("BBC Premier League", "https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml"),
    ("Sky Sports", "https://www.skysports.com/rss/11095"),
    ("The Guardian", "https://www.theguardian.com/football/rss"),
)


@st.cache_data(ttl=1800, show_spinner=False)
def get_free_football_news():
    """Read public RSS metadata only; tolerate unavailable feeds independently."""
    articles, errors = [], []
    for publisher, url in YANIDOLLARZ_NEWS_FEEDS:
        try:
            request = Request(url, headers={"User-Agent": "YANIDOLLARZ/1.0 (football-news-reader)", "Accept": "application/rss+xml, application/xml, text/xml"})
            with urlopen(request, timeout=6) as response:
                raw = response.read(500_000)
            root = ET.fromstring(raw)
            items = root.findall(".//item")
            for item in items[:45]:
                def value(tag):
                    node = item.find(tag)
                    return "" if node is None else " ".join((node.text or "").split())
                title, link = value("title"), value("link")
                if not title or not link.startswith("https://"):
                    continue
                articles.append({"publisher": publisher, "title": title, "link": link,
                                 "summary": " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value("description"))).split())[:650],
                                 "published": value("pubDate")})
        except Exception as exc:
            errors.append(publisher)
    unique = {}
    for article in articles:
        unique.setdefault(article["link"], article)
    return list(unique.values()), errors


def _news_team_terms(team):
    name = (team or "").strip().lower()
    variants = {name}
    aliases = {
        "manchester united": {"man utd", "man united", "manchester united"},
        "manchester city": {"man city", "manchester city"},
        "tottenham hotspur": {"tottenham", "spurs"},
        "wolverhampton wanderers": {"wolves", "wolverhampton"},
        "newcastle united": {"newcastle", "newcastle united"},
        "nottingham forest": {"nottingham forest", "nott'm forest"},
        "brighton & hove albion": {"brighton", "brighton and hove albion"},
        "internazionale": {"inter milan", "inter"},
        "paris saint-germain": {"psg", "paris saint-germain"},
        "bayern munich": {"bayern", "bayern munich"},
    }
    for key, vals in aliases.items():
        if key in name or name in vals:
            variants.update(vals)
    # Strip FC/CF only; never use generic terms such as 'United' or 'City'.
    simple = re.sub(r"\b(fc|cf|afc|sc)\b", "", name).strip()
    if len(simple) >= 5:
        variants.add(simple)
    return {v for v in variants if len(v) >= 4}


def show_free_match_news(home_name, away_name):
    st.markdown("#### 📰 Football news & team intelligence")
    st.caption("Read available publisher summaries right here. Full articles remain on the publisher’s website; injury claims are not automatically verified.")
    articles, errors = get_free_football_news()
    if not articles:
        st.info("News feeds are temporarily unavailable. Try again later; your match predictions still work normally.")
        return
    terms_home, terms_away = _news_team_terms(home_name), _news_team_terms(away_name)
    def contains(text, terms):
        return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) for term in terms)
    relevant = []
    for article in articles:
        content = (article["title"] + " " + article["summary"]).lower()
        is_home, is_away = contains(content, terms_home), contains(content, terms_away)
        if is_home or is_away:
            relevant.append((article, is_home, is_away))
    filter_choice = st.radio("News for", ["Both teams", home_name, away_name], horizontal=True, key="yani_news_team_filter")
    if filter_choice == home_name:
        relevant = [row for row in relevant if row[1]]
    elif filter_choice == away_name:
        relevant = [row for row in relevant if row[2]]
    if not relevant:
        st.info("No recent headlines mentioning these clubs in the free feeds right now. This does not mean there are no injuries or team updates.")
    for article, is_home, is_away in relevant[:12]:
        tags = []
        text = (article["title"] + " " + article["summary"]).lower()
        if re.search(r"\b(injur(?:y|ies|ed)|sidelined|hamstring|ankle|knee|fitness|suspension|suspended|doubtful)\b", text):
            tags.append("⚕️ Possible availability news — verify in article")
        if re.search(r"\b(derby|rivalry|rivals)\b", text):
            tags.append("🔥 Rivalry / derby context")
        if re.search(r"\b(predict|prediction|pundit|backed|favourit|favorite|expect|tip)\b", text):
            tags.append("💬 Opinion / preview — read original")
        with st.container(border=True):
            st.markdown(f"**{article['title']}**")
            st.caption(f"{article['publisher']} · {article['published'] or 'Date unavailable'}")
            if tags:
                st.caption(" · ".join(tags))
            with st.expander("📖 Read summary in YANIDOLLARZ", expanded=False):
                excerpt = (article.get("summary") or "").strip()
                if excerpt and excerpt.casefold().rstrip(" .") != article["title"].casefold().rstrip(" ."):
                    st.markdown("**Publisher's RSS summary**")
                    st.write(excerpt)
                else:
                    st.info("This publisher did not provide an article summary in its free news feed. The headline is available, but the full report cannot be reproduced here.")
                signals = []
                if re.search(r"\b(injur(?:y|ies|ed)|sidelined|hamstring|ankle|knee|fitness|suspension|suspended|doubtful)\b", text):
                    signals.append("Availability-related wording appears in this headline or summary. Check the original report and club announcements before treating a player as unavailable.")
                if re.search(r"\b(derby|rivalry|rivals)\b", text):
                    signals.append("Rivalry or derby context is mentioned. This alone does not establish a statistical effect on the match.")
                if re.search(r"\b(predict|prediction|pundit|backed|favourit|favorite|expect|tip)\b", text):
                    signals.append("Prediction or opinion language appears. This is commentary, not a verified result or model input.")
                if signals:
                    st.markdown("**Why it may matter**")
                    for signal in signals:
                        st.write("• " + signal)
                else:
                    st.caption("No specific injury, derby or expert-prediction signal was identified in the available feed text. This story is shown because it mentions a selected team.")
                st.caption("Summary supplied by the publisher's public RSS feed; it may omit important context.")
            st.link_button("↗ Full article at " + article["publisher"] + " (optional)", article["link"], use_container_width=False)
    st.divider()
    st.markdown("**What this means for the prediction**")
    st.info("The existing Poisson prediction is unchanged. These headlines provide context only. A report, rumour or pundit opinion must not be treated as a confirmed absence or automatically change probabilities.")
    if errors:
        st.caption("Some feeds could not be reached: " + ", ".join(errors) + ". Available sources are still shown.")


def show_match_analysis(match):
    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}
    home_id, away_id = home_team.get("id"), away_team.get("id")
    home_name = home_team.get("name") or "Home team"
    away_name = away_team.get("name") or "Away team"
    kickoff = match.get("utcDate") or datetime.now(timezone.utc).isoformat()
    st.title("🔎 Match Analysis")
    st.caption("Historical football statistics · Real completed matches · No predicted outcomes")
    kickoff_label = html.escape(local_kickoff(match.get("utcDate")))
    status_label = html.escape(str(match.get("status") or "Scheduled").replace("_", " ").title())
    st.markdown(f'<div class="yani-pred-hero"><div class="yani-pred-kicker">MATCH ANALYSIS · {kickoff_label} · {status_label}</div><div class="yani-pred-fixture"><div class="yani-pred-club">{crest_markup(home_team, 62)}<strong>{html.escape(home_name)}</strong><small>HOME</small></div><div class="yani-pred-vs">VS</div><div class="yani-pred-club">{crest_markup(away_team, 62)}<strong>{html.escape(away_name)}</strong><small>AWAY</small></div></div></div>', unsafe_allow_html=True)

    with st.spinner("Loading match history..."):
        home_matches, home_error = get_team_history(home_id, kickoff)
        away_matches, away_error = get_team_history(away_id, kickoff)
        h2h_matches, h2h_error = get_head_to_head(match.get("id"), kickoff)

    st.markdown('<div class="ya-tab-kicker">EXPLORE MATCH ANALYSIS</div>', unsafe_allow_html=True)
    tabs = st.tabs(["📈 Recent Form", "📊 Team Stats", "🏟️ Home / Away", "🤝 Head-to-Head", "📰 News & Injuries"])
    with tabs[0]:
        st.markdown("#### 📈 Recent form")
        st.caption("Latest five completed matches · Scores are shown from each club’s perspective")
        left, right = st.columns(2)
        with left:
            if home_error: st.warning(f"{home_name}: {home_error}")
            else: analysis_form_panel(home_matches, home_id, home_team)
        with right:
            if away_error: st.warning(f"{away_name}: {away_error}")
            else: analysis_form_panel(away_matches, away_id, away_team)
    with tabs[1]:
        st.markdown("#### 📊 Team statistics")
        st.caption("Historical completed matches before kickoff · Sample sizes may differ")
        left, right = st.columns(2)
        with left: analysis_stat_panel(team_statistics(home_matches, home_id), home_team, "ALL VENUES")
        with right: analysis_stat_panel(team_statistics(away_matches, away_id), away_team, "ALL VENUES")
    with tabs[2]:
        st.markdown("#### 🏟️ Home vs away performance")
        st.caption("Home club’s home results compared with away club’s away results")
        left, right = st.columns(2)
        with left: analysis_stat_panel(team_statistics(home_matches, home_id, "Home"), home_team, "HOME MATCHES")
        with right: analysis_stat_panel(team_statistics(away_matches, away_id, "Away"), away_team, "AWAY MATCHES")
    with tabs[3]:
        st.markdown("#### 🤝 Head-to-head")
        if h2h_error:
            st.warning(h2h_error)
        elif not h2h_matches:
            st.info("No previous completed head-to-head meetings available for this fixture.")
        else:
            hw = aw = draws = hg = ag = 0
            valid = []
            for previous in h2h_matches:
                ph = (previous.get("homeTeam") or {}).get("id")
                pa = (previous.get("awayTeam") or {}).get("id")
                sc = (previous.get("score") or {}).get("fullTime") or {}
                sh, sa = sc.get("home"), sc.get("away")
                if sh is None or sa is None: continue
                if ph == home_id and pa == away_id: x,y = int(sh),int(sa)
                elif ph == away_id and pa == home_id: x,y = int(sa),int(sh)
                else: continue
                hg += x; ag += y
                if x > y: hw += 1
                elif x < y: aw += 1
                else: draws += 1
                valid.append(previous)
            st.caption(f"{len(valid)} completed meetings · Historical results only")
            items = [(f"{home_name} wins", hw, "green"),("Draws", draws, "blue"),(f"{away_name} wins", aw, "red"),(f"{home_name} goals", hg, "blue"),(f"{away_name} goals", ag, "blue")]
            tiles = "".join(f'<div class="ya-h2h-tile ya-accent-{color}"><small>{html.escape(label)}</small><strong>{value}</strong></div>' for label,value,color in items)
            st.markdown(f'<div class="ya-h2h-grid">{tiles}</div>', unsafe_allow_html=True)
            st.markdown("##### Previous meetings")
            rows = []
            for previous in valid:
                hteam = previous.get("homeTeam") or {}
                ateam = previous.get("awayTeam") or {}
                score = (previous.get("score") or {}).get("fullTime") or {}
                dt = html.escape(local_kickoff(previous.get("utcDate")))
                hn = html.escape(str(hteam.get("shortName") or hteam.get("name") or "Home"))
                an = html.escape(str(ateam.get("shortName") or ateam.get("name") or "Away"))
                rows.append(f'<div class="ya-h2h-row"><small>{dt}</small><div class="ya-h2h-club">{crest_markup(hteam, 26)}<span>{hn}</span></div><strong class="ya-h2h-score">{score["home"]} – {score["away"]}</strong><div class="ya-h2h-club away">{crest_markup(ateam, 26)}<span>{an}</span></div></div>')
            st.markdown(f'<div class="ya-h2h-list">{"".join(rows)}</div>', unsafe_allow_html=True)
    st.caption("Historical performance does not guarantee future results. Available matches depend on your football-data.org plan.")
    if match.get("status") in ("SCHEDULED", "TIMED"):
        st.button("🎯 Predict this match →", key="analysis_predict", on_click=open_match_prediction, args=(match,))


# ==========================================
# POISSON GOALS MODEL — HISTORICAL RESULTS ONLY
# ==========================================


    with tabs[4]:
        show_free_match_news(home_name, away_name)


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


def performance_competition_names(graded):
    """Resolve league names on demand; cached API responses limit requests."""
    result = {}
    if not FOOTBALL_API_KEY:
        return result, "Football API key unavailable."
    for record, _ in graded[:25]:
        mid = record.get("match_id")
        if not mid:
            continue
        payload, error = fetch_analysis_json(f"/matches/{int(mid)}", FOOTBALL_API_KEY)
        if error:
            return result, error
        match = payload.get("match", payload) if isinstance(payload, dict) else {}
        comp = (match.get("competition") or {}).get("name")
        if comp:
            result[str(mid)] = comp
    return result, None


def show_bet_tip_accuracy(graded):
    """Evaluate frozen pre-kickoff probabilities against completed match results.

    This is retrospective validation, not a recalibration of the Poisson model.
    Markets are assessed independently; rows from the same match are correlated.
    """
    st.markdown("### 🎯 Bet Tip Accuracy Lab")
    st.caption("Checks predictions saved before kickoff against final scores. No bookmaker odds or invented historical matches.")
    if not graded:
        st.info("No finished saved predictions yet. Accuracy testing begins after full-time results are recorded.")
        return

    market_defs = [
        ("Home win", lambda r: float(r["home_win"]), lambda h,a: h > a),
        ("Draw", lambda r: float(r["draw"]), lambda h,a: h == a),
        ("Away win", lambda r: float(r["away_win"]), lambda h,a: h < a),
        ("Home or Draw (1X)", lambda r: float(r["home_win"]) + float(r["draw"]), lambda h,a: h >= a),
        ("Away or Draw (X2)", lambda r: float(r["away_win"]) + float(r["draw"]), lambda h,a: h <= a),
        ("Either team wins (12)", lambda r: float(r["home_win"]) + float(r["away_win"]), lambda h,a: h != a),
        ("Over 1.5 goals", lambda r: float(r["over_1_5"]), lambda h,a: h+a >= 2),
        ("Under 1.5 goals", lambda r: 1-float(r["over_1_5"]), lambda h,a: h+a < 2),
        ("Over 2.5 goals", lambda r: float(r["over_2_5"]), lambda h,a: h+a >= 3),
        ("Under 2.5 goals", lambda r: 1-float(r["over_2_5"]), lambda h,a: h+a < 3),
        ("Over 3.5 goals", lambda r: float(r["over_3_5"]), lambda h,a: h+a >= 4),
        ("Under 3.5 goals", lambda r: 1-float(r["over_3_5"]), lambda h,a: h+a < 4),
        ("BTTS Yes", lambda r: float(r["btts"]), lambda h,a: h > 0 and a > 0),
        ("BTTS No", lambda r: 1-float(r["btts"]), lambda h,a: h == 0 or a == 0),
    ]
    observations = []
    for record, _ in graded:
        try:
            h, a = int(record["score_home"]), int(record["score_away"])
            for name, get_probability, get_actual in market_defs:
                probability = get_probability(record)
                if not math.isfinite(probability) or not 0 <= probability <= 1:
                    continue
                actual = int(get_actual(h,a))
                observations.append({"Market": name, "Probability": probability,
                                     "Actual": actual, "Brier": (probability - actual)**2})
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
    if not observations:
        st.info("Finished records do not yet have enough valid stored probabilities to evaluate.")
        return
    frame = pd.DataFrame(observations)
    num_matches = len(graded)
    a,b,c = st.columns(3)
    a.metric("Finished saved matches", num_matches)
    b.metric("Markets evaluated", frame["Market"].nunique())
    c.metric("Calibration readiness", "Early data" if num_matches < 30 else "Review results")
    if num_matches < 30:
        st.warning(f"Only {num_matches} completed match(es). Aim for at least 30 independent finished fixtures before drawing even preliminary conclusions; substantially more are needed for reliable calibration.")

    selected = st.selectbox("Evaluate market", [name for name,_,_ in market_defs], key="yani_accuracy_market")
    sample = frame[frame["Market"] == selected].copy()
    n = len(sample)
    observed = float(sample["Actual"].mean())
    predicted = float(sample["Probability"].mean())
    brier = float(sample["Brier"].mean())
    a,b,c = st.columns(3)
    a.metric("Average predicted", f"{predicted:.1%}")
    b.metric("Actual occurrence", f"{observed:.1%}")
    c.metric("Brier score · lower better", f"{brier:.3f}")
    st.caption(f"Based on {n} finished saved fixtures. Brier score measures probability error; lower is better. An observed rate different from the predicted rate is not automatically evidence of a poor model with a small sample.")

    bins = [(0,.5,"0–49%"),(.5,.7,"50–69%"),(.7,.8,"70–79%"),(.8,.9,"80–89%"),(.9,1.000001,"90–100%")]
    calibration_rows = []
    for lower, upper, label in bins:
        sub = sample[(sample["Probability"] >= lower) & (sample["Probability"] < upper)]
        if len(sub):
            calibration_rows.append({"Probability range":label, "Predictions":len(sub),
                                     "Average forecast":f'{sub["Probability"].mean():.1%}',
                                     "Actually occurred":f'{sub["Actual"].mean():.1%}'})
    st.markdown("**Confidence check by probability band**")
    if calibration_rows:
        st.dataframe(pd.DataFrame(calibration_rows), hide_index=True, use_container_width=True)
    st.caption("Each market is tested against its own outcome. This is a retrospective check of saved picks, not a prospective backtest across all fixtures. Saved matches may be selected non-randomly; related markets are not independent.")

    with st.expander("📋 All-market accuracy summary"):
        summary = []
        for name,_,_ in market_defs:
            group = frame[frame["Market"] == name]
            if group.empty:
                continue
            summary.append({"Market":name,"Finished matches":len(group),
                            "Average predicted":f'{group["Probability"].mean():.1%}',
                            "Actual rate":f'{group["Actual"].mean():.1%}',
                            "Brier":round(float(group["Brier"].mean()),3)})
        st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
    st.info("YANIDOLLARZ's prediction formula and Bet Tip selections have not been changed. Once enough completed records exist, we can use these measurements to test proposed improvements against the unchanged baseline.")


def show_performance_tracker(records, graded):
    """Evaluate immutable saved picks only after a final score exists."""
    st.subheader("🏆 Prediction Performance Tracker")
    correct = sum(result["correct"] for _, result in graded)
    pending = sum(r.get("status") == "Pending" for r in records)
    a, b, c, d = st.columns(4)
    a.metric("Correct", correct)
    b.metric("Incorrect", len(graded) - correct)
    c.metric("Pending", pending)
    d.metric("Accuracy", f"{correct / len(graded):.1%}" if graded else "—")
    if not graded:
        st.info("No completed predictions yet. Results will be graded when final scores arrive.")
        return

    rows = []
    for record, result in graded:
        probs = [record["home_win"], record["draw"], record["away_win"]]
        pick = ["Home", "Draw", "Away"][max(range(3), key=lambda i: probs[i])]
        rows.append({
            "Date": str(record.get("kickoff", ""))[:10],
            "Match": f'{record.get("home", "Home")} vs {record.get("away", "Away")}',
            "Prediction": pick,
            "Actual": result["actual"],
            "Final score": f'{record["score_home"]}–{record["score_away"]}',
            "Result": "✅ Correct" if result["correct"] else "❌ Incorrect",
            "Brier": round(result["brier"], 3),
            "Match ID": str(record.get("match_id", "")),
        })
    frame = pd.DataFrame(rows)
    selected = st.radio("Show results", ["All", "Correct", "Incorrect"], horizontal=True, key="tracker_result_filter")
    if selected != "All":
        frame = frame[frame["Result"] == ("✅ Correct" if selected == "Correct" else "❌ Incorrect")]
    st.dataframe(frame.drop(columns=["Match ID"]), use_container_width=True, hide_index=True)
    st.caption("Only finished matches with recorded full-time scores are graded. The predicted outcome is the highest home/draw/away probability.")

    with st.expander("📊 Accuracy by competition (optional)"):
        st.caption("Competition names are retrieved from football-data.org when requested. The first 25 completed predictions are checked to limit API usage.")
        if st.button("Load competition performance", key="tracker_load_competitions"):
            with st.spinner("Loading competition names..."):
                names, error = performance_competition_names(graded)
            if error:
                st.warning(f"Some competition data could not be loaded: {error}")
            league_rows = []
            for record, result in graded[:25]:
                league = names.get(str(record.get("match_id")))
                if league:
                    league_rows.append({"Competition": league, "Correct": result["correct"], "Evaluated": 1})
            if league_rows:
                grouped = pd.DataFrame(league_rows).groupby("Competition", as_index=False).sum()
                grouped["Accuracy (%)"] = (100 * grouped["Correct"] / grouped["Evaluated"]).round(1)
                st.dataframe(grouped, use_container_width=True, hide_index=True)
            else:
                st.info("Competition information isn't available for these matches.")


def show_performance_page():
    """Dedicated performance page reached from the sidebar."""
    st.title("📈 Prediction Performance")
    st.caption("Your saved predictions, graded after full-time results are recorded.")
    try:
        records = load_prediction_history()
    except Exception:
        logger.exception("Failed to load performance history")
        st.error("Unable to load prediction history from Supabase. Please try again.")
        return
    if not records:
        st.info("No predictions saved yet. Open Fixtures → Predict → Save prediction.")
        return
    graded = [(r, prediction_scores(r)) for r in records if r.get("status") == "Finished"]
    graded = [(r, result) for r, result in graded if result is not None]
    show_performance_tracker(records, graded)
    show_bet_tip_accuracy(graded)
    if st.button("📚 View full prediction history", key="performance_to_history"):
        change_dashboard_tab("History")
        st.rerun()


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
    show_performance_tracker(records, graded)
    st.subheader("Saved predictions")
    # Match IDs are stable; a current fixture supplies authoritative club crests.
    history_crest_matches = st.session_state.get("yani_recent_crest_matches", {})
    for record in records:
        score = prediction_scores(record)
        label = f'{record["home"]} vs {record["away"]} · {local_kickoff(record["kickoff"])}'
        with st.expander(label, expanded=False):
            crest_match = history_crest_matches.get(str(record.get("match_id")))
            if crest_match:
                render_fixture_teams(crest_match, compact=True)
            st.write(f'**Status:** {record["status"]}')
            st.write(f'**Saved at:** {record["saved_at"][:16].replace("T", " ")} UTC')
            st.write(f'**Home / Draw / Away:** {record["home_win"]:.1%} / {record["draw"]:.1%} / {record["away_win"]:.1%}')
            st.write(f'**Over 2.5:** {record["over_2_5"]:.1%} · **BTTS:** {record["btts"]:.1%}')
            st.write(f'**Expected goals:** {record["home_xg"]:.2f} / {record["away_xg"]:.2f} · **Risk:** {record["risk"]}')
            if score:
                st.write(f'**Final score:** {record["score_home"]}–{record["score_away"]} · **Actual outcome:** {score["actual"]}')
                st.write(f'**Brier:** {score["brier"]:.3f} · **Log loss:** {score["logloss"]:.3f} · **Outcome pick correct:** {"Yes" if score["correct"] else "No"}')


def render_prediction_explainer(p, home, away):
    """Explain the existing baseline without changing its probabilities."""
    st.subheader('🧠 Why the model favours this outcome')
    choices = [('Home win', p['home_win'], home), ('Draw', p['draw'], 'Neither team'), ('Away win', p['away_win'], away)]
    ranked = sorted(choices, key=lambda x: x[1], reverse=True)
    leading, runner_up = ranked[0], ranked[1]
    gap = 100 * (leading[1] - runner_up[1])
    if leading[0] == 'Draw':
        st.write(f"**Draw** is the most likely individual result at **{leading[1]:.1%}**. This does not mean a draw is certain.")
    else:
        st.write(f"**{leading[2]}** has the highest model probability (**{leading[1]:.1%}**), a **{gap:.1f} percentage-point** lead over the next most likely outcome.")
    left, right = st.columns(2)
    with left:
        st.metric(f'{home} · estimated goals', f"{p['home_xg']:.2f}")
        st.progress(min(1.0, p['home_xg'] / 4.0))
    with right:
        st.metric(f'{away} · estimated goals', f"{p['away_xg']:.2f}")
        st.progress(min(1.0, p['away_xg'] / 4.0))
    st.caption('The goal bars share a 0–4 scale; these are model estimates, not measured expected-goals (xG) data.')
    with st.expander('🔍 How this prediction was calculated', expanded=False):
        st.markdown(
            '- **Home estimate:** average of the home club’s smoothed home scoring rate and the away club’s smoothed away goals-conceded rate.\n'
            '- **Away estimate:** average of the away club’s smoothed away scoring rate and the home club’s smoothed home goals-conceded rate.\n'
            '- **Smoothing:** each rate includes five assumed matches at 1.35 goals to limit small-sample swings.\n'
            '- **Probabilities:** independent Poisson goal distributions are combined into home win, draw, away win and goals-market probabilities.\n'
            '- **Limitations:** the current baseline does not explicitly weight recent matches, injuries, opponent strength, or head-to-head results.'
        )
        st.write(f"Historical data: **{home}** {p['home_sample']} matches ({p['home_venue_sample']} home); **{away}** {p['away_sample']} matches ({p['away_venue_sample']} away).")
    st.caption('Explanations describe the existing baseline model. The highest probability is not a guarantee, and the model is not calibrated.')


def render_experimental_recent_comparison(match, baseline):
    """Display an optional rolling-window model; never replace saved baseline."""
    with st.expander('🧪 Experimental recent-form comparison (optional)', expanded=False):
        st.caption('Side-by-side research view only. Your saved predictions still use the original Poisson model. Recent form does not automatically mean better accuracy.')
        sample = st.select_slider(
            'Recent completed matches per team',
            options=[8, 10, 15, 20], value=10,
            key=f'recent_model_window_{match.get("id")}',
        )
        home_id = (match.get('homeTeam') or {}).get('id')
        away_id = (match.get('awayTeam') or {}).get('id')
        kickoff = match.get('utcDate')
        if not (home_id and away_id and kickoff):
            st.info('Confirmed teams and kickoff are needed for a comparison.')
            return
        hm, he = get_team_history(home_id, kickoff)
        am, ae = get_team_history(away_id, kickoff)
        if he or ae:
            st.warning('Recent historical results are unavailable for this comparison.')
            return
        recent, error = calculate_prediction(hm[:sample], am[:sample], home_id, away_id)
        if error:
            st.info('Not enough recent home/away matches for this window. ' + error)
            return
        st.markdown('**Original baseline vs recent-window model**')
        comparison = [
            ('Home win', 'home_win'), ('Draw', 'draw'), ('Away win', 'away_win'),
        ]
        for title, key in comparison:
            left, right = st.columns(2)
            left.metric(f'{title} · Baseline', f'{baseline[key]:.1%}')
            right.metric(f'{title} · Recent {sample}', f'{recent[key]:.1%}',
                         delta=f'{(recent[key] - baseline[key])*100:+.1f} pp',
                         delta_color='off')
        left, right = st.columns(2)
        left.metric('Baseline goals · home / away', f'{baseline["home_xg"]:.2f} / {baseline["away_xg"]:.2f}')
        right.metric('Recent goals · home / away', f'{recent["home_xg"]:.2f} / {recent["away_xg"]:.2f}')
        st.caption(f'Recent model uses up to {sample} completed matches for each team, still with the same venue filtering and smoothing. It does not use injuries, odds, or opponent-strength corrections. It has not been shown to outperform the baseline.')
        st.info('These are two model estimates, not measured chances. The experimental values are not saved to your prediction history.')



@st.cache_data(ttl=900, show_spinner=False)
def get_tipmaster_consensus():
    """Fetch available participant consensus modes; no invented opinions."""
    matches = []
    for mode in ("national", "classic"):
        url = f"https://tipmaster.net/api/agent/v1/consensus?mode={mode}"
        try:
            req = Request(url, headers={"User-Agent": "YANIDOLLARZ/1.0", "Accept": "application/json"})
            with urlopen(req, timeout=8) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
            if isinstance(payload, dict):
                found = payload.get("matches") or payload.get("data") or []
            elif isinstance(payload, list):
                found = payload
            else:
                found = []
            if isinstance(found, list):
                matches.extend(x for x in found if isinstance(x, dict))
        except (URLError, HTTPError, ValueError, TimeoutError, OSError):
            continue
    return matches, None if matches else "Community prediction data could not be retrieved or is not available."


@st.cache_data(ttl=900, show_spinner=False)
def get_published_prediction_headlines():
    """Optional free predictions RSS: show actual sourced articles, not a fabricated vote."""
    url = "https://sportspicklab.com/feed.xml"
    try:
        req = Request(url, headers={"User-Agent": "YANIDOLLARZ/1.0"})
        with urlopen(req, timeout=7) as response:
            content = response.read(1_000_000)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
        items = []
        for item in root.findall(".//item")[:120]:
            items.append({
                "title": (item.findtext("title") or "").strip(),
                "summary": re.sub(r"<[^>]*>", " ", item.findtext("description") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
            })
        return items
    except (URLError, HTTPError, ValueError, TimeoutError, OSError, ET.ParseError):
        return []


def _published_match_previews(home, away):
    items = get_published_prediction_headlines()
    def aliases(name):
        name = re.sub(r"\\b(fc|afc|cf|football club)\\b", " ", name.casefold())
        name = re.sub(r"\\s+", " ", name).strip()
        return {name, name.replace("manchester ", "man "), name.replace("tottenham hotspur", "tottenham")}
    home_names, away_names = aliases(home), aliases(away)
    matched = []
    for article in items:
        title = article["title"].casefold()
        if any(x and x in title for x in home_names) and any(x and x in title for x in away_names):
            matched.append(article)
    return matched[:3]


def _consensus_team_key(value):
    if isinstance(value, dict):
        value = value.get("name") or value.get("team") or ""
    value = str(value).casefold()
    value = re.sub(r"\b(fc|cf|afc|ac|sc|football|club|united|city)\b", " ", value)
    return re.sub(r"[^a-z0-9]", "", value)


def _match_consensus_record(records, home, away):
    h, a = _consensus_team_key(home), _consensus_team_key(away)
    if len(h) < 3 or len(a) < 3:
        return None
    for record in records:
        if not isinstance(record, dict):
            continue
        home_value = record.get("home") or record.get("homeTeam") or record.get("home_team")
        away_value = record.get("away") or record.get("awayTeam") or record.get("away_team")
        if _consensus_team_key(home_value) == h and _consensus_team_key(away_value) == a:
            return record
    return None


def _consensus_shares(record):
    """Only accept an unambiguous home/draw/away triple; never guess field meaning."""
    if not isinstance(record, dict):
        return None
    sources = [record]
    for key in ("all", "allPlayers", "all_players", "consensus", "distribution", "shares", "percentages", "votes", "prediction"):
        obj = record.get(key)
        if isinstance(obj, dict):
            sources.append(obj)
            for nested in ("all", "allPlayers", "all_players", "shares", "percentages"):
                if isinstance(obj.get(nested), dict):
                    sources.append(obj[nested])
    for obj in sources:
        for keys in (("home", "draw", "away"), ("homeWin", "draw", "awayWin"),
                     ("home_win", "draw", "away_win"), ("1", "X", "2"),
                     ("homePct", "drawPct", "awayPct"), ("homePercent", "drawPercent", "awayPercent")):
            if not all(k in obj for k in keys):
                continue
            try:
                raw = [float(str(obj[k]).strip().replace("%", "")) for k in keys]
                if min(raw) < 0:
                    continue
                if 98 <= sum(raw) <= 102:
                    return [v / sum(raw) for v in raw]
                if .98 <= sum(raw) <= 1.02:
                    return [v / sum(raw) for v in raw]
            except (TypeError, ValueError):
                continue
    return None


def show_bet_tip(match, p, home, away):
    """YANIDOLLARZ's concise, model-derived picks. No invented expert consensus."""
    home_p, draw_p, away_p = (float(p[k]) for k in ("home_win", "draw", "away_win"))
    btts = float(p["btts"])
    overs = p["overs"]
    picks = [
        (f"{home} or Draw (1X)", home_p + draw_p, "Double chance"),
        (f"{away} or Draw (X2)", away_p + draw_p, "Double chance"),
        (f"{home} or {away} (12)", home_p + away_p, "Double chance"),
        ("Both Teams to Score — Yes", btts, "BTTS"),
        ("Both Teams to Score — No", 1 - btts, "BTTS"),
        ("Over 1.5 Goals", float(overs.get(1.5, 0)), "Goals"),
        ("Under 2.5 Goals", 1 - float(overs.get(2.5, 1)), "Goals"),
        ("Over 2.5 Goals", float(overs.get(2.5, 0)), "Goals"),
        ("Under 3.5 Goals", 1 - float(overs.get(3.5, 1)), "Goals"),
    ]
    picks = [(label, max(0.0, min(1.0, prob)), category) for label, prob, category in picks]
    ranked = sorted(picks, key=lambda item: item[1], reverse=True)
    top = ranked[0]
    match_winner = max([(home, home_p), ("Draw", draw_p), (away, away_p)], key=lambda x: x[1])
    best_btts = max([p for p in picks if p[2] == "BTTS"], key=lambda x: x[1])
    best_goals = max([p for p in picks if p[2] == "Goals"], key=lambda x: x[1])
    best_double = max([p for p in picks if p[2] == "Double chance"], key=lambda x: x[1])

    # Styled native HTML cards instead of Markdown/progress widgets.
    # The probabilities are the original model estimates; no bookmaker odds are invented.
    def esc(value):
        return html.escape(str(value), quote=True)

    def confidence(prob):
        return "Higher" if prob >= .75 else ("Moderate" if prob >= .60 else "Low")

    def tip_row(label, prob, category, featured=False):
        pct = round(prob * 100)
        tone = "high" if prob >= .75 else ("medium" if prob >= .60 else "low")
        return (f'<div class="yt-tip-row {"yt-featured" if featured else ""}">'
                f'<div class="yt-tip-name"><span class="yt-category">{esc(category)}</span>'
                f'<strong>{esc(label)}</strong></div>'
                f'<div class="yt-tip-confidence"><span class="yt-pill {tone}">{confidence(prob)}</span></div>'
                f'<div class="yt-tip-prob"><div class="yt-track"><div class="yt-fill {tone}" style="width:{pct}%"></div></div>'
                f'<strong>{pct}%</strong></div></div>')

    css = """<style>
    .yt-wrap{color:#eaf3ff;font-family:inherit;margin:6px 0 26px}
    .yt-eyebrow{color:#6caaff;font-weight:800;letter-spacing:1.6px;font-size:11px;margin-bottom:9px}
    .yt-title{font-size:27px;font-weight:850;margin-bottom:6px}
    .yt-muted{font-size:13px;color:#93a8c4;margin-bottom:18px}
    .yt-hero{background:linear-gradient(110deg,#123e55,#0d2940 64%,#123056);border:1px solid #277a99;border-radius:15px;padding:21px 24px;margin-bottom:14px}
    .yt-hero-label{color:#7edcce;letter-spacing:1.3px;font-size:11px;font-weight:800}
    .yt-hero-pick{font-size:25px;font-weight:850;color:white;margin:9px 0}
    .yt-hero-foot{font-size:13px;color:#c6deed;line-height:1.55}
    .yt-no-pick{background:linear-gradient(110deg,#4b321c,#28313e);border-color:#a77a35}
    .yt-no-pick .yt-hero-label{color:#ffd17a}
    .yt-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:22px}
    .yt-mini{background:#142940;border:1px solid #284661;border-radius:12px;padding:16px;min-width:0}
    .yt-mini-label{color:#92b1d0;font-size:11px;text-transform:uppercase;letter-spacing:.7px;font-weight:750}
    .yt-mini-main{color:#fff;font-size:16px;font-weight:800;margin:8px 0 5px;overflow-wrap:anywhere}
    .yt-mini-sub{color:#9bb5ce;font-size:12px}
    .yt-table-title{font-size:20px;font-weight:850;margin:8px 0 12px}
    .yt-table{border:1px solid #294864;border-radius:13px;overflow:hidden;background:#102238}
    .yt-tip-head,.yt-tip-row{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(75px,.6fr) minmax(140px,1fr);align-items:center;gap:12px;padding:14px 17px}
    .yt-tip-head{background:#1c3955;color:#b7cce3;font-size:12px;text-transform:uppercase;font-weight:800;letter-spacing:.6px}
    .yt-tip-row{border-top:1px solid #263d56;min-height:72px}
    .yt-tip-row:nth-child(odd){background:#132940}
    .yt-featured{background:#143b42!important;border-left:3px solid #31c7a4}
    .yt-tip-name{display:flex;flex-direction:column;gap:5px;min-width:0}
    .yt-tip-name strong{font-size:14px;overflow-wrap:anywhere}
    .yt-category{font-size:11px;color:#86a7c9}
    .yt-pill{display:inline-block;font-size:11px;font-weight:750;border-radius:20px;padding:5px 9px}
    .yt-pill.high{color:#71e5c5;background:#123f3b}.yt-pill.medium{color:#ffcd77;background:#433721}.yt-pill.low{color:#f1a6a6;background:#462c35}
    .yt-tip-prob{display:flex;align-items:center;gap:12px}
    .yt-tip-prob strong{font-size:14px;min-width:37px;text-align:right}
    .yt-track{background:#30445b;border-radius:20px;height:11px;flex:1;overflow:hidden}
    .yt-fill{height:100%;border-radius:20px;background:#31c7a4}.yt-fill.medium{background:#e9b65b}.yt-fill.low{background:#7189a6}
    .yt-note{font-size:12px;color:#91a9c3;margin-top:11px;line-height:1.6}
    @media(max-width:650px){.yt-summary{grid-template-columns:1fr}.yt-tip-head,.yt-tip-row{grid-template-columns:minmax(0,1fr) 75px 110px;gap:5px;padding:11px 9px}.yt-tip-name strong{font-size:12px}.yt-tip-prob{gap:5px}.yt-track{height:8px}.yt-title{font-size:22px}.yt-hero-pick{font-size:21px}}
    </style>"""
    # Step 25.3: interpret model and news without silently changing the Poisson baseline.
    # RSS keywords cannot establish a player's injury, an expert consensus or a numerical impact.
    articles, errors = get_free_football_news()
    home_terms, away_terms = _news_team_terms(home), _news_team_terms(away)
    def _mentions_news(content, terms):
        return any(re.search(r"(?<!\\w)" + re.escape(term) + r"(?!\\w)", content) for term in terms)
    relevant = [article for article in articles
                if _mentions_news((article["title"] + " " + article.get("summary", "")).lower(), home_terms)
                or _mentions_news((article["title"] + " " + article.get("summary", "")).lower(), away_terms)]
    fitness_pattern = re.compile(r"\\b(injur(?:y|ies|ed)|sidelined|hamstring|ankle|knee|fitness|suspend(?:ed|sion)|doubtful|ruled out)\\b", re.I)
    rivalry_pattern = re.compile(r"\\b(derby|rivalry|rivals)\\b", re.I)
    fitness_reports = [a for a in relevant if fitness_pattern.search(a["title"] + " " + a.get("summary", ""))]
    rivalry_reports = [a for a in relevant if rivalry_pattern.search(a["title"] + " " + a.get("summary", ""))]
    # Keep a clear difference between "highest probability" and "worth betting".
    primary = top[1] >= .70
    hero_class = "yt-hero" if primary else "yt-hero yt-no-pick"
    hero_label = "🏆 YANIDOLLARZ TOP MODEL PICK" if primary else "⚠️ YANIDOLLARZ VERDICT · NO STRONG PICK"
    hero_pick = top[0] if primary else "No strong selection for this fixture"
    hero_text = (f"YANIDOLLARZ leans toward {top[0]} ({top[1]:.0%} estimated chance). "
                 + ("It is our highest-probability evaluated market, but odds and match-day news can change the decision."
                    if primary else "None of our evaluated markets clears our 70% probability threshold."))
    rows = [top, best_double, best_btts, best_goals,
            (f"{match_winner[0]} to win" if match_winner[0] != "Draw" else "Draw", match_winner[1], "Match result")]
    seen = set()
    table_rows = []
    for label, prob, category in rows:
        if label in seen:
            continue
        seen.add(label)
        table_rows.append(tip_row(label, prob, category, label == top[0]))
    output = (css + '<section class="yt-wrap">'
              '<div class="yt-eyebrow">MATCH INTELLIGENCE · YANIDOLLARZ OPINION</div>'
              '<div class="yt-title">🎯 YANIDOLLARZ Bet Tip</div>'
              '<div class="yt-muted">Our model-based picks, ranked by estimated chance</div>'
              f'<div class="{hero_class}"><div class="yt-hero-label">{hero_label}</div>'
              f'<div class="yt-hero-pick">{esc(hero_pick)}</div>'
              f'<div class="yt-hero-foot">{esc(hero_text)}</div></div>'
              '<div class="yt-summary">'
              f'<div class="yt-mini"><div class="yt-mini-label">⚽ Match winner lean</div><div class="yt-mini-main">{esc(match_winner[0])}</div><div class="yt-mini-sub">{match_winner[1]:.0%} estimated chance</div></div>'
              f'<div class="yt-mini"><div class="yt-mini-label">🥅 BTTS opinion</div><div class="yt-mini-main">{esc(best_btts[0])}</div><div class="yt-mini-sub">{best_btts[1]:.0%} estimated chance</div></div>'
              f'<div class="yt-mini"><div class="yt-mini-label">🛡️ Double chance</div><div class="yt-mini-main">{esc(best_double[0])}</div><div class="yt-mini-sub">{best_double[1]:.0%} estimated chance</div></div>'
              '</div><div class="yt-table-title">📋 YANIDOLLARZ Betting Tips</div>'
              '<div class="yt-table"><div class="yt-tip-head"><span>Betting tip</span><span>Confidence</span><span>Model probability</span></div>'
              + ''.join(table_rows) + '</div>'
              '<div class="yt-note">Percentages are estimates from the existing Poisson model, not bookmaker odds or independently calibrated success rates. '
              'Higher probability does not necessarily mean better value. Every selection can lose; skipping a bet is valid.</div></section>')
    st.markdown(output, unsafe_allow_html=True)

    # Show match-specific headlines only; the news reader elsewhere handles broader team news.
    direct_news = [article for article in articles
                   if _mentions_news(article["title"].lower(), home_terms)
                   and _mentions_news(article["title"].lower(), away_terms)]
    if direct_news:
        st.markdown("#### 📰 Match news")
        for article in direct_news[:3]:
            with st.expander("📰 " + article["title"]):
                st.caption(f"{article['publisher']} · {article.get('published') or 'Date unavailable'}")
                st.write(article.get("summary", "").strip() or "No summary available in the free feed.")
    st.markdown("#### 👥 Community vs YANIDOLLARZ")
    records, community_error = get_tipmaster_consensus()
    crowd = _match_consensus_record(records, home, away)
    shares = _consensus_shares(crowd) if crowd else None
    def compare_card(title, values, subtitle, favourite, highlight=False):
        names = [home, "Draw", away]
        colours = ["#18a7f8", "#a9b9d0", "#ff3859"]
        cells = "".join(
            f'<div class="yc-outcome"><span>{html.escape(str(name))}</span>'
            f'<strong>{value:.0%}</strong>'
            f'<div class="yc-track"><div style="width:{max(0,min(100,value*100)):.1f}%;background:{colours[i]}"></div></div></div>'
            for i,(name,value) in enumerate(zip(names,values))
        )
        return (f'<section class="yc-panel"><div class="yc-kicker">{html.escape(title)}</div>'
                f'<div class="yc-sub">{html.escape(subtitle)}</div>'
                f'<div class="yc-outcomes">{cells}</div>'
                f'<div class="yc-fav">⭐ Favourite: <strong>{html.escape(str(favourite))}</strong></div></section>')
    model_values = (home_p, draw_p, away_p)
    model_idx = max(range(3), key=lambda i:model_values[i])
    labels = [home, "Draw", away]
    card_css = """<style>
    .yc-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin:13px 0}
    .yc-panel{border:1px solid #285073;border-radius:16px;padding:21px;background:linear-gradient(135deg,#0b2038,#112b47);color:#eef6ff}
    .yc-kicker{font-weight:850;font-size:18px;margin-bottom:5px}
    .yc-sub{font-size:12px;color:#9ab4ce;margin-bottom:20px;min-height:30px}
    .yc-outcomes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}
    .yc-outcome{min-width:0;display:flex;flex-direction:column;gap:9px;text-align:center}
    .yc-outcome span{font-size:12px;color:#c5d8ec;overflow-wrap:anywhere}
    .yc-outcome strong{font-size:26px;color:#fff}
    .yc-track{background:#283d56;height:10px;border-radius:20px;overflow:hidden}
    .yc-track div{height:100%;border-radius:20px}
    .yc-fav{margin-top:19px;border:1px solid #32567a;border-radius:10px;padding:12px;color:#c4d9ef;font-size:13px}
    .yc-fav strong{color:#fff}
    .yc-status{background:#102a46;border:1px solid #2d5279;border-radius:12px;padding:15px;color:#bcd4ed;font-size:13px}
    @media(max-width:750px){.yc-grid{grid-template-columns:1fr}.yc-panel{padding:14px}.yc-outcome strong{font-size:22px}}
    </style>"""
    if shares:
        crowd_idx = max(range(3), key=lambda i:shares[i])
        agreement = model_idx == crowd_idx
        html_cards = (card_css + '<div class="yc-grid">'
                      + compare_card("🎯 YANIDOLLARZ prediction",model_values,
                                     "Existing Poisson model · match result",labels[model_idx])
                      + compare_card("👥 Community predictions",shares,
                                     "TipMaster participants · shares of picks",labels[crowd_idx])
                      + '</div>')
        st.markdown(html_cards,unsafe_allow_html=True)
        if agreement:
            st.success(f"**Same favourite:** Both YANIDOLLARZ and participating predictors favour {labels[model_idx]}.")
        else:
            st.info(f"**Different favourites:** YANIDOLLARZ favours {labels[model_idx]}, while participating predictors favour {labels[crowd_idx]}.")
        st.caption("Community percentages are shares of submitted picks, not model probabilities or a representative poll.")
    else:
        st.markdown(card_css + '<div class="yc-grid">'
                    + compare_card("🎯 YANIDOLLARZ prediction",model_values,
                                   "Existing Poisson model · match result",labels[model_idx])
                    + '<section class="yc-panel"><div class="yc-kicker">👥 Community predictions</div>'
                    '<div class="yc-sub">TipMaster prediction-game participants</div>'
                    '<div class="yc-status">No verified votes for this fixture are currently available. '
                    'No percentages have been estimated or invented.</div></section></div>',
                    unsafe_allow_html=True)
        previews = _published_match_previews(home, away)
        if previews:
            st.markdown("**Published match previews**")
            for article in previews:
                with st.expander("📰 " + article["title"]):
                    st.write(article.get("summary") or "No summary supplied by the publisher.")
    st.caption("Community data is fetched automatically when available. No external pages or manual input required.")
    if errors:
        st.caption("Some news feeds were unavailable: " + ", ".join(errors))


# STEP 25.6 — verified fixture intelligence.
# API-FOOTBALL is optional; the free plan offers a limited daily quota.
# Never present RSS keyword matches as confirmed player injuries.
@st.cache_data(ttl=3600, show_spinner=False)
def _yani_fixture_intel_api(home, away, kickoff, key):
    if not key:
        return None, "Add API_FOOTBALL_KEY in Streamlit Secrets to enable verified lineup and injury data."
    try:
        day = datetime.fromisoformat(str(kickoff).replace("Z","+00:00")).date().isoformat()
    except (ValueError, TypeError):
        return None, "Fixture date is unavailable."
    def get(path):
        req = Request("https://v3.football.api-sports.io/"+path,
                      headers={"x-apisports-key":key,"Accept":"application/json"})
        with urlopen(req,timeout=12) as response:
            return json.load(response)
    try:
        payload=get("fixtures?date="+day)
        candidates=payload.get("response",[])
        def norm(x):
            x=re.sub(r"\b(fc|afc|cf|football club|united fc)\b"," ",str(x).casefold())
            return re.sub(r"[^a-z0-9]","",x)
        def similar(a,b):
            a,b=norm(a),norm(b)
            return bool(a and b and (a==b or (len(a)>5 and a in b) or (len(b)>5 and b in a)))
        fixture=next((x for x in candidates
            if similar((x.get("teams",{}).get("home") or {}).get("name",""),home)
            and similar((x.get("teams",{}).get("away") or {}).get("name",""),away)),None)
        if not fixture:
            return None,"No matching fixture found in the lineup provider for this date."
        fid=(fixture.get("fixture") or {}).get("id")
        if not fid:
            return None,"Fixture found without a usable provider ID."
        lineups=get(f"fixtures/lineups?fixture={fid}").get("response",[])
        injuries=get(f"injuries?fixture={fid}").get("response",[])
        return {"lineups":lineups,"injuries":injuries,"fixture":fixture},None
    except HTTPError as exc:
        if exc.code in (401,403):
            return None,"Lineup provider rejected the API key or access is restricted."
        if exc.code==429:
            return None,"Lineup provider daily/rate limit reached."
        return None,f"Lineup provider unavailable (HTTP {exc.code})."
    except (URLError,OSError,TimeoutError,ValueError,TypeError):
        return None,"Lineup provider is temporarily unavailable."



def _yani_lineup_pitch(lineup, team_name):
    """Render provider-supplied starting XI on a football pitch, without invented ratings."""
    players = [x.get("player") or {} for x in (lineup.get("startXI") or [])]
    if not players:
        return ""
    esc = lambda v: html.escape(str(v), quote=True)
    positions = []
    for i, player in enumerate(players):
        grid = str(player.get("grid") or "")
        try:
            row, col = [int(x) for x in grid.split(":")]
            if not 1 <= row <= 6 or not 1 <= col <= 6:
                raise ValueError()
            positions.append((row, col, player))
        except (ValueError, TypeError):
            positions.append((None, None, player))
    # API-FOOTBALL's grid: goalkeeper is row 1; row increases toward forwards.
    # When the provider omits grid, use the formation to display an approximate layout.
    if any(row is None for row, _, _ in positions):
        formation = str(lineup.get("formation") or "4-4-2")
        counts = [int(n) for n in re.findall(r"\d+", formation)]
        if sum(counts) != 10:
            counts = [4, 4, 2]
        slots = [(1, 1)]
        for row, count in enumerate(counts, 2):
            slots.extend((row, col) for col in range(1, count + 1))
        positions = [(slots[i][0], slots[i][1], player) for i, (_, _, player) in enumerate(positions[:11])]
    rows = sorted(set(r for r, _, _ in positions))
    items = []
    for row, col, player in positions:
        group = [c for r, c, _ in positions if r == row]
        total = max(group) if group else 1
        x = 50 if total == 1 else 10 + (col - 1) * 80 / (total - 1)
        y = 9 + (row - min(rows)) * 78 / max(1, max(rows) - min(rows))
        name = str(player.get("name") or "Player")
        number = player.get("number")
        initials = "".join(w[0] for w in name.split()[-2:] if w)[:2].upper() or "?"
        items.append(
            '<div class="yi-player" style="left:' + f'{x:.2f}%;top:{y:.2f}%' + '">'
            '<div class="yi-avatar">' + esc(initials) + '</div>'
            '<div class="yi-player-name">' + (esc(str(number)) + " " if number is not None else "") +
            esc(name) + '</div></div>'
        )
    return (
        '<div class="yi-pitch"><div class="yi-pitch-mid"></div>'
        '<div class="yi-pitch-circle"></div><div class="yi-pitch-box yi-top"></div>'
        '<div class="yi-pitch-box yi-bottom"></div>' + "".join(items) + '</div>'
    )


def show_injury_lineup_intelligence(match, home, away):
    st.markdown("""<style>
    .yi-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:12px 0}
    .yi-card{background:linear-gradient(140deg,#0c2036,#142c49);border:1px solid #2c5177;border-radius:16px;padding:19px;color:#f0f7ff;min-width:0}
    .yi-label{font-size:12px;color:#9ab9d7;letter-spacing:.6px;font-weight:700}
    .yi-title{font-size:20px;font-weight:850;margin:8px 0}
    .yi-row{padding:10px 0;border-top:1px solid #2b435e;font-size:13px;color:#d4e6f9;overflow-wrap:anywhere}
    .yi-tag{display:inline-block;background:#173d54;border:1px solid #347c87;color:#9ff0d7;border-radius:30px;padding:5px 10px;font-size:11px}
    .yi-muted{color:#a8bdd5;font-size:12px;line-height:1.6}
    .yi-injury-heading{margin:22px 0 9px;font-size:17px;font-weight:800;color:#f2f7ff}
    .yi-injury-row{display:flex;align-items:center;gap:12px;padding:13px 3px;border-bottom:1px solid #34516b}
    .yi-injury-icon{flex:none;width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:#f0f4fa;color:#a8213d;font-size:21px;font-weight:900}
    .yi-injury-name{font-size:14px;font-weight:750;color:#f0f6ff}
    .yi-injury-status{font-size:12px;color:#ff8d9d;margin-top:3px}
    .yi-injury-reason{color:#a9bed4;margin-left:7px}
    .yi-injury-empty{padding:14px;background:#10283e;border:1px solid #2b4a67;border-radius:10px;color:#adc2d9;font-size:12px;line-height:1.6}
    .yi-pitch{position:relative;min-height:540px;margin-top:14px;border:2px solid #9ccbbb;
      border-radius:10px;background:repeating-linear-gradient(0deg,#337e67 0%,#337e67 16.66%,#39876f 16.66%,#39876f 33.33%);
      overflow:hidden}
    .yi-pitch:before{content:"";position:absolute;inset:10px;border:2px solid #b6dccb80;pointer-events:none}
    .yi-pitch-mid{position:absolute;top:50%;left:10px;right:10px;border-top:2px solid #b6dccb80}
    .yi-pitch-circle{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
      width:115px;height:115px;border:2px solid #b6dccb80;border-radius:50%}
    .yi-pitch-box{position:absolute;left:24%;width:52%;height:15%;border:2px solid #b6dccb80}
    .yi-top{top:10px;border-top:0}.yi-bottom{bottom:10px;border-bottom:0}
    .yi-player{position:absolute;transform:translate(-50%,-50%);display:flex;flex-direction:column;
      align-items:center;gap:3px;width:20%;z-index:2}
    .yi-avatar{display:grid;place-items:center;width:38px;height:38px;background:#eef5f8;color:#12314b;
      border:3px solid #d9f4e6;border-radius:50%;font-size:12px;font-weight:900;box-shadow:0 3px 10px #14372a88}
    .yi-player-name{color:#fff;font-size:11px;font-weight:750;text-align:center;
      text-shadow:0 1px 4px #001b16,0 2px 5px #001b16;line-height:1.2;overflow-wrap:anywhere}
    @media(max-width:560px){.yi-pitch{min-height:480px}.yi-avatar{width:32px;height:32px}.yi-player-name{font-size:9px}}

    @media(max-width:720px){.yi-grid{grid-template-columns:1fr}.yi-card{padding:14px}}
    </style>""",unsafe_allow_html=True)
    st.markdown("### 🏥 Injury & Lineup Intelligence")
    st.caption("Automatically matched to the selected fixture. Unverified reports are never treated as confirmed absences.")
    key=st.secrets.get("API_FOOTBALL_KEY","")
    result,error=_yani_fixture_intel_api(home,away,match.get("utcDate"),key)
    teams=[home,away]
    def esc(v): return html.escape(str(v))
    blocks=[]
    for team in teams:
        lineup=None
        injuries=[]
        if result:
            for item in result["lineups"]:
                name=(item.get("team") or {}).get("name","")
                clean=lambda v: re.sub(r"[^a-z0-9]","",re.sub(r"\b(fc|afc|cf)\b","",str(v).casefold()))
                if clean(team)==clean(name) or (len(clean(name))>6 and clean(name) in clean(team)):
                    lineup=item
                    break
            for item in result["injuries"]:
                name=(item.get("team") or {}).get("name","")
                clean=lambda v: re.sub(r"[^a-z0-9]","",re.sub(r"\b(fc|afc|cf)\b","",str(v).casefold()))
                if clean(team)==clean(name) or (len(clean(name))>6 and clean(name) in clean(team)):
                    injuries.append(item)
        if lineup and lineup.get("startXI"):
            players=[(x.get("player") or {}).get("name","") for x in lineup["startXI"]]
            formation=esc(lineup.get("formation") or "Not listed")
            lineup_body='<div class="yi-tag">✓ Starting XI provided by API-FOOTBALL</div><div class="yi-row">Formation: '+formation+'</div>'
            lineup_body+=_yani_lineup_pitch(lineup, team)
            substitutes=[(x.get("player") or {}).get("name") for x in lineup.get("substitutes",[])]
            if substitutes:
                lineup_body+='<div class="yi-label" style="margin-top:16px">SUBSTITUTES</div>'
                lineup_body+='<div class="yi-row">'+esc(", ".join(n for n in substitutes if n))+'</div>' 
        else:
            lineup_body='<div class="yi-muted">No confirmed starting XI available from the provider yet.</div>'
        if injuries:
            injury_parts=[]
            for x in injuries[:16]:
                player=x.get("player") or {}
                name=esc(player.get("name") or "Player")
                kind=esc(player.get("type") or "Availability report")
                reason=esc(player.get("reason") or "Reason not provided")
                injury_parts.append(
                    '<div class="yi-injury-row"><div class="yi-injury-icon">✚</div>'
                    '<div><div class="yi-injury-name">'+name+'</div>'
                    '<div class="yi-injury-status">'+kind+
                    '<span class="yi-injury-reason">'+reason+'</span></div></div></div>')
            injury_body="".join(injury_parts)
        else:
            injury_body=('<div class="yi-injury-empty">No fixture-specific injury or suspension records '
                         'were returned. This does not mean every player is available.</div>')
        blocks.append('<section class="yi-card"><div class="yi-label">SQUAD INTELLIGENCE</div>'
                      '<div class="yi-title">'+esc(team)+'</div>'
                      '<div class="yi-label">👥 STARTING XI</div>'+lineup_body+
                      '<div class="yi-injury-heading">✚ Injuries and suspensions</div>'
                      +injury_body+'</section>')
    st.markdown('<div class="yi-grid">'+''.join(blocks)+'</div>',unsafe_allow_html=True)
    if error:
        st.info(error)
    if not result:
        articles,_=get_free_football_news()
        def tokens(name):
            parts=re.sub(r"\b(fc|afc|football club)\b"," ",name.casefold()).split()
            return [x for x in parts if len(x)>3 and x not in ("united","city","real","club")]
        injury_re=re.compile(r"\b(injur(?:y|ed|ies)|suspend(?:ed|sion)|ruled out|fitness|doubtful)\b",re.I)
        for team in teams:
            words=tokens(team)
            reports=[a for a in articles if any(re.search(r"\b"+re.escape(t)+r"\b",a.get("title","").casefold()) for t in words)
                     and injury_re.search(a.get("title",""))]
            if reports:
                st.markdown("**📰 "+team+" — availability headlines (unverified)**")
                for a in reports[:2]:
                    with st.expander(a.get("title","Football news")):
                        st.caption(a.get("publisher","Publisher unavailable"))
                        st.write(a.get("summary","") or "No article summary supplied.")
    st.caption("API-FOOTBALL fixture data is independent of the YANIDOLLARZ Poisson model. "
               "Predictions are not adjusted based on missing or unverified injury reports.")

def show_prediction(match, risk_only=False):
    home_team, away_team = match.get('homeTeam') or {}, match.get('awayTeam') or {}
    home = home_team.get('name') or 'Home'
    away = away_team.get('name') or 'Away'
    st.title('🛡️ Risk Analysis' if risk_only else '🎯 Match Predictions')
    st.caption('MODEL MATCH CENTRE  •  Independent Poisson estimates')
    st.markdown(
        '<div class="yani-pred-hero"><div class="yani-pred-kicker">MATCH PREVIEW · '
        + html.escape(local_kickoff(match.get('utcDate'))) + '</div>'
        + '<div class="yani-pred-fixture">'
        + f'<div class="yani-pred-club">{crest_markup(home_team, 66)}<strong>{html.escape(home)}</strong><small>HOME</small></div>'
        + '<div class="yani-pred-vs">VS</div>'
        + f'<div class="yani-pred-club">{crest_markup(away_team, 66)}<strong>{html.escape(away)}</strong><small>AWAY</small></div>'
        + '</div></div>', unsafe_allow_html=True)
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
    st.caption('Experimental model estimates — not calibrated or guaranteed outcomes.')
    st.markdown("""<style>
    /* Step 24.2: horizontal prediction tabs with mobile swipe-to-scroll */
    div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) [role="radiogroup"] {
        display:flex !important; flex-wrap:nowrap !important; gap:7px !important;
        overflow-x:auto !important; scrollbar-width:thin; padding:7px 3px 12px !important;
        border-bottom:1px solid #304864; margin-bottom:12px;
    }
    div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) label {
        flex:0 0 auto !important; border:1px solid #344e6c; border-radius:9px;
        padding:9px 13px !important; background:#15263c; white-space:nowrap;
        color:#d8e7ff !important; cursor:pointer; transition:background .15s;
    }
    div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) label:has(input:checked) {
        background:#174b83 !important; border-color:#4ca6ff !important;
        box-shadow:inset 0 -2px 0 #43c9e9;
    }
    div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) label [data-testid="stMarkdownContainer"] p {
        font-size:13px !important; font-weight:650 !important;
    }
    div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) label > div:first-child:has(input) {display:none !important;}
    .yani-pred-tabs-label {font-size:11px;font-weight:800;letter-spacing:1.5px;color:#8fb6e5;margin-top:20px;}
    @media(max-width:700px) {
      div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) label {padding:9px 11px !important;}
    }
    </style>""", unsafe_allow_html=True)
    # Step 24.2: native Streamlit navigation. Only the selected panel is rendered.
    # Native widgets keep navigation keyboard-accessible and working on mobile.
    sections = ['🎯 Prediction', '⚽ Expected Goals', '🥅 Goals Markets',
                '📋 Exact Scores', '🎯 Bet Tip', '🏥 Injuries & Lineups', '🛡️ Model & Risk']
    if risk_only:
        sections = ['🛡️ Model & Risk', '🎯 Prediction', '⚽ Expected Goals',
                    '🥅 Goals Markets', '📋 Exact Scores', '🎯 Bet Tip', '🏥 Injuries & Lineups']
    st.markdown('<div class="yani-pred-tabs-label">EXPLORE MATCH INSIGHTS</div>', unsafe_allow_html=True)
    selected_section = st.radio(
        'Match prediction sections', sections, horizontal=True,
        label_visibility='collapsed', key=f'yani_prediction_section_{match.get("id")}_{"risk" if risk_only else "full"}',
    )
    if selected_section == '🎯 Prediction':
        st.subheader('📊 Match outcome probabilities')
        outcomes = [('HOME WIN', home, p['home_win'], 'home'), ('DRAW', 'Level score', p['draw'], 'draw'), ('AWAY WIN', away, p['away_win'], 'away')]
        leader = max(outcomes, key=lambda x: x[2])[3]
        cards = []
        for label, club, probability, key in outcomes:
            cards.append(f'<div class="yani-outcome-card {"is-leader" if key == leader else ""}">'
                         f'<div class="yani-outcome-label">{label}</div>'
                         f'<div class="yani-outcome-number">{probability:.1%}</div>'
                         f'<div class="yani-outcome-club">{html.escape(club)}</div>'
                         f'<div class="yani-outcome-track"><span style="width:{min(100,max(0,probability*100)):.1f}%"></span></div></div>')
        st.markdown('<div class="yani-outcomes">'+''.join(cards)+'</div>', unsafe_allow_html=True)
        st.caption('Highlighted card = highest individual outcome probability, not a guaranteed result.')
        ranked = sorted([('Home win', p['home_win'], home), ('Draw', p['draw'], 'Draw'), ('Away win', p['away_win'], away)], key=lambda x: x[1], reverse=True)
        st.info(f'Most likely outcome: **{ranked[0][0]} ({ranked[0][1]:.1%})** · {ranked[0][2]}. This is a model estimate, not a certainty.')
    elif selected_section == '⚽ Expected Goals':
        st.subheader('⚽ Expected goals')
        st.markdown(
            '<div class="yani-goals-panel">'
            + f'<div><span>{html.escape(home)}</span><strong>{p["home_xg"]:.2f}</strong></div>'
            + '<span class="yani-goals-separator">ESTIMATED GOALS</span>'
            + f'<div><span>{html.escape(away)}</span><strong>{p["away_xg"]:.2f}</strong></div>'
            + '</div>', unsafe_allow_html=True)
        st.caption('These are model-estimated goal rates, not measured xG statistics.')
        st.markdown('#### 🧠 Why the model favours this outcome')
        render_prediction_explainer(p, home, away)
    elif selected_section == '🥅 Goals Markets':
        st.subheader('🥅 Goals markets')
        markets = [(f'Over {line} goals', prob) for line, prob in p['overs'].items()]
        markets.extend([('Both teams to score · Yes', p['btts']), ('Both teams to score · No', 1-p['btts'])])
        market_cards = ''.join(
            f'<div class="yani-market"><span>{html.escape(label)}</span><strong>{value:.1%}</strong></div>'
            for label, value in markets
        )
        st.markdown('<div class="yani-market-grid">'+market_cards+'</div>', unsafe_allow_html=True)
        st.caption('Goals markets are estimates from the same independent-Poisson model.')
    elif selected_section == '📋 Exact Scores':
        st.subheader('🎯 Most likely exact scores')
        score_rows = ''.join(
            f'<div class="yani-score-row"><span class="yani-score-rank">{i}</span>'
            f'<span class="yani-score-club">{html.escape(home)}</span>'
            f'<strong>{h} – {a}</strong><span class="yani-score-club">{html.escape(away)}</span>'
            f'<span class="yani-score-pct">{prob:.1%}</span></div>'
            for i, (h, a, prob) in enumerate(p['scorelines'], 1)
        )
        st.markdown('<div class="yani-score-list">'+score_rows+'</div>', unsafe_allow_html=True)
        st.caption('Each scoreline is one possible result; probabilities do not sum to 100% because only the top five are shown.')
    elif selected_section == '🏥 Injuries & Lineups':
        show_injury_lineup_intelligence(match,home,away)
    elif selected_section == '🎯 Bet Tip':
        show_bet_tip(match, p, home, away)
    elif selected_section == '🛡️ Model & Risk':
        st.subheader('🛡️ Model risk & data quality')
        risk_class = 'high' if 'High' in p['risk'] else ('moderate' if 'Moderate' in p['risk'] else 'lower')
        st.markdown(f'<div class="yani-risk yani-risk-{risk_class}"><strong>{html.escape(p["risk"])}</strong>'
                    '<span>Uncertainty indicator based on sample size and probability concentration — not a measured error rate.</span></div>',
                    unsafe_allow_html=True)
        with st.expander('📋 Historical sample and model limitations', expanded=True):
            st.write(f"Historical sample: {p['home_sample']} {home} matches ({p['home_venue_sample']} at home), "
                     f"{p['away_sample']} {away} matches ({p['away_venue_sample']} away).")
            st.caption('Method: home/away goals scored and conceded; five-match smoothing toward an assumed 1.35 goals per team; independent Poisson goals. No injuries, odds, measured xG, strength-of-schedule adjustment, or calibration. The final 12+ goal probability bucket is aggregated.')
        render_experimental_recent_comparison(match, p)
        st.warning('These probabilities are experimental estimates, not proven accuracy or betting advice.')


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


def open_competition(league):
    st.session_state.fixture_league = league
    st.session_state.dashboard_tab = "Fixtures"


def show_fixture(match, allow_analysis=False):
    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    status = match.get("status") or "UNKNOWN"
    with st.container(border=True):
        left, right = st.columns([4, 1], vertical_alignment="center")
        with left:
            render_fixture_teams(match)
            st.caption(f'🕒 {local_kickoff(match.get("utcDate"))}')
        with right:
            st.caption(status.replace("_", " ").title())
            if allow_analysis and home.get("id") and away.get("id"):
                st.button("🔎 Analyse", key=f"analyse_{match.get('id')}",
                          use_container_width=True, on_click=open_match_analysis, args=(match,))
                if status in ('SCHEDULED', 'TIMED'):
                    st.button('🎯 Predict', key=f"predict_{match.get('id')}",
                              use_container_width=True, on_click=open_match_prediction, args=(match,))


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


/* Step 24: premium dark standings table and prediction match centre */
.yani-table-scroll {overflow-x:auto; border:1px solid #293d58; border-radius:16px; background:#111e31; margin:14px 0 9px;}
.yani-standings {width:100%;border-collapse:separate;border-spacing:0;min-width:660px;color:#eaf2ff;font-size:14px;}
.yani-standings th {background:#1c304b;color:#a8c4e8;text-align:center;font-size:12px;letter-spacing:.055em;text-transform:uppercase;padding:16px 11px;position:sticky;top:0;}
.yani-standings th:nth-child(2){text-align:left;}
.yani-standings td {padding:11px 12px;border-top:1px solid #26384e;text-align:center;background:#111e31;}
.yani-standings tr:nth-child(even) td {background:#17273c;}
.yani-standings tbody tr:hover td {background:#233b59;}
.yani-standings .yani-pos{font-weight:800;color:#e2e8f0;width:46px;}
.yani-standings .yani-rank-top .yani-pos{box-shadow:inset 4px 0 #38bdf8;color:#7dd3fc;}
.yani-standings .yani-rank-bottom .yani-pos{box-shadow:inset 4px 0 #fb7185;color:#fda4af;}
.yani-table-team{display:flex;align-items:center;gap:12px;min-width:160px;text-align:left;font-weight:650;}
.yani-table-team .yani-crest-img{object-fit:contain;flex-shrink:0;}
.yani-standings .yani-points{font-weight:900;color:#7dd3fc;font-size:16px;}
.yani-standings .yani-stat{font-variant-numeric:tabular-nums;}
.yani-table-legend{display:flex;flex-wrap:wrap;gap:12px;color:#9fb3cc;font-size:12px;margin:0 0 12px;}
.yani-table-legend span:first-child{color:#38bdf8;}.yani-table-legend span:nth-child(2){color:#fb7185;}
.yani-pred-hero{background:linear-gradient(130deg,#142943,#0c192b 65%,#132e48);border:1px solid #345274;border-radius:20px;padding:24px;margin:12px 0 18px;box-shadow:0 12px 35px #030a1550;}
.yani-pred-kicker{text-align:center;color:#90bce9;font-size:12px;letter-spacing:.08em;font-weight:750;text-transform:uppercase;}
.yani-pred-fixture{display:grid;grid-template-columns:minmax(0,1fr) 75px minmax(0,1fr);align-items:center;gap:10px;margin-top:18px;}
.yani-pred-club{display:flex;align-items:center;flex-direction:column;text-align:center;gap:7px;min-width:0;}
.yani-pred-club .yani-crest-img{object-fit:contain;max-width:100%;}
.yani-pred-club strong{color:#fff;font-size:clamp(14px,2vw,21px);line-height:1.25;overflow-wrap:anywhere;}
.yani-pred-club small{font-size:10px;letter-spacing:.16em;color:#8ca7c9;}
.yani-pred-vs{text-align:center;color:#6fb7ff;font-size:22px;font-weight:900;}
.yani-outcomes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0;}
.yani-outcome-card{background:#14243a;border:1px solid #304560;border-radius:16px;padding:19px 15px;min-width:0;}
.yani-outcome-card.is-leader{border-color:#38bdf8;background:linear-gradient(145deg,#173858,#14253b);box-shadow:inset 0 3px #38bdf8;}
.yani-outcome-label{color:#a6bcd7;font-size:11px;font-weight:750;letter-spacing:.09em;}
.yani-outcome-number{font-size:clamp(25px,3vw,40px);font-weight:850;color:#f8fbff;margin:8px 0 2px;font-variant-numeric:tabular-nums;}
.yani-outcome-club{color:#b5c9e0;font-size:12px;min-height:34px;overflow-wrap:anywhere;}
.yani-outcome-track{height:6px;background:#34465c;border-radius:9px;overflow:hidden;margin-top:13px;}
.yani-outcome-track span{display:block;height:100%;background:#4b9cff;border-radius:9px;}
.yani-outcome-card.is-leader .yani-outcome-track span{background:#39d5ba;}
.yani-goals-panel{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;background:#13243a;border:1px solid #2f4867;border-radius:16px;padding:18px;margin:12px 0;}
.yani-goals-panel>div{display:flex;flex-direction:column;gap:4px;text-align:center;min-width:0;}
.yani-goals-panel>div span{color:#b8cbe3;font-size:12px;overflow-wrap:anywhere;}
.yani-goals-panel>div strong{font-size:34px;color:#f8fbff;}
.yani-goals-separator{font-size:10px;font-weight:800;color:#7fa2c9;letter-spacing:.06em;text-align:center;max-width:95px;}
.yani-market-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0 22px;}
.yani-market{display:flex;flex-direction:column;gap:12px;padding:17px;background:#162840;border:1px solid #304765;border-radius:14px;min-height:110px;}
.yani-market span{font-size:12px;color:#b8cbe2;}.yani-market strong{font-size:29px;color:#f3f9ff;}
.yani-score-list{border:1px solid #304765;border-radius:14px;overflow:hidden;margin:12px 0 24px;}
.yani-score-row{display:grid;grid-template-columns:30px minmax(0,1fr) 75px minmax(0,1fr) 65px;align-items:center;gap:10px;padding:14px;background:#13233a;border-bottom:1px solid #2b405b;}
.yani-score-row:nth-child(even){background:#192c45;}.yani-score-row:last-child{border-bottom:0;}
.yani-score-rank{color:#83a9d3;font-size:12px;}.yani-score-club{font-size:12px;color:#c1d2e7;overflow-wrap:anywhere;}
.yani-score-row strong{text-align:center;color:#fff;font-size:18px;white-space:nowrap;}.yani-score-pct{text-align:right;color:#6bd9c2;font-weight:800;}
.yani-risk{display:flex;flex-direction:column;gap:8px;background:#17283d;border:1px solid #3b4d62;border-radius:14px;padding:16px;margin:10px 0 20px;}
.yani-risk strong{font-size:16px;}.yani-risk span{color:#b2c6de;font-size:12px;}.yani-risk-high strong{color:#fbbf75;}.yani-risk-moderate strong{color:#fde68a;}.yani-risk-lower strong{color:#6ee7b7;}
@media(max-width:700px){
 .block-container{padding-left:1rem;padding-right:1rem;padding-top:1rem;}
 .yani-pred-hero{padding:15px 10px;border-radius:14px;}.yani-pred-fixture{grid-template-columns:minmax(0,1fr) 40px minmax(0,1fr);gap:4px;}
 .yani-pred-club .yani-crest-img{width:45px!important;height:45px!important;}.yani-pred-vs{font-size:15px;}
 .yani-outcomes{gap:6px;}.yani-outcome-card{padding:12px 8px;border-radius:10px;}.yani-outcome-number{font-size:24px;}.yani-outcome-label{font-size:9px;}
 .yani-market-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;}.yani-market{padding:13px;min-height:95px;}.yani-market strong{font-size:24px;}
 .yani-score-row{grid-template-columns:18px minmax(0,1fr) 55px minmax(0,1fr) 48px;gap:5px;padding:11px 7px;}.yani-score-row strong{font-size:15px;}.yani-score-club{font-size:10px;}.yani-score-pct{font-size:12px;}
 .yani-goals-panel{padding:12px 8px;gap:6px;}.yani-goals-panel>div strong{font-size:27px;}.yani-goals-separator{font-size:9px;max-width:65px;}
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

    # Prefer the signed-in provider's display name; never show a fabricated username.
    username = str(username).strip()[:70] or "Football Fan"
    safe_username = html.escape(username)

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
    section[data-testid="stSidebar"] > div {background:linear-gradient(180deg,#041328 0%,#06254c 70%,#051a34 100%) !important;}
    section[data-testid="stSidebar"] .stButton button {text-align:left;justify-content:flex-start;border:1px solid #15385d;background:#071e3a;color:#e9f4ff;border-radius:12px;font-weight:650;min-height:42px;}
    section[data-testid="stSidebar"] .stButton button:hover {background:#0865cf;border-color:#24a9ff;color:white;}
    .yani-sidebar-brand {font-size:22px;font-weight:900;color:#fff;letter-spacing:-.7px;margin:12px 0 2px;}
    .yani-sidebar-brand span {color:#1caaff;}
    .yani-sidebar-tag {font-size:9px;letter-spacing:1.6px;color:#59c4ff;margin-bottom:20px;}
    .yani-sidebar-slogan {border:1px solid #1385e4;background:rgba(1,20,48,.82);border-radius:15px;padding:17px 12px;margin-top:20px;font-weight:900;color:white;text-align:center;line-height:1.7;}
    .yani-sidebar-slogan span {color:#1ab6ff;}
    .yani-hero {background-image:linear-gradient(90deg,#06162c 0%,rgba(5,23,47,.85) 31%,rgba(5,23,47,.08) 100%),url("data:image/webp;base64,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") !important;background-position:center !important;background-size:cover !important;min-height:190px;}
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
    /* STEP 16.3: sidebar spacing, no decorative text behind controls */
    section[data-testid="stSidebar"] .stVerticalBlock {gap:0.45rem !important;}
    section[data-testid="stSidebar"] .stButton {margin:0 !important;}
    section[data-testid="stSidebar"] .stButton button {min-height:39px !important;}
    .yani-sidebar-slogan {margin:12px 0 6px !important; padding:12px 8px !important; position:relative; z-index:1;}
    .yani-sidebar-ball {height:180px;margin:10px -8px 0;background:url("data:image/webp;base64,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") center bottom / contain no-repeat;pointer-events:none;}
    .yani-league img {filter:brightness(1.2);}
    .yani-league-action div[data-testid="stButton"] button {background:linear-gradient(140deg,#123b69,#0a213d);border:1px solid #2765a5;border-radius:11px;color:#e8f5ff;font-weight:700;font-size:11px;min-height:40px;}
    .yani-league-action div[data-testid="stButton"] button:hover {background:#0865cf;color:white;}
    .yani-team-crest {width:30px;height:30px;object-fit:contain;vertical-align:middle;margin:0 7px;}
    .yani-live-time {font-weight:750;color:#8cdbff;text-align:right;font-size:13px;letter-spacing:.3px;}
    .yani-hero {background-image:linear-gradient(90deg,#06162c 0%,rgba(5,23,47,.85) 31%,rgba(5,23,47,.08) 100%),url("data:image/webp;base64,UklGRiKqAABXRUJQVlA4IBaqAAAwzwKdASqqBeoAPpVCm0mlo6MoqlK8kRASiWZuQqeNcF6Y/PgHJZ1D94fV3Z9L/3/Op5D70Pkn4X9w/HX/a7wfmv+n5zPuX9l5w/+f+2/+k+HH9E/1fsE/0n/B/s57nP/T+7Hv7/xP/n9Uf9h/337me8z/0/3I97/+Y/Kr4Ff7//1+tX/eX//+43+6n//9o3/6/vb8P/9t/8/72e2v////d7gH//9vHnr+ZHpA+W/1P/K8U/Q788/jf3d/yHzU/v3/F5k/h/BP7k/yv8t7RP8zwn+cX/F6h35d/S/91/efYfjy9jqCv0//B+b1+p6Pfu/Rb4hn8/1D/8b6Nf/B56vs79tvgd/oP+O/8BsrFTHPi/3JEt387U2GSm91bc9IG3PKleEi7xgh7fK21uYCHWy61YWXwfHKhDJrgPZNFbnZDMd/GfjzcdUrp9KlTyuaRhgQTXU2kyRWaY9M/Vny3rxrV/TjIL5eBmHbdebzHBTfSqJY3TkTa8SJ1xtHQ+8n6Pl9/rAjZn+Na5NTpK20ZBePDRw6D0h2dDJZXaOvSlL7BmpRhYs24kbH0jeFTrGW03sCWV3Dik9na69tdj1AY1NFxy7h/+6jVDkodeQQP+1sPM903MIWUdUP/Z4Qk1nl5SLoj02LyqkBv7799yfski0pV/SGV+Kksx4fbqcn2YEgOMlMM/bhx6QN3vSafS0CWuqnt5Zv+Oi5+rK23KyT+nxXQOUkmMHG9yN4J8dJAZXcCtSYKwKmDU88s+ZsfbUorrQPoDzMYgQJ33MvQH4EzUYjpBY3G2q93dxlDSqI/C6KMRFKjGV35x8e+r//9VMxRZK6H6TCLImD8sU/6nQRv8lwnztFRWcrWKCFCCyk8oTINsjAlRx8ymSodP9UgD/KZAFZF6CL1eT0x7dWfUVC4XfX5TaO8G3IIE7H+qgGxA4njVRIT05qkQqttbGOXCL2ms4mQXP//5zIvaDNKt5bmi3o1M58nt7hnIu300KvuTlGMILEUthL0c8mTQaq8Mf+F2tqc2yknl0Qk/hXlRVTvRd6wvKJqLsrKBV4y9/aHeKbGcPYSCIIW7J+p2VMLzaAtZZvGx9Kqr7VWJ6LZZjuPT+p7WeBLcc2fWp6vQga5WCOW5P3IsSBZoAi2dExkswEWqf45S8zoUtJHP9D7adO6PhzNHl9mHRfpbBIz3PF7QXcec3XEEUnYkI6by1x5aRlfwAzwBP0PUoQZUr9cKAWCMDCjI/njYSLgNdOwP6c0f7QH/9e5mUKtXBTSZ/bDsUT3CiHIxlCo6uUk8RkiQXUoUfaaANWfRwOtkpG2LG1VsmQKo1mh/rJndPB0bo0Ye0ncctltrFAqypop/ib4cvVftcw9a4/mLySKKtaVl1D+/uUgM+lyNC55wJ9GxV8v1Q40fiylafanRbJlFkpjfcRJr9seuJ93PYSePs9iL75QBlVQqVTn8/Ghg6gJE8+Z+kyYCEB6YEJ1MzKpMy+zOkzjoFzr7s6mJpBFR20zyzfoAiJqz8tHt439H4/E5JzkwcmS9j6zIFWpcQrIN9LAjxUZ7+ISAoynvcAxrKeCPrv6o8jrF/l7E8UI1NKqAzddPo2xbtAiHOtl5D4o0Q1QE+AVOsAGki3CobJbDYx/U2LrSdj12JOOAmLhKKPgs77To/8wgx++GAOd//kQZYUD41iVduFL6rHdMjhQqqyK93Q398kB+K4HwgbUwhhAea9roBLcBda8P9CYAFjB132WCmFc17Z4vM1eneb9zgPx6U7h1ttXGyciPk2Lc1eFPygNdHm4s2DPUH5MH/7TZ9x5FTXhDvBc7XpQzefay3U77rMFuHbYGFpwY/6IMNi8BrskyO/FwpdiAWfp/D4IY84jwBMCy/pc/7uCf/LmaB0/vR83Z80y1FFRQZr0ftRdOhZklpuskqdud83dfQH2WFfmjwrh7k0M6je3HtqAdpC+7X14DPUjy007akDMK1XGt/9Fznm+SxmIGx8SGVZu7xEoHdPGb6GQw4EpyayLuglYLiPaxMQwGd4Zyoj2a6hJyHfR8D0+6gy7y3q9sjmDqM8hZgzlAE4YLn350KQiibYj4Ah1cF3J8vzDZGhW6snWjCI3NkxksGQklMvFq1gvjrROZ3LjdbTjy2z/hgeFjNDOBpnKIXqFXGtub/ekUi2TIVl730ocYUkiNkxLPTruFw/pjabbw57UPd8Ezp/DjtSzEMjlHVQo5PUnPhjRZn6BS/BGw0TF3B9konlA8fFGI6WNS9KZruoxOMkwQXlFuW9/UZY1sHVu7gyfsa9zY19lnheA2f//u0X9ZG6tYyNMjGX1IrtV8ziIMWJ+/8FjKRX2aCsrCbMlMDOqpgU6w7sVH1rM7p2y/9vrgPx0g05O+X/3JDgtARKaGQmvCLsYlvU+cJ9FE0Ie8yPVv2sKKR/nybkDMj+0aZePrSCN6HeX3QFEioj23Bw/BkequMgDtVYO+UZyUOru6aBIKC/7mkkRnpcUixkG95YsB5SggAdHi+hZ+A8TM7T27YdkCY2ZThdCfNzAkHKYCPftfJ10t6fS8ZftnpgHvPjWVw57w150FQLVP8cIV2DnNM7pXTjXkGkLz4Pr1a4eCtzPc9jFuQukVEeCT01mrHJjdFQxSQj/mkfgshqvhc1wNH71ii12jS5BLH0IwQjRhxfQfFKONzIjkIQNz5sNF+sAeIQh3R4xyEdTm921hZU5dDT3FzCBi8wmcrBCT+UfD+h0hr1P0ZoCK7osm4wr9w9D3N9D7TzHQjl34XRKsn8YgNL4l58jnHWbeqHdsM2WOttZryXu+zugSqV7UmYwLvHhf6RUEjxH+UFuf16lSW20FAil/7MRZ1rnyeYDSskTZ+qrgxzQ80vjlFWMou1u7BMzmeF1n1YRSwxy//0zC2vqhD6+dHjAwqe91qdFAlZxg/GjAfjvH3tFdWigMnn30AI38TIX9bnpeSdCwFK9C+igI7j2KiVYOBva2wBzbqNqQIaiPAjuwXl7LIu43Ea4qevyKOogqKwrjuuJpIkTfjCkjj8zVaJac/OlrjqgKDxhxT/2FsTklwgXTBeIg0pZ8n+oUHIJhzJQAec+meZiuBjHf6x281U/5WW5IpclKaKeTZofxD8VVTb5vxHSnXwvhg1cuBmb4pDi7XLCJFqHul1BJp4abEF8LRfg3wQ9DaedsKBGtwoCWNmb/hb4N82ihAM8rJOy70OXUjaCMxa7+SO7DBmZxSSSFIDYmiK8zjBOAHBzRemYQZ6acuF4Dn+Jxj0SDwR+qlI0vO3TtVKzLtJQz+gwt7Hy0g22CCoX1i03U/HWHYpAsrvTS3SO4QTI8rDYDFP1NHp+Z4yPNMxB45JNOdwL0xa5yVW45nUt85kGvD8IpmUdL7NMSaO6Gm2MKBN1nzUeYf0Tvz6+GxEJvQIyV11tkcT1gO1E2iPc81f08GZHe2TWOIHaECfgjf1G9DkCKPg7g27/Ue4W31Ul+9FZPV6gfgbrtxRDckMUV9OJbD9M4FdI7gMnroTN1zr7YTLVHb0GcdANXm8nLT+1MGo7IN8JoqvA9P7K8HM8wdoJjxbn88uSpU5ppMtxxidw7ERLuVGhWHcfMueFbhDnUwVyGSTFIkKqUPYS1PO4Do/4iQHIZldueYZTAa2V403bB6wjVJ13DvMOTLjVpgVnPl8OAOmvGlUbAyJIqhAFMveUUMn/b2H5lV38UpOg/NJLqvpyM8LiLoz1jLV6D7XWKE+smdr+cfLgkQBs9YYOloa0G270q98WU/RHTIKo3MfWF/olVYPq0epuXDMLFAYk4+TjI46uX37aBCOVqdrTJlgVnsPBy/mmLJrZCdCLDHP9vPjmSf3JITo8ldSKKSmz3Xve2fp/F7fhfkalhHFgQzsCeDip4B/d1FxcnLbveK0HvIysndyeiaTaXnlK+tNnE0PL4dBxeR9lAo3kNWde+mc8cUXoeDuZun9ZBuy538Nd5l3QnxnntI12JREHvxk2dpzlQtZS/Om0z4c97W8LUacNiZLXQigspqRA+rxmAWgmHBe9tLmZVmwNVJmjshY2FgBTpdwKG9F5eqI34ollNJZfmvBbGhjc8Wfta6EkVvQAdlma/zZNqnKsj3y7sl0t0VjYoKhJOC/JoTzYSUDB2gWXBIGg6+njRMIPSkMvLCEadcykbLjG7yKoIBnwHktDLGGY+N9hxO2NUYLpF1M3ve8xJ2LZXMDQnSiU2dPkCZihT64eV4oGhjYC5sur+A4euDWWojbE0Nrd53DXsZesLBqFXTY52HUmSe8Wtp/fUaZIJPiHVzHG+Jfja2Gmn8a9ZzOO9m5UHDZqWitCPKynQysYLB9iAQtBUu234nqVpuh+Dh73VQXoj/3R/+0OvBkbv6V0JT0vKPyJm6QV/h/HzV4XABfpNm7vlh36whEOpTN/zEsSEplPVkxOr391BJL9x4rBt4IXBit/91/ts/1Qn22YXLdtbkONV//iuBfbKbh80cut5xhPUE0eWTEJoCGuqj3TLTFagPU2gTCA5ylu1gYHRuJSKQ5067QcPRyierZrlQNdG76lIdi2iSMDK6bHH39P2a+IdmtWL66hYHTv3JMh1YncSoS3T2mamBn+ignTXCMPmyf6PQ809klb67Agt0EMTocaon2AiVmLHqxf+8deo8dK+eju6Aq21k/fhsLP3dPmWbvrBhlxfoFqK9QrAdYhFh6Rr96xUloZAUItdhdlaW3iwPVVmAEN3ffiXlD8kShFdlDpN91/YO1Wmyb3RBGWvqMJCIk8AafQMf32nXuw3t85KkqQ3ppzaj4zHMp82EbyJMHwkyeBw928prxF/ZhwhjUw3EwSqujH0rhH5FmARBbCeJkbp1Nzlx2TDV6wfGQ7MxyAH9D4C54CF4MToMxCXvdO+uUz/4POHxT0D+aDXHOyCD4/eDfVIAUmyWJiOiFMll6qH7faX9hExiusWwbDJaexCe+l8czMWxZsXVj8mqJ8GraqDds6lYXKqxqJ7A6Um2ibLO/4X8Rl3VM9kFjUOh8WbNj2sPLrUy9GrMA988EzZ+4tH53VaSonQZ9dg7lh0GPqp7Xy3nF3l0+DYkbg+6nDNoVyV56pt9dr2w6BxBwS7Q1iXWRDLMBerzxdUsfgtYYkDXgdBr9nTbWLiWdg4d7CG7aOnHsDgru4KdNI//fH/TSveoDSHGgdOZs+keqnk77VVgcLHpqRmkFNTnR5BHxSinuPPg6YgntmlPxAeHvkmgRzc0ebg+YjGF4YFtaN1Dba5xrsJ3842vONDEeAnpuNcl7lBnA8KnyZpvGEvO0iV/FXDXvBjokkqsB4DNEa8oqXurXimVq1iQt0avhVRycBYaTXxsPe0Pg1QLZKF3HnaCfUNpLbC1U7es1IBbnIlOZNpfQG9rpq3VX+rlZ1Z4Hn+WmC6TIkPT4vz+wW7IYrREOx0HoEOy2y/rl1a0sa5w4Ur7HVO+9gS3I3ljoV9zf5GR+EwfSt2TbXPMX6HCfYp70Zgdbzszv74FPjlS9+2Eb8brLojiMre2nWcamHn/+5zKil6sDPEnvnfaozYWOp+DFOQRi8CGKtG7J8p/dxfE5G0qjiJkuhmbtIpDfnB2lZrLRoUEv5jpAygDIxqdl9pnVqE3np5o536UTmS7AxdMB44rct6pj3Mhx2gByrQVBQoQua+jTfRyxVnBRrIg+9wpXNjaB2aNQv5mByYhPqGOe+EmZC0obTMoogQVnug8xjXdiquSIfWawCW9nGAhc2Rta1/K4r6vrE9ThJAqBJP1zYi9ccR3xslQ10ODFq5msrvCU4pBWgJkfGDrTRfnVQ4Ay6OkZBoZVWEJ5mnLhVia1NWAbAYDGrdH9TK9IQvNILpQ9V6hrEirs4WyC6Vxi1aV+cUi6ILeFPEXrM/tIlqQRnmctKna5qOoqyo71TTrkHUhlrzJ6wMmH+s5DnExRVYf1VtLcey9Cieo7XmDaIMbq9iykmVwzPMH3i1y+XzgGJmDjvccijkCFu3H+5fSFmbQu3bDvRc3iLEBn9fRzAUYDpIKeLljrx9qaybxK1aI3Q7M8aEwVJs9VQ2pTyJ47oeTRTMN9OsznER5Rog1YyCg96yCXNaMdENe+VFPhmFtgS6gGSN4ebHwZVgXazXChmTrHb/6TmOMpdeTfG1Xkwc0wZzlkEzoyNDsa69xh5iWUHeBGSmjJH3VvQqxiSxHbUkBXjzCtUo0hVU8+o5y7MrKcei1VV67BHLZCB82nATPy+bsIyx/Zrpa4mnu48iHl9ags077EMNAlT4K6uNxeLZi9kJRho6W82P3BXS8hzJIRZTuyQG7/6iBkPMYY/pmfZNddeWZ7bIVq/feHG68DNTaFEOkrLP+738iwRm7KIOC9/XhQLHce0Njyi6ndKSnLftiN5i5CsKrrT+0DYEUR4/uOk9+MwrnohfEhiQZBzqyVrwGheVo9+8LzVs7dBAzQ8OtQWEJu9XLRfbcaOw7ydow733htIjNCoxAmo/X8rOYrZIVNqDw68nmoN9zbeGLs+UP3RbUPngrj9oPRKbSHuJpMfXVfn0QZ9jQEQTHG9f84lsym30b7C9BKfFUns0fPUxMyBF6Ka91z0rzgbWiLNZnUDMho/s6GOpDniP9q1jdgOHBSVoJcxPizBm5sg/89xGEFm2naYW5gl4ygCiUTNuGBo21vBzI8H1O6vTInzfJPQfp65mOfF8Ai7aW4NPynar+rS5QdV8nyclI8IchTPQy4ZXQc2nCN4VgSHIVE9roxiC+lDsgLeOoy9j0J+xZXnA92CcALTkdL9t90cIrdQCg6S8p3rL6yDovNUxuI3vK3U0eyJUnGIuHfE5IKIBZ4L+8Dd55iE7RxzooDU2hbFv8Mm4ceao0CSau56gNaQcrzWZlbDOqvLOMY3EtSuctiVE8iicUgjKH7c6GGbXvNX6srRLKLOQiniDcTavKWlIKD4S65SJ4Liq3HPMfsToRRu8SZnWKU9M43sWrssYq598/qyypPTpH47Hawf5Dz9v02bW3u7ybcTvVtjJaCq/HWUrkjP7da45P+xPl9TZvBJwVQgjzdmNPBnaddCx9TpihRYq/FGXlybRXLvYcifbFC19QVKj1I1sIhPbGCH18QxhKZHAe8h6BWoXYsyO0qSdwk5fAk1cFA1w61Jgp7I5wdTdYzzqOscRiLa2G7ORnTU8vdr2Mot2DyKt5hNlenzh1xm/w9rUHdW3OsTyHQhhX9+XU1Z+s3OIC95Wur2fcC2Fui06875owvfZZ55QL1HZl6WeTRUkGGd1bnrzSJoou8wQHvDZNbNxq1TbYDdHlZhrKqB0aeM+9dD1hJrXrtNLKkpmtTIevvxXmfCniodpnSaUcvTjpHhMQ09dFDqQnleCS5X3JsaEMXNkpsG6422rB3rFp/PHGOpA6QkS6NUQq2IyNT4fYihS2tbhfn2aB369fF0z+N6kqjPM1Kjm/U3JqSsRAiGSZIAx9008hbvPuqRcNz97/JfcjgpLCFovX9fR2YPBUsMkF/3tikfZetJ89hCnynOhmnKR7rviBq+iwIBfu9XfjMTFs9axRwdBhvv8urLA3y7rEr+G0AmHO44vkBVbblA2Uz9JTxtIQr5unyxb3+OKFRoOMpBUX3mB77x0Jqv1UeaRa34osHzep90y8K1n3UYG2kfbrfExUsFxMzqC0TmyZplB6g+B8nZH1DAAD++aTlhMVLu8tO9wsXb8bjI/irlw1WIoP4tcbSOjOU5h7DTnlvxTVrN14QS+eAwxvL39Osee1YHWKZTAhyiL9O6USm1tHyj90Su/4MT+WJRxjjgqMGvubikdShM6cPLY0p3VshllVYJNibutRxT4hwGCxW5JyxeCmYc2WezzZkzROM3L2/8SmELbLrpwCzCvI4FoGVy76ByRjlrX2Dm7EClxRMxW8eC1KRd3IRjD5735/V1GmlFVBhZhwJJAT79R/QtI3BASiBO9fb0HTNt5HBifHP07P9Z6swOh/5l5WGDaDNmMPMG485kkq5a0BdZVjw3MlA2HkagWX0C4qJsbY6ZAewiLU7x45SNONtYVlqK2I0TgwY7O/CrISOKeCFC+y/kE9kDm4jNnqWVfRHn7t/WsjnMdUra7kums3PlnZOHCss+XdpV5ThrpU7rX3/Zoa4iRTq22eoAvYPUxdJlRqnODn8IyB0qo5KFFbjOwr25B9M/3Qd3hZlXzmW3rxuMRhL1iVeczp2VTlYET7J+sPXhu/l59UfWOoBY3YpzOxwtDWn4QENr+5RlB4tM1Tf8BOUBWjfjEQ0fgp+6PPT40tnxKkSyBhEE0WLe+swJqFQO0s11y1WbLquJC0Whxcn1RG+TWLlS+jRcHf9lKclmVGHHx+ASIZhHaHIpnRMC59tm+yyWjXIuTCVw4r8QRxLtObm+zmUGWojh2q3v/TRd9/R2mMERhhfMkOSJoX5dvguSyFO4Lr9pCi4E8KaYHpvL2l274gfZ7zyH0gVWpTibtXJqEP2LBF5CtZ581b7BJZzlzn1bZHOTyDq13TOXavT8KVG34bQM/U4xfOoHCPX+qlauLBfQKE+TZQMQTMAFM45wP93Jzw5XzaqJOkbynG0XidZsV2svzM0RARTbvdVYegUGREJGuJKOmKExEYlpFapb65I74GI/uKZX9CiyF3pkLW0bgkGyU4/kQ9u1sGdmWrKscQidkNAgwCVedEXILXFfhuuUsWoF4IgJzaYVLc9PSxtqr+z0/yg2AG9TVbKroPXF6i57Kt3k505fJwRH7O2C/TT1nkPaCKJWs6JsHwW2SVjqvb8KVrtm7w7GwILCMDWzPCmIK8CGTb0BfQjTfSJri5XAIKWKb83TK6+6x1xkrV4pcCT96iwlu2Yi91R5xOVxxkxIUy/Z3YyDZz8q5N5Afvu6Hx8UtPtd2wzikDSk8V3A3+udT6Snzde+IqdWcBMgQHcK+6RNveqWjK5n9dlZPKRrL5pkhqIKVNU1jTQ4/kc0ZRLge6hJSo+OS/gN1Ij5hOARdX4c+0lnXI8V1lKQR0WEOm89WGZB6lq28Nftduo2wfisfeDRb3uc0ceFZxltigZYKaXwhBP+im0EpE8ArJiPq5YB+O2FTlCdXtJ4tx1HTkJsc9oYyEKkVHknKH3ZR5FQo+AfCJ4TRQIe3Q+7bOJAgUvYZKdc5E6b8DLDEpNOOQmwboaDZ6ZxBWrujpySlpsf+KTl8rUXZ4uUboYKnVHyhVlV5k0OQijiCkL5HL4GHbRCcwiW854sh0Gi5bD05+g5VO7CSMAVBcK3tVLxMEjyiFvkb9UovZTYcJgo3Yxi/2AEHra6v+FBjlTUBbH3eSiaoJNk90sEqT6+1gK8xA79/bvAPaTHqtOdaIaO+6zvLb4eXE+Rq0VAAK7Url1OkJTYt/F+G86sdM/mbVDgALDz67CLr3+Q3nU7BAgBTAMhiwdwIDCQAH7E196xWsXvBaO4KqhOdslD/lxJpR8Pi57VaFmdRwJdvlw2KUPhYmTZuLiNhT5EMT5PUPCEEwr7GVXGOAYghLgwLXGb78Vloc7TfrrRzu3AP0h8nSaD5fUQ9gt7As2tadWdYPrJrxQnjgGcd+oh5rW11D9Hm8jS9Mb60cIlWT8Ij505POdS/beKD+tI+CuSWGSIS3jEIRBhJgIEwCmUOqWPwfIkN1XcICnTnb6SMuOze6KRdKZNtvUtk5RZEvWaL692fzy9lqLkJW7AeKrKovO3Go/S0Vt/anuEEhUqDTax1kMQ9O788viHOiWJSFOpZt3Ag/ivvJ5DCRY3KgsSSfhyXQiKritx50Jq2mjMqJeqBthH0Z1dbcglHF4YC9mWqqlt4K3Hc99e8yY7jVugRvsE+8LPAwKclxXNWLJJfnZzWVIQs54hpoogDl65NdSfKWBV/fFQVAXXy1bbJ6aPVhwk4kYDeBv9d7ye8l/2S1tWyL88plwtg1TA/mZnKgI1mpU86i5be3PDNNbycD4I48BYA+R7ANkF4aJFjCvpP08dUUrTFAw6CRP+PSTs1wfPysthhM5ktPzju7s6rttvyyICSvaTMohC3yXLwrfC83jBDy4ikGgt3GtZMGAKLYEawe848gu0KBRo1spxZmcAZHIeh/JGAwjYEXMbZolkXrbJnEQcYf0LcUzB2UrHmdMerZfoKTLWVGAZhRCRwJqrr/JhZUXplIJV6Gp6tFvbZkGmPUblD6Q/3pnRWgYSBS0G5thTp40XeYTq6Q8c0y+Fmunjl2OF0aFnCm8rlUh1MK3vYXXPzKSMalVih5nVWyPcmL1ZsQeGpoWGPE1MkTLJL3/a1DR2WjE/0ifstjWVLYsGcYRp7Q9AAFlnwBd1jxRy/ERGki3KwyAP1v9Vxwd6HdJlx1XEk8+x7ClWredxS+Ucl51Gl9aWVEaRo+HoDEsXEvMvDqqj8rHDadh8vVZ7ugzXsHIMdEKV8IAaiHB9rk43/2mmP0H3yPS5ozONrNlpDL1jGOJBjBAq8lNgaHGD9Ed6FaWW4fCDq/pHuv1ruaIYGHRHlrEJ6OS6g9eHvnmDC4cqiNKW4SgKHC84RkYJxhiWEhYLVgypLqc6phqHtYlQk0ZHHg6MBRBWQA5Ikx+X18q6ExBWppgQLFbEk4gJCf1VyG0ahKQP66qrEzxFBfxXS5Gy8nUEtsA4OQJrwYB+5UcMslNfXGNlOO50wtl8doqdluQOM2Q7q+KaS746uUEDfMekIT3c/052zubHtnr9ks4k4DxgRg23o7aS9XytNkAfyan8FnmfJ+k3OFx3EuIH9ZUKM2+qUlB6BdMgBRRZzmctZOwOk3ZtDsjOVmlJfR9G/By6MVovi0VPmlLUrAYLyBtgX+vHfloytLzCESMxVZLVe6yjVaDPzDcFWrC2YdZnZxwzmB5A7ANNszFo54l8KvhSwmbJ+XzATy5E7sMIKPVNTCseUeYedChNLjh+Hl+aYGfRwEGyjYAAVI9TPFAQPPlXAYV0U+Z1z5tUPQFS6E/RjZu+KHVqaw3WrxlO8eOkkPK+V28G/J2hbfJ8vHO1u9h2X1o7h/YQAM9j1tFhR7KN06/ap3tgUJuHNqZX9HIj2MYebzsqYQAaJOsg8BUil3PTTFZlidGiwIrnQ3W90JjUq5thAM+ZJliaFID78Lb+stEGuFrmL3AUhf0h3Ruyex6CaJzZkfyEkxzyignEBzuzqXOyuP8cIDyHKF9vQ2ykd/vQuBzRp3BfZv2f1pVaQgEBzIgVDgaH6oOkA62hLvukvoy/uTh1iddW9v90XZl7QJKX8t1uFcvDO7Z1qYh5mAXF7cY9qncmtKkSxin7kmvl9IUWC1lthzXhC98HZnq1uKV0Zi9g/v8LYcK5V0U6O+5DpQUO3AweNmjyow7CHmfCOvlB5bC6wUPkocuuaXlltYHZ7/8kAr4U0+zO4s3Nxk/G42JvIDn3Q5Vd28n6UVI6HrT2cL+EUYe65aEUdCxQAjgHqnIedKBHfvnUzH+4ikfOXoSZl3qannsXE7TMvuzjLJqCoWiX8TORZoYZaS8dngHWLoMfnwFSdJjK83XHqBzq17l9l0F4BfeQQAJNQ0GXsO+y3hwPgAwH1cA/p5hpBh7Q6szsNpxcz6murVkIqyO62IXcOQFyWh+DWbfUg2tPo22Pl7xKBS5AmSZQ86tCZgUDHSzyFOCQqkf+FD4Kya+OrwlVFrcs92jMVfXw1g+u205GAVV9t5u5p9fd+jSI7m7/hFQZdsH/YmxQRzVi6xTJ9UTP/KAN9O6LFLMGTGjbOPDSO5oPjLUD7vVzL5258nntakBR+8CaeHKn7GrJA9abvyOpSJEzUohizx17s3e5wQAopA/7lBwMw84phxA6MdAdVLno7S/ZzbEjp6AJ4gTfZNBdxTKkGrYK0rizuT9qgIKWTiEESJF32SNl2e5yn6/doyVhbsy9I1qk9Pl7Ce8H+qLYegxlnIPvBtZwCTPmxtqF7d4gGwgVWVHY8xFwcPTfmOmHwWzScJfJnJ9d/0e3VdxISMPhT+RBB1bbrWhIIBFJAPgtGtdvF23wY1Pxni2R080Qt6W1dsi2Bu93uF8HA3/e4tFyOy8thf4HD91c80MOhDJZvgW27UWJlJIeeZ14ezOiCubflndBIsOVAdPSwNBd3hob3KgiQPFifYQNtFvFW80KSUr1K33MPbre/Yg5rCHi/LW8NXwwesgcxOfsG5Bd0F+pWtl2T3kt1737LymjqxhF/AV7J+oIKoIdF6BuExoACfo/xPmgzgp82S+LH9JXhWrts/1o58i4pscpl2lGPBPOIvEbttAbcrCbjJZS1tgDDlD88vPdyAoQAF6xPUfP8yybh04fHh8CG8w5LXqoqpmlwQKXd7sybfIc5YNiy38xQzidRVsoYplf0wV1hSYm44xIFzgZhwJy4wE4hZNhToL7QyUcUkOxwBC2Vp9ZMg1AlSB4UkKBKmhCN9IZU4grNabM5zU0h998O3oPf5QD/3NaRMRX85pK613ZaWQhsriE7LPYtljgLQKqt38o5bAv5RKK+/39MBSd7GVIoTxWkN5W4rL5xLFNzC2OtLic/2E0cKzNuXfdm5GMaG/xY77gXw+GXDhron++xMXJ4angQpDvKmWougL5fNNs+kVN+IVr9LvB8ok0CvPKra+WvLRV6wls8IEHfzoB/cLzIUEJOBW8yNESHhjzl4IZCt9VhM2jHaS5i09aYhZc9Dgpuc5EblnfKFUvDyd8RShQggaKWqEEq0n+qt3t7RPNJ+4Rmg/Zjm/sbX1GX+43eDSlYoyENmQWyhNS+PhPbM8kVRul4XXc7wJQGV/lfYe4bniAUCyZv4wn4Bj/Ak+asGk9xKPzmMq3ULkXyb532P8WvYbPimlllLn9vuC7OT3mNChRloBaZgWvUYJ2gRL8kbjFlLJ6vJrtrz8ryHDUhQzLlC91BV2Xi2nK92GyedNZBNtpFpGocU0RzOPdXvzyA1LerzxMRBGKHfg9ExQuT+682zIMTc7x7DiyPRnLpbA5Au54gkTyBuMVRkyAhDvdVKzGyJlmlBqzWdmT+Jg1mg7ITTdg0xa0yIBevDO8ZFNX+YgNxbj/r49T/Ht2KUWCnTPKXRILjvA1tZPXWIRLAEWOfaH2s11V4OnZudJxmS6ISrZrisAcz+V96DU/719vGs9qGntDptXE9VGkIzovQ5sviboZBkOYORREEiY+gl8ZPShHX8WgOx0bc2Rw5U5eRH+L8jgOAgZI2e9nw2RFfF89++66LFMkXMEK+wn08Nn06ZWVMq6srR7ChSTdn/vVhKc6nzcAD86Njh+k0MjycGYBk+QiDBzotiscbFQC1Ojzy0WPAaoJAONsEDmIEi5tw7w5wYyQrU1m0YiobWB+S2s0+ssFvsjYDuHfjqp+EOydeepW3BoS4OpYVC2FvQf2E4fBqhqfSU3FJc2EzMiv14JCOqxDfmTl7bT5kk2VMp3Vp206467C6goJ/tKorK+Y4rH38hdYu0uXMJYlG12GKIGwfvezRq/+YSOcJoQpocCJ92tsUPKSnsVN1HRuCgwRHzR70oBqCZhbdbGsabvY4ZE53r63I4XWs4c3I9SeYvAv+9ubg+56uMcao/HexEUJN64Vt304pwn6FvoJku/Qa5l2PinRCKOp1m9E+qX6y+KbQTbUalu7py8LPexx8WGiv+FHQKxSfi5Y7npdtjNupIWa4h/FdLhZgD6D91cYC1eRz6ADd0O9D8EqY/xjjlHNCQoHCAMSr9RN1msmT8rDBK6Zyors9oRtOT/yNA/kHkfBSzo3McY6ZOfNRhUr4vQR7RaVEXN52IXfrqNRXA96kAm+fdUj3tq/MbdpHPqR2UjPewZly4RdXAQXlLBK3KI77YK/i6WWy49F92Jy92+piyxSYM467wTNmRNAlARCBWqMbeqdXamOLllpja7vL8rXvbVcALo2qIpv5QgrMk4AzvoZaQEBu/EGC5D+NBY53i9G5oz2huB0mm/dtXmW0Rj+0U9/FO50UNp0o+OZOfkEj1F2UWfQUBSyyW0JgV8y2anx+V9tk4oe9QZu0DY4wvpGugWJmz/YVF6U5KixXQBiLm4UemmjK7lBnvhujxOH5UqAR0cBZaBy77Uo0hYtsBUaUiKppNQXJBS9/RTy+EguxNSltHwm4vnb/rO7gF6CCu8ANfo/4vioT8ltZUnokNP1P6nBB726WG2b5SozGp5bQf5tx7q1Htd0iQnuhPEDGV3KgdRJLoP3o1x4RV8jvA4D7p27HfSCVu+QhrDBY1Nkk0US9ITy8Gwxo15lrsuix2UDTygXEisWt8WRagkFgT4+RfBHcBdoDTvp/6vBVMNS/tPNJkTxtAMUgy5sfZM04tSvlIGCSayu3QyVhD/dOs5acwUIfokYfQ007xavBQfJRjcyUl2LO75YO5eo1pJuqi4QSMe1EAEHsyHKR9w8YN3liyvgQAKCSaBZmUla1YKQ8NB5Bjv/llUK9leCVMWP/DNMSmp6iRQ/LyIJPxRKU2SAnrBFtFK16GJndUBcE8Uy6UK3nZisxA5P+vLwGjzovm5iwctZKxslxl18Sk1Y7vbHqCMKoO9AcJTox6j7FgA7Jy6muH73Joza0IwfuYRPXmzLYlUGbaalv39gtHg5xhTgbMiuXqMiUD0yvqBODMLFXJw6SygV23ghkJAwjdHuBvtNVqn36BoIdpHNVH+CV84sLHzM1YSAKJUUBgtrpiHeq5lN7NMKKyWvOm8qO7b1+Di8Wmz0UBH1YlYOXqULZO09ipAR7cG36Cd9OrQvNQfnvKqz/3t/ccHHpiR1TRnLUE2vc/JerDm7zPxLbnV9gp1Zz7947iY950xpW5MMwNvrSiZkNv30hvTKHrSul/V6ro0fj0flL9TwT9F+cJwGCSDZEEoPfNNeSQzjuKBBkgEQD1Y+A1H+J+WOjY3/7YOnJ/cJecJ3bODoPhqmYX0XvSUwN9aI/A6NPBc91JkG2yb1WtjXOkAVuxiVY14mf2IMB1cRAQ8WJQeB3mqSNu2iGhCjHmZ+5OzkqrvoExs0AP+9G19ToK3kUDcarCSziHD4o/OE1t0p0hWq6Qx7F3m/cdMVjvq6OiDNjm6/6cUT5dJuvb9mgHTGiA51I4QPwpGxAnI711ti1fx+6LXftdPBydJ8Hpob6wYOzOfwwhl/wJi5cc4dj5fre+CWfs9pQD5WJowv88B+Z0eP1m6chC3zA3B7fvJfnlpa1eENm6dZr/TJcVIeBHOnvGcI7BIXxDcjt5CSa6gn+RTHFZuKaQE5eyC/kqGqDOsIlAdlN6XWUokpMsGz0m1ha1mE+9i9TfDg55DN7U9t7880gGg5y0AxpSNZJkahrpd9uyVomhvNu/jcy+Rp8XuDTcwFvZUok3bluqiz1LeGkLJZXHCNg92adpX7rDqHfd6DyIFHF3qljTGOjU9XpQeqwwLcWUNhx0od6VGPI8OPDIhC15Lssc6fZNJwDpkWLLSGBqwk3WLErTTa0EYNgX9XGGeFMDlhB69QRBOwslqgz6SD4MOzJhFZEW2l1jG6CpjD+0kg0p9Q2QCLVH8EmPk2W4aqPepaAelcuZHr451BPd463PlYUfYnvPhQO/kiBOYZjaddPJaG1IoK/kBngiobSCPRH4Onh28VGvWf12VkmUNncfJYHAsNQ0NDnNm4tEXNYj7MbPOLWWNontQ6w4XNDTsAAwptMZ9U0xiEEfymSW9jedeV4WozMzjz8RtkAM9XefwefH2A+JC5EiNv0plNSh6Eg4bMbRsJZQA0lICgw99gyvS3i/c9mqg3W9HngsSpGvaHxnbQabHEEYe7p5ee7TU++yMv14W5NSJmyD0qt2gqRQhf/zLdskXaw2ON/ewYZa8syP/6H2JNW2TWDLgS/jYpZe9DYb9j59lMVHjSrc0GQnxcoyJkYOxP0qrNghebyKk/wx7qJanTDe0c307Mfqud5dVlBi51MTT4bYxRiP4sX62HPFQDoRWvyhr4sTluK60ltEUW/jMOOG0vrSD85PYaTw1fVjoycu5pxoTku4cytTK3K2UbaavvtxEbJCsXc0446igAReGKN6wXp30lMZF3/YZ9wECxei9M6kaDZREHqB3cty3rBhGNZA9D/rEe+aZRlX6m7FAteVUb1ivoXeYjSQ874y7CSKUmOCkUNairIRbxX81KrqV+hZFVVIQHk2i6uNc3nLSzNLbquabB/cfDnt6kUdqn01YuWiFgKpIAP9XqFjNAVaVx4SfQhegShs+X9+6mXL8mZlv/k8Mbqtz6XaG6NJT/x3SzzFtV+/xSjadvFTIuNXzbu7pP07A0eD1lMzxmm2pOht5gZjGfiborET5Hj0DbMLdoPVQ+qWCz2TTHQAdUKWhbDNMqde0R7SAjdNjDGxRsOAK4Os6C5g1lGLutjvYT8ibE1xagveH5iog2LZG7gqHYzUqTWThniG39LeeWFW2R6KLwKoVRfsbADwqk6gKVPCw2guET1KkY+nuPoZQZBjggiQ6hVoqwrilYzz4oAtRs/wi5BRj/Z2Z5a3QRVlCqgLn39+vj4ctQzCajhz+m/YEQ2kpAXKObGxqoXlkygL+odvN5T70iUcpOnvJrcw/53OPA8oWxuc8DQC2M5KA49zVrwKicUCeGM6Wcs6Ef53fG0td5ht0w/2EGhZ4xxJBryUXJDRTjIU+3R7ss7CefxV6wrkVf+psYGvUKa5+jjtEw19epYXkADunZQcWk++XyBs0TEr4J6C7S7U250hROdMiPW3ZZo/z5JP4bV5GE3/q9fTa2fJv8vICkLSICycK4WS6YLDWG7khDFwBelRUJy43K76tlAAKFPbPosbxL4AgeeD+p2RobvPFeI4B654GIXY/Q0mEiw0Z/YrnaX5i2JnzEmlSc6zlECZQsI2wAC7RFl9sLaMAtABmIGvnXxgjZ9e81b1uG33dlF+Vus7rJU/6z47FrH7XEe5cY5G7M/waQzmwiwC289DVDkJRxcQOLLG33PwB64Jg/AsY8E1LY1sD8Y77vXKAl/5CWs3ishllfhwdrpuwzz/r/LHBKBPsuLr86FEZEFtvjWRXVuYNtLOBAEUwSPH/1nonipg8Q/bBIKbElx/j66Nl2fYlIoaW05+Yy1mGxXKtexUuwqUGs+4T6m/nbECuxN/RXi8aSKR/KL6Wqn8hVAMnopXBNn5f701dkIXOvSjdDh6NBA3CUnLQAS8VABcsN1IqUDSEJvYMZ15+s09hPuJIANHRTj2QQoE0iA1oEE53Z9i/BQ2O8GGBD+3ZKZU0AKHQ5jPYD/aDNDlEdzzheTdp8uhWJXAauhQu0RaPw6yxscITUMU6D0BgNct03Gt3loKCIEf7iYJAfF6vgq6SJzYN/49MXELkLw/HDMD93PPOp3dR1yzlDz1WTu9afwzP9ehx7H5fkOr43vwEb2Vn9CACBq9KAU97Gs3gF30DgZJHSZJbu0q3IuOTk+5KNi7SG57B4CqJsTk71xm+7qJZYgk5iR/K380xzGFMRBqaZiV/huvMP7PDxu0jJTcc8L6AUUdktQ0vjZYS0aeOjakz7zgE815qasJLf1f3pqUF4EadbmCb1dHbVLVhq4LVswK5nD5Efd1rLM1b3aC0oj3T4w213a3DRzv5WiUlmZRUajaTEhQsaxY7hpJydIYjDP+EqrpUsxmqHPHngb24+3/oEpjSX5qqo/T8tOXXxjbe7dl3FiWI0WjycmZl6/ysrC05lpgS7a5uZTdUCu8bodIdxeknDP2mrVDX3BH9jJx1U3B6lcSsJeD/h63KwGO3Bn/ApBwyT30BXFUvr5kquvrEjZHEfdgZxp1FTLmCroNnL9QEj958lChpZhADtQYWtLpW26D2Fk4/wvDCPMaZQYtCP+duDz4qtSmVzu4jJkt01J0q9YTQtp/fIqwzkyCyB0tzpXsfH+A2UcXs3a0GjdAV0vMkAsa+PdYdxAOOuVNdXxVb/nK4Lh3QWef2cLO0Wy0sm/CgV7zpzGyBlw4mSaNsINs6BLbfEUQ1LwKaNinmIjfx8Pr98cokMwNRJj0L34LNQOI7ssdILN4dUywF0CLwzowm9dpT1hDvcW/vGwwb5wfVPpK/78xvic1COgfpjW78Cw0XzEJfTl4jB3hISVH8dmUPjM2nhurBeTFROKfQMNSvNq7T2cmtvpfn0H38bfjC6pXb2Nb9jDVAUBcsIFbxVM/SCT3zgiYmheivibwRml+RSC/i2RwlPMp0Jj1s9ENPqRm9JC1zWFki0anaN0nNRVrsoAHoVxyQtMNjyWYU+hkla2mb/RKL6nProQ2m1fkw9HW9L3VUDhKjR/jIeCM6wH6X6qrmFcx47wklRsyqs1pIcTVe8gOCbdXSdR7ebpqWp16wAxiERkg9pa0tm+FZdQsgKcyAZDxWU4uUsYxG14MPGWwWkSAf+GEjW3gkFMr6xCCPqixdPnEnc09gXHeRCC7IuK3zPOK5LcX06nGbG3kwtIlPlItMPDC9fjPfXH3KIr6JkZtIld5yrSmpMD7l051mY6hvB2uHzGsPw3yBw12ShJfgw6PDMLMP14pjQoItlOBDV0Ur754K/sRrvMWjnI7muNO7w/I40pe60TDg12SIUNGFroEIrSDIR093fHSUGQ2eiFTCyjaen7S9bzT/szk49mOAGGnyaeIAkuDMZ8m777pvHZgUfn8m3HBvA1e+rUxEYRalEUE3AavVa1ECDlvyJS4MiLf2urs9o4K8NcXhTuKyqx9wkC3K+pjFGzWS681GRQuJNV32jtvlonzST6zpBMQM21PNuQ53MHQXenEmujabDUo0otqo97SOGgCxMrh5r8oqtpUgEzThSNxq71bJK9+ru7MRckcWSt0q91hm1OEYh7NXTdZ3Mc3lYcRhMQ3hE2xq7ilOu+xdwulxyfWLC0Mjz9hTDSuSyu3l8Y528NPdR+qtgzlzBNGktdLYgTtxzBAi1ZN0/w+g1FVsSmxMfEs7q+CyQccv/KoMbKysgxRZk11k6Ngnx1XOtduBpKQcyEGIc2x4N1aLmBBRyLRFQUJxRPCw5K8lsWxveSPAWs9xPJf/QYR4eCwTV3pzzBAi6eKFqCjLohSDMu1VkslvFv+YUtcuLwPklfj9a14Q3YfnaxXLMdNwaJ3RDHn/JaOD5xb9/UT5MdneeOX7zMCtIVlU9d/v8+uwpxOGN242Qqq9O2OSY0DscK7aMxz2A4n5i/I6Bg/jiPg9HKJjXCl2UKMv5FR6S4WSGp0UZnSGyDTOUvOZmztFXjToBwsE9oK9uIXIJItsbJmhbG53SewVAx+8ocMmYsAZEtVMVK4UvYko5FcOFkf6eTiNxBw3GkaRVKyG5de5Wef+AjSrTnWOffhz97e0+b655/oLQhCxjU65s4wtsKbRm5mTBQrwuRuA+yTfCZOR9kcUpuHmf/Wf8eRTgbK9/N6cwVeu7hrK1iGPVY+Q5Zc+Sl4is1Zl601G8QVwWERLnAwtMpLxAFotPxH9CgHUTxdOmcqAzL4l1FdpxK4K5vFcOm8E6V0as7M/0M+z/076USSAVtsjQenRVmu/wxi5sjQqiL61GRwB0C2IVfVOOuOqbdzIA//SIeUeyEF8iE9Z8cT9GYjdtN8n0wChu2osXn6WrI461RRZv+EihxItTjYnErtK3nejcWU3i/db1AsizDwNIZDcolieUzrZQnK2wKw04wB9T2dnoKPF4mlJd24uqfqqxrcoUdRY7MqC4/d3lXnvTUTP/3QTg1yt5O0S3kzc1TN3xCR/G7UPDm9A+dkGMlvmwtXRBbjFvDDsxwrzwP453jD2xS060EVqFE2L2AVhCqh89GzJmTH7GPg2fbcEt+qdmt0quNgTDMokNT4gf0KBcLo4TXrmXgfFg7spkWvCyWc0HDEHUXSi25F/EvlUOwpSZBLyLkhCQkrpGgQeBCvYcUb4k6DC0ADHJ9gRD5DJIxHzGlBrbroJKy9hp31vtHtR3Fppa5YCiSO4hDo8JzZSm6VpqYnLyGTwpcBPxlX53UGroaOtcUbF0Bi1vBw6wAEJzbJmC7HByNKGdgp4Is2wmwg86SgapvfTCf+Y0T50mXcNHHZXYorHZdHmq5RqITphppbFL+or/ZwsBUdwt39tQs9JIr3YRmfRfnIBC1to/nbzlVkOgrfiEjy+dfISzpql3qVI2keYA6bnRjPM/w0vFgyOuzrgOPxoqbXhGE3JCrapU4v8djyATaYUlivjSwpLPhzlsZnrZz3VqHkU3UNLIkvKpZ97EiXHY0OuT8v2faFmZSwzo8/yPhcnsUfGaixxrYntqbW/Z5KgyN6V/ih0DoDKFpUwGKW1pod5/4f3TI4EucAo96KrIGROlLrsTjaC8ZupgU61IUkJOT6XyZ5PAadR4wT2K6RVpP49tYqB6N+rtwXxiINLSXSNNRQp1ulilSbhHAmGiE3HVgBZRncNHLqSSaEIzTm6RYPXuR9XFJLhV1GajXjNzdx3YXKfOHY47D1H53uJWxKlflMZoXcK0Sxr7jPsdWL30cz6sTf4xIAAAByQUIN9iNtsCMb5qtlF7YnJXK5LOYrlQZg5x2Gvd8q/UcCuyAVBzhJ4vwUk/om4djm1q7VNMYdEDFPmGU57gljP3FhewrdN8bLEynmzgJiJqlt4u2lP9IudM8w8XHQDjcSA5nvPPWssPmb+n6b50xPKy3AEZOO84VU760akZQROOwlOYu2kzmRM5lDLFkUolb9rj+yRqkHUs3a1hgox5wT2+E+ZCGgy4mNt59HjqDVy4z2l/tH2ZIK18+UvgqpIc9YpVzn6uBuIFo3LoqO8mPmMu6XqUqU4h909GsquC2/2LvdwpCes55b6loQ+kZaS9A0byDy/JBYqNGc4kDMgnVBRV3ovXBSJ5TRLSjLuYGbbKO/7M34ozNs8AEdIquTU7sePt+BsStZxgNTbsLOXmyVoEhsmFrKJJEptds841ndsO4tHrY/BA3XpzDvGhIhHVy2kjRRYw1XpKu/gXUGcGhh8UppSzw+wZdWeChS12M0FUT88hDVceQQACgP44wMMQZ9SXIvhhWxOwIWwNoFJRSZphCef0mKN1zYSm8PXVxQsGTV2fMVqeu2N1rNvvuSDlxYQ1sp6eVYCYuQktg2hl+DXKfP+9K+YLwYRPgzz1uJRX3TVucZjiJdO64DH2R3Ev39VQ86vI2gu9JhaRCLxkjep4hfz2T4O3y3M9IRIqparLDZCS3ZXf7kV2ePF5KTePzTFhGxHK/6OM0T7CR0+K7Eo2STJtsMcmsamADJYdwnUK9vJXCdQr2jKdRkU43YqsKrW/6lhivoHWYfeC4xefWNxOz/BRsKQrG5TcRBinpoZRoC3Gj0TVDdh2RHmRHA+Qx88Jzg2fHp8x5aPZUr3UXplRNVFgT3QLe1TesKZX6+hXgeC9uwL/SibYMQ7KN9m4AFyxMLLq4E0kczm39lexroQP1FZNr1jtvuK4frNc5KXNjY8Ns7lLdfOC3KWFJjD55rqNvcNnCDlFt88qmOPysaRM6Bo9iMFhmK6AtMC/Ml+qTpirTQtqX+1LjmXSkAng5j3KBBREKo5H5tTxRLfHMSWSp8Ss+3w9Bwy9oEm0CbIyGiJGnt3GmGf0/14DE8ihcmR7fJv4DafO1o0JEWczvL4gx/7TYo/jhL/F7T51IewQKvYzeJPk/B9OJ4INcFKbR+TEcIiHqqArBWnWMhpEBEjJl/exltw8S3Bfn2JHTDbeqxx8JgNswANJTPmpiLOwCSg75xrDNZehy94m41txSRVcNEC2JDBB0onnWPPOpQKRIT5u77l/drfTGCx2bbnuOOVy2Q93vdjV9iFO74NRsCgTFpnbS8/QPtre++2gDr2Q5c6f8Wz+MA1TXch2/g2lx4qO6PvwEJjIp5pF8w64xKwXhbx+PxhXb9FLybzF5HWbay+jE/zWo44ehfc9Pf7q5RfcmRDgfaDqF0R1SI0SYOtZ0/sO6qbB7AJJV+QZ2k8ImCjxRR82gxMSKv35WjyLRE2mYaKQmgxtew+Ey0pECm4AUYTbEjCWpKlHcYMelI86cYM4CO3+hfBOmsNEOrd/S+UgxWjGGUb9nqyXptK5RvyGAZa5ktdUJLTzUtVJEruzfYro+VxFMGpCEe5GrGFnmvqSyTxmhvlJ3v8448DF62DC36jFW6pZ4TOyb9L2Z4Ev6f0MuC7ItcPdgeEq4A215lWpMwnDAivGH6V5F24lzMu6gnhe/DWoHURY3KrrjYihA9GMu31UU/e6loo3NP/Pu65Wsoro5uUNGvxdG/z4XE2n+LafSOJtzdm3/j4fJFPHaXXumklk6inZO6sSdN0ALoNY7i4ZAZYEjWMxxf6AX3ECfFEHPUEJ6To/mSrrX5Uj+7yNCI2KWCissUgfr9sXvKDmqWSgwMPvyhd/LR5sdxYb+22nspuHB6Ffi+27OJGMLTkIJU5/uBWfdIXkG3VMl4ePft15TOX7QWFmSQFWxvb9XMk2NZENzFVhhXpRMRbCVEO2+NXEJp2AAsElXIOMYU06xiq5+/d2XnU0VDMtzQgfXmV0cDHJ3rgOu8OR72sPR9APps/xegxlhOqgps6hJW26Py+AcTLZFOz9Ssw/SEP6tdkMSSxZF52nNVcXqF9ROxyWxsVFhQ/xh+NDkKC6KseNDIxOsHCPnvGFe4FFtNAIkICrGbVfRbwm9Mme0pDtLBBFoC8dgEmmZ8kEPR9ZnC9xIz+dzfx1DQ37HCSoSxM3WbLyOEjjU3Mk6cFJ+3hJ+fUBaisydbmSyLfbF1LITra0HDA4affrrrwb5ltu1re9DmWOeJy8gfZeDnmkbs45Xf8S4poZkZ0VZk2JaP89AY498LwHmiudVvGY9OvtDPE0j7372qer8Jppd2VgcSLH+E/lVUf6srILqwCRv6AF0sm5ee3WoW3BvnuZWEqa/3JMx3ikPWqR5RyBT3KECD/s/wI0GvD8qSucF4IY8v2Cd/pAO6kbd2UTcSHeiJMHJUr2xpP3tSCJXWg/wVDHtE7XoklGdZqhNVjQ857h9aDuuRZ/+EUeM5LsyNJUewEagKUezu3a741KhCn0IAp/859lulMfhjKhzo4iJpH9wu2OY1jc+e5cki3ijfZpyeXxX4fRCtS2S8wgewMXXhuTDj+3/x7d/z+nN33XcRrm80f5M+gy0gf4oIBmH/sOUwU+NYyAv7CapH42hWK9LdFKOwf5tXMW5VcNuH2rIYn1EC3qVqm688OpZbdeXDBVsgqPQ1n0HUkv9CYP26ur+Fqww/cKdtb0IHQj8hzfQtPQHdNa2te66Cce4rOD2oDU29zmzQsc9DvJ4nLC4E+3cS/LW6udQ+U/FTJ0aAnEidBU/A7aze4MCkFuGqxLEWMKl4/rvbF1mo670qwnYsR8PR34l+27bDpGTCyuZA2av1ACJtrL7iyyhtVMsGGKaj+oyRAnohc5BRg0OI8BDAIT76ZiRVzOF279AbYBHq78LSFXqkNDYv6ZuVwK6FPKMLW0tvTyH2wcW8nDdToFJilqCs74c7ttRY6R4tRcjW9IQSlgCOfmvyaPAJhI0KmOqcYbXB4gJO+o4y34GFSbQbVDrA7/KF8127U0I1GpET6T/uTQbfXgyq099WF7LmNhwPBb3J37R7CPE2bflwvYwVVoQ/Cs3Q1VEVojDbDpYueZeQqOWUmYJaBtDKPE5izIxkXpVp7oNl7Jig26hrIhuhN3f4uEWN38iYV+PNM615r41zpNX/SJGL0WcLjxi3y5APo/4XXdQcH1ZHpu7INmt++K7UfTIXJ/qyyz4GkARuv2YOOE5VNmqw8tTYT0nJKYxH12kp+RX3x46USlS/0HnnzIy4eEiyjnRR0dYi8SjnW+z8dcoKqg9vJrXF84gIjqUDdMYR1kWqCfECLMRfWi+KAgNPfM0eaHrxvXh804Isx0hL413y/fFU4zN1dvq4iSOgsNMr6KgebCWWK9MCNRTTYvZSoLlqKdJAhLqWyV0mpEmlynAMDmSLk6HQYgrE4jd1KnU1xCFsaFGYzeu1jb8upL1BI6QnecYW4+pncDg8D7Ex1Y8bf2Lm1y17Z8xitPejtWnltQFtgEwrFrNZLt/u5G8Dc5Th68lfC8YQ0/XydTYzWwLN+J5+eGfCrpDkHHuOi40YPN25Z5quEyIQkPbZyH4Z6f1LGSXv509kkT2hA2loriGs2BDtlSYqs+vmAbRPyddkO4aszuKLRqBVxIQX/WPpY9Z2WtfL9CsDEcZRSTy+Zh8U4/W2CKr+YJNM+NTG57ChMVV+o0X7Kodu6Nqo+QJ6PyhRKopAWtp8L0sBMNYUjxihQFHuRwSUt8OJSM4HTMoRuRHmAWp7bFZLcTyMoTBO0KyKIPLW8s6UwH7HcqCpjkYE/u0JH+BXXj6MNBLjqWq+V9Kgyo3sfNzXZxD+hnUO3tPlwPrilXrmMDL535OuDnQl7F93TLpuu4d71bMf27XlnGE/x5fa71BZ9GzjWTeyBZDMtM3MqZQV43EQha7r4KP0URUtscvByEhELPpNKM7ReWp9nkaw4wGNNBq8ksElkX88pX1YHL5artmMwEAgYPdOfsJHLCi2aJgAsGrR+5paemTg5kXdy1HETtawWkCK0FE8wRME+h+YWwLtmPKe93XqAnVWVwvTjA9n/yDhJ/Gu8Gvjld/yjK5JUk2RmkV7YUplbrWzvz1OrSVWZ3pm4bj0JCn+RiP3ouCb0cdnMgPZJtmmCqpR454RVM+fxEIoCmTvJRsvO6jpD4iz9MovyA388WWGX7lWfV5V3p9FHEAEYy+C5MryrP6kQZalciaNe+qWL8zLSkVAhctaAx56i5S4VRt5splCqDxu/Qqvi+dtESKctGUwoareCQ/XeD5HAZzxOr88aKE8eE9prh+TIRDrVGoSL6cfmgB28tANgqY+tkssTDqg+qepxQiRBrfrFzxi8+O8L68qvnaiLh3DeZl+RIdZ3irCdoByNnoUzfQJoI7bxYDJp3hQ4w5BzCEvdb5Q4rUj7Ar6E90PY22Nyk887Ufrdl5MICAS/rUh/MEpgVsHHmIxY05oc93SDl/+7FF7JJu3+oeaVCD4NJGqZiQVzTSRUfq154Hq7L9zPyOFbn1dwf+2LaALm72VnSp75v/ZDvGeeHcgAUCAIi6C3BUuC4XwObZXQh/50Tmo1GtKuC4urXhy+ZMSRHEswUTlRbROt3i3LSu+YXzunH36B0S00AfeUlsyLpuOehk9E8tskD8fskDDerZKRKXDRzIP3nNT7rKApxKi1yGt57jWmHUw7y6oLgEosZAtwQcnF8yW/nwv51caMzg/n7v7MZAIRRGGyzjgbpOyJ1RrheItTBolt7oNzaPAWaJSo7zbu/hhblX73OUf27XMowpXV4J1hpbTNbCQ07LCtPApaBfnZE8rM4XpPvIIZsxN6+8ZOV68erzanfWj57l6Mf2ID+WsfTFuCi7ppbq7131H1KVGNqSX0A+A8keW/dM7nPWUWTvvFTy/jyG4HRoMEjLs9qAIuslbhvPU3q0AoBSGucDSq8Mb3WYxUjmCDv1j32oUbA9YYyIi2G49ew/UMprdAL5pNsbuBlk6FmthFFHhCYuRA9RvtDuVnArrrXIpfQswpKyDz8W4w6b/pAQ5kpIUUXD4axCOBLf1vPuMe5QT1F8iykWk2dNMmm4fefy1W6LYiKzoB0aRoyoBpBqjYbB5WWFRIhDkVNbkSfyUb38lY8rRX+te3AD4Wshrpuri+njoJX0iw5C1I2Dtsx9Aw6knD4rFSGRFW7YeuAwWfl7/eAMDMoD5mzRnNEa3oEWX5236+8NiomcBMgciSHTzpuDxoP1ff3NO1vnwct3LSKfFYhcnhU/07ALQjYewSLnwG5r5PxFY2iVtQczNJ3R+qB9EfjR9iQRIrI+5ZMqCOHqmquFq2aYlvtwe/OgOrwjeaLehnoAJvKIk/CINaoN2mPPYgoX8gioxgNHvLj0Arkbzc4ouD739ntozSsroaCI5O1sedov61ztI+HjuSTE5UaXoauQwsD88a1Yx74ubSTSr4zLAYqah3X0Ig2zBmskH4l5xx6NwtGg2HXfjXcwhQEeozO+b7kq6/BfeDr418NmG0UdQUo2r0dAX3BTrVza+e93LiL5+9A0zeUwS/xHnAlxZy0ixnJtMS3lQnNdWcxaa74OjuULhhnmxk21lI0TMGj075pveEhj7d3IBBmxJYsYZCfU8A1MVVkhGyq5mOBLzmx5Son2IHXGPwLQvToEgjBB2GERFcWyzn8Fslqb2/kyrSW08cJoQrtfvxefRuYR8Qj571n/D9QAy6zTIVIfbzeUU38T8LZCy82GAL3wgWbTX6njS3strxT0+bA5tmGpY0PRMjmOjsLaXqoihQyhyU1kT5m0vnURUzlT7e8ybU5QVEl5hY1btYqxnXfOCb79h0NNQkaT89YP3cqJ4+Sh+eCJfwuz8VuE9jcho0YSimL21ThXKn45uw11hiI0prKHTAQBF/DhwEq+W4COuNtXndd+VBbB3UaV6t7x+ko7kgsA0Yq7Q+WBT/1JcQ4NdhuAQEiblTjy+HvcfIVXyYolU3nD2NEg6XppNZekondzJN2/i7HMnktJ3Is/HA1QaXurYucF1+AgVefu8zTiIOHUIug1s0nWM2bHz9bxQ36Qkosp9N1LrlMvcVJQidbCpmXw2GQAhd5EMUY7y5LkemwcQ+Uaeak9GH9Rbv7l7pCc4NHmWJU+iasESQIVvspaAUTDU9HyzQXs55mwwdUWY3sDIo9vNp6t2HHATQTGA5dRR0ZyzoMmbYtWBr5WSFD4cYiIitzqBFqmxy3mFQOrcnMd11JMpBHGRnfTTZT7EMa1rC0onYZ99boMsL7lTdvRANqAC6snzhutpHldCjshE1lw9YSRDxftQjleGQKsilLQCQhl7plSNbJxSP4WsxdJm8/w6TIgv6sPcsmxtUAHwFBwjkQPSH6/TmZ34R4Fji4jB73kufNB9jO1Uh1mFfYfmmHcqOSk0JZaDkoVTuOF+4sceR3Iakk9sW+zfTOT2WUtoqu+TwJCbt+L+DboG68WwPsrAvq/9Q+/BSfisBMg5qOdS9NmaXHVPDhEZG3Ype457UDwwtgwqgVe6BpqOUtL2m3KaW+tLdAeqhMGrlGWJ2nWsOQ8NilaLuBM6C/DdRUu+V64FdcVuyCoUK/QWdxWeKaR9oWPWPgXNnjHlqlaoAMBcUs2hMTAgyxKQNqfxW3sSYcLUobfaATKrnjS7T7FRvAt881mNAWvezBABA4kX1NavVeHOD3bCv7EUIIXC6mc5eob677duIz+2iQZMQD/mjyhTdk950alulGCCtn3YDfYzHU5hJIU1VHNvkWCCIsaRgy44UBFpi9VbrDa5xGeKchCdG5O50dwsOUACc5X1i8hNzcSXxVicVmXDlc6WhHKm9hL4TRRmnAmmBfkTngimjbWa6DBp84W27Q0U6JpAn6dEq+7/30s/gKnLfHdaXh1D8EfL9ZV7VhgliE8Xpb8QT7Onxe1IVXZY3HtqueMNXAvMZWgjB22ScSgz2McMfBpAqkSlgezUD2KUzvEji1bo7vuXC7P4Q0GBql2LKK5vAFf79/BSlcQwQhg483uhPsgoN5jvymN/NQBug+1QGGFtDW1wJw7dj5Th2vI2TUQnP/1fmV8/KLYP7lNF3QMcj7CQaWmGZ6ikX0ib0I7pUes8uMWrNpOQgXGa7vRO+d/Wi67o2GVhR6hwltYuOXDjXOEmIy75dvtH7pQy8p8uVrZxWBQ+ozvRjdfaZSBlIzxvS9XLu59kQKykJqbuxXJukRbpQN/pgqz1y+ko5xyfxP1a0Wi6j+xELrBWP07LPi4e2bPt7okwE9Zi6+WIPthvepfNPqhgWd7gAlANQc4tCF5J49NxQHH7U9UjKariMzBcRv+fJFDdStV7DXVhZboVelzkl5XWk5L392OfapjSNy7xt7bgKdrKeGF4Xmxwmsq0/zV5TtXiehkHap7HdLfdCkpIPhl29E+EnqusIesbVgk/wmxBMDRnc609XgQY+eiTNt9RKinuj2Sq4RM9AgxnfJRQTRVwhevkHcy7e1j0YRNj47qQ6R320hd1ZgO95bX0mNoFVpN6tTLvBnjsRwVPA3omm1kl213fD1uOQh/G8H58sKO5qaCjIrBo4+/g7uth2TmKO0YPkby7a3VQQH4EL35dl60d4lFM4fDvw7csqQOV9n1XMGfRfHNiZ0cg/3ZZpYMcenkn1vlJz+iDCSrzs+hcVNcb21buIRKvfdfTK0Sr2eU6mjDhrEb+85dYLuH48HI0Z7T2xRI5eLsJtOmxyld4Vcx/Iyy3hK38804ykSttn03+7K0fWQ8Zz33oRma1dax4NcTESJMn16ntUoVxq7JfEZxb8VQVSZ7zw5JCbHR4TI7Ga9C4nhc0w0APa3NBkyN77cRBgSmUV1Afs7vRU+NPdafIfMc7BEYulPXU8KeSuS9AQEtZ7ng14VsRrAvxsRjQlJ4+GoyAMIaxqodfRL2eJlEw3H2YHvEWOTwnXgolL+3DlmpDuESIkOaXiiu5EqjVe+6URf+LeSt4Dp09l7IjbZ6wy1f2hxTj/84rLBQhQ5r2c9gXB0+252Q5B+rmGzTkau9Er9mA5LxKkuPz74fHFhtBrz78XUmEwsLW56+ZU3d3wuUaITkUVR6orpUVFjisdAoWvObe47CCdFe60hkdRViYJa9yaHUlBnHfW4vFTI704VACeXWBBw/SkO67OMnxzvyKzl5ozoyD87pFZleVsTrIQ5fml8LwQbGgW1lh6gSZ7kVudOY6U14FShsxe4gBtMbPBZkhzn5JWi0c8ANOLmsUz952cgyTpwjRzhyg5FnZVS6og5bB825jyVP4UIvJLeXHQ72af1AC6D4zpKDrk97Bvzl0cie3v0ug8brblUBsOvy8Yl4asTQ1Q8kaNSJ5vgwr3Gb+bj5fsrGF9CNP9KSWcdGsNc7G508dKRgHO40wMDLe2tyb5Lgq6J04GZspy3IaiiNw0+1l4thBlwW8sOvOAlJ1xVr4BHy0g6YCFebGuQCRG1FVjq11cB1FdkdV+h4s2DsbUS7BPle1p1E4DZhlgpugkfPXxPytjLXxL68cFtCeUso4dvYrMPahIED6Ln6LJoUOqIqyy/F+YzpVJNl7S0NfLbtd+7EBhX0aox8tz4jfySdXhOuOjcSs0GEEXGlRjiGypUhqDGkHR7xC72AzF2pjYh/DD3US9GAcVB67Jwi0xoRgCfP1WfxiVwSAy0SAmurj1Z5KfkPU5TiMBN/p8M2jaRT8M8SkAV2uyo1KAolIShYXw9LDqBifDfadAOl2mSF1Yb8Gb7abJggwK/I3I6wDbOXsOkFW+PcBRh+yB+Q/Qx+jB9sw5K8CqH4FtR5eUCXJTfTMb6ePECZAAiRgZseZQhtYAMD73aFpa2/46T2wUwclfMkQxoTmP0qq6C739jZmcVc+B9dQVb1zYgTbjqm4+HEArttWXQY9sBXUETNT6rc5/TUTmZDS+yBPOO9BzTDXGWxIumIV2hNRML+s2wah9arZvzSd9dTP7U2khGMSv80i5F8AZSg6Tw2LN9FlAx6JvT+mSZ3JkNvQvsJsisVmzPh297QLmnkrgpRMvozruI9DsE+Ez8ag6nBG2G7ndWN5wZUhjWHya87LPeXicIna7GnVAbCtvaT4ayG80XJye9Cem2amv696LlhGQr7H37lFzF1OJVw6LlNY5IkiIYT3QhpDA1LOpRA3/yzMprabyzNsZqfw8BJnNhgRdvzm/Hkw8I2h6nNjIKsRlEsx3YSn43yXlJdz6iz8Nyo07VUdbbuU9t5im4aGsASRfDXZ1z2ACuM14DwLAkKQmdf3gsZr9yyeyCT7/kdrYDtpxpjrT72TlHlHTrNUw4WplpTqc3ed0qi6bkG29mIXAzjL5kHa9kMwsQbPmKk7uKXYQIv/hjW/9z8HuLMtKk4Uv7ctVjbBOak50gyYB43iNkWSWUeXKdMdkyysAJyn9MNcw4NnFm3YEUMgrZ4RmgolGaRmXGpRc5vpmSIvJDxNcygpmXIOyPQ5OtULmUCdwgReNpWvqvDl2KM7hYvXaG0CZG7lzLq93XOJcfXjN1HEkw7Q6+ol4vBesrxVaKL5WamsdxZiDf4Nv4vSwq+7YuxPlJysJJIHpGPz4IVUC9sIlOIFfp2LwTBnuYEeJfmyTgyqA9LSjiE3JzLLmHchWl2oI4qR91P9uASzsnGSISaFTK6BzGi8BpCVzhwHH0TqeahwFKaAwDk1shNj/Q/9YKpavrf+CR/BsC1/EAxeYyUjY8UOsZQ9gSYs2Gp8qtrZ4fFV+yUO2H2H93VcQ0l1xIiGxpciw1UjdloSeccHxXu1XMnirRk3JdEU0UuoS9vDMCJyulKdoSR9JFo8bNmdk3OdDzZ5p31cuA9crvXVsQ8nWJ8Y4VSf6d6ViI4yN0x/T5ldPPz0ZyGLobNS1dsyFK4sgan7xPVbBvWe/Ldz5JGrZmWJdPGlRHBQXFENUrNMIo8/oTNjLw+eUl47NwCa3dDbwTjsQNy0ExvLwJ+96JngXOy3ysJEMESXYjCx0vtnTfy8aAcbWbgpY4OmdUgOXo9nt+0VKwdOC/dMoqTVNMUDyzlKE/NS7hJ2v59JpnoRqRpgs7Zv4iPRpXrVJydg2Z4Y8B6/1KRzDPNCzz9EBfgLLtwCXg7H3B1lX4thHg1xuek8gLwCsQupgCG9xcrIJPRh5iPztKvAUVEsF2yMCVzgT3rtZUn4MDbvFyglNaS9Hs7bK1qkain/eMHUrbJxxwOcSw4P2oSHgRvx2olRJF6PSDd4fpx+1070ZbwFXPV1gIl8XpApCsk+W5MfIPoBoHWDoEElmXxQ5XfhomZTepgbWtDYfVPJCpWzCOEQkn0nfqmgKeIBIPyegS3bNUPiCKve1P9/tsE3EWVwYk1H7+BD7XFqo/pQtOQRamEYUbQedNYt73olw445OPYcPLvaauAaj0pSci55HDIrcuxVzlyDlrk3vF1KUn1Jg74XoRR45Rk5O5fFzbn/RRJk7sGpsF5YLmBo/fdssaVWz1uGQ2OmJN6DgSU/u5BfERmQ6Qs4YZHlRM5NXf1kB5gTH9dZnwr4jwZCx01R9elUD/oaPWe05nuqIbLAJMqj51gO55AapeYYA75K5TKBH3GIY6r2295ttIlqGoXeBMCfQOje7icvZm+cfR2qwabEyPIWCEVnWVUAdkZ0pO2ObZ39VcosqHC17rylWQ4aSzo4Tzbb0405+k+eTBJj3lbXw/uMEPcKotzIl1opnJbyW/jVjtacCIvJXWWz6HPcLxD9tq1Z7tNI+l0x0pisy2AM3zKFUuFKrhWZGDqw75ucUwvUtZEWl3gBIyxrHfJlWhXc36kBBsXU0NEX1uRIhbyJUlHFZ0tfH2znSQN5w24tbTXIC0a5l6I1a+RaykQ7YKLzvWtvkiM4jAF4FRqWUPbxcekXLyN+/PM2VAnrzKs9bPVY09HcE+GV7is62hE7jFgf9KhxX8/Y3dk+7KIQu/vH6OoQEpSPra3+O3nsdsPfEwUxgC5AN0G7994NXaJMYpZZQ+Ts/kynrusBsOhqLYTjgqJ4P+uzuWfVb1tIkDGHkaqy0ifXK+/7+/Ejq65CzsDKhgMB8hOagJHsFc/sT2g4EpK4aVov/phZ7d6AKbAlC0vwvGHzHqo4jR8XiGb6uPc7BohEjs4HsZSxLPEk5uzaf3HX+FZV2jPYT7qcQuY+XwyDy4wpIbdcWq6nPBdSUdvKmvLRVq5oKpCphMVmf/zxN5nW3w0cKpXI/Na5VtMwtIowjkD1Emv98XziLFHsb0utLO5n7re2g4EDeL4fExoGhzVuy3ZE5Hnz5OB1DPN8Y6FH1gA8FVCF1TGmZUTt4Ke6YqqMliE4PeU8f/rRuesxlDsvQ6Zzgg5pZG91WT7drhBX+6lOsRZsbnBN5QB2Lt0+4h0OZx+39WIPd8ycdaUEHvTi7x2RCQ7kE4kVk2GrFl+3fCozi27qobcypKsiY8nPvEqoWMcDIN2i3qU7p9nRDw+tHm8mHTf2vbvrs7z6tVo9tYVAwIJH3vyLVhlrvlh/t6prN7dzoxWcwHvNeQ5gFN+z0oMjDIyEHNZqKy+oxSHWFT9V0jD0Gx7mbYZzb6a+JLuD+87uXXj8ik34R5qID10dvNAhDdu67JLcMNY6ANPEAXQS+4P2PVD+SP18nAXQNIZYe1BXQ6sK5HD1AMEKQqEfIgaXpEJ7Zy5apTmrkNkyap+snkuoMNE1BtE6I9BehUm3Eq/fkvN8IKfOmcNVfVENEWWw35ta8J9ZlTHFk8Yjj6moN2Ix8EOr6uW6y9zV2etWjvDnKf9pLXFlXL9Y6xxAivArPgrfWnTHzydXLcaUlPGWHxnuZNk2EYnhGITMe2vMgp3cr4TyxlDpy5TUtFsLiC++H96wjQ7XIH5yF1QOnMB9qqWssVM+IOaZv9ce2yPCyRCmkyVHrjjYK9tu4FaHljbye+72oOsDBd83mfkPcAJFQrQhwWtzDGBrbqy5cKuJxaa2iE2wXo3Se4sFCmihHkLaBvvOTjquLnqZcsaSUtn8ioEXvn/t0EnF6UZwFI/LMhUbBcBmHvQZPKTFbtJ9tEcLEvrrkNOX9qVzQYdYDIBwGUmEDewNllz0ADpHWp6iFvg1axtOck905KuY2lQMcKo6fI++7WLmllqxf3okW+jjUT7PK0hLmWDx9iC+oJKOmRhoDnh0jF81TY4n+8gS0cd4Gl6+SO9IbZiHsULnyXQo6et2CnjsS2/zI5aPEBmrbIz3TF2p40wFCflpHuXn/GI8Fo8p1NyvzjQ6GPszhjirh3CQpZ8MOYRAzNz2yrob3daY8zgLfmFV+CsyWPDeOzpcCYxb5Z44sDr901/godIkYpZPe+xNWx6F8Ma7FV9Vmla9J1lo617BSMngutv/ZnrHe0Rn0Q33BcS4XZjWx5wJmoQS8NF6w0IvlBGLA8zuTOYSeqyOMtZxZXp2kNfpGQMlM8TL+W2YBcz3Si1Sn5HFJJICwodmth3fe/yvZ3iwU9Ff79BiIjeepbA1urW9YX/VEivOhKcC0D953NHCX8CyQeen9RTWcVyuGxFfx/1wnlLKsxd87o5Vp+WAkGiwGc88cixvMx+m/Ix8JFnrPdiaX2y9ILoAzNzTylI0HzvTiDpVNgFvo1yxP6hGY6udSNuYBu5hurz08TC4Ay7geIiX1nqT1A2ZhFg7LbxGR/HJn7lkNecFqr7/c2ujjEGlAO4+Vo0bD5nIfVwcwKTaQW66vdaofOZYgHiMBsD8FDC/SwZSMne2FBLFnoRYfBKnxyix61sls4bNIW59KxHz7/x52cv2+V00pUfnDHrNKXZpK+dPnG1mR26891JVSc5j4rXY8hCMr5hM7UF/9j+wwzmyy26mJhnl5xDp7Dl3NqTSN1gazJbBUxwhf+GuTBkzUZGF8yxvmCYvSRxrRr1qK/Jl1PUn++vAfeXaUZehRAke9JW4JKR0vbXiOEtHgSlBfAJp1wlWdSozyLJhf3lbBmtn5i8XUC3T5/DMjIm+F68Ye+FDl0nuy+b6w0hLGD7VXVuNLoArpFk1iYDBjj1V+cTWn393hqVeARdcMsDT8A26b8fKl7sGOYKJQBczTdtTTRJXpjYh9TtfR/lG2vrvu+a+stu0Gh6cFkhShVlPhd23k/7cXZE/bbMI9I/D29+jrr1Ol3OGGq0wWyICe+kvCm2E+mWQ+Qz2+fzFnZuglM3ZD2RtgEAZeRcvmE+3jqWNely2dvTAbCD78Y3i34cEf37LRMzex73mzSxvoYxRgoLEfva1a7Qi039yP4XlppPZAxfJHpFSWjIpoZ1f03ljs1w8O4+qZ+fVsulWJVHcOMAXyo98HClZH0pa3QTq5Wf6J3PGLbjW5Kc1OQfxSUg3fKG/GZIJKxa2d+5LWSkm4n9tVTt4cd5ICYqKbGQma7NULbBXGxGEmCPHYQNhwsL4InRmKVy53nTtFX9KQkerxG+c7BtTVhHSO0USm4huLOHzEmiHOQE3MOOI/1xRHpdAqREqx6RP04e7aTtb9gNOTWQZL/gB6GI48RaSt0XzkZYne41pzaQ6nkrl/uGaNcxa44gYJov0iWyJuxJ9ytG9AhksIJ5vupXPA74SS4ixdC9OwGlwopyP/MVOyBtwqRqbxQ3F+/lwz6dUa54W0PGhh9X4ap4xPwCzZ07vGMsUHeMauSXE/t/23yUYhWRjlGdyYO0MXiSspwLiz7nTMwnH8kWkQZIQBBlqa3jgGsdaVPhqz6lUMuV4wX9vYLvYSccQrmga0ph0CerKedlqbB9KJxzeJBytxBnJmcl7CYXOyKWVoPnxLcNf+CZ9NoATC+CtoRUjFchZ4sNzAELeKNIOYUWPP3Z7I6kIPRwFjJnNZ1fXa86IkIuDtsuKD89lGRtk2LOm3NItaVkgqlDBcYr5YmyOZOM8nHzQhh3Q51bRvGVxJ39bVvYZYdYB+Tu7QcEDhayOPLz/+hHnR4A8uBuPZBxvDVFWZTJfOtxtIf8xTEp77vaaTrsW9De55fMRb79cjNPVwNsBMcPt6FHxANr4AGW0hmJKeOGn9/5O07/jNU+tVri/wc2ctNm225Jn9DsAAaZJFHm2ynY3c/ke4bOUiVPH3ZTeV5/kTHcZ715H/v+rhutSjv+0oIDXP+E0m7kUj/YNw62rp0S4PSgBcioPbIDe57HzG1x3yyul6e+ksfsrgn0G7HT9CRvRAlTPTj8oMSZ+HneYCjIEp16THhtfV6wBwXfCuN3g6WkSDYBpU72FleGGVQELxpkkVnZMvWHW0XS4GG+3Ua3gvgR52wB9WgU6w5jzUz1B8t8lbXndRImCQlmSOcDy+g6bU7hmQ1zICc+6RLAulcZLswr7RpY6jcChRHrlHAgN4WhWbh7lEtyDmg6gvD6i/84sjBIo9KWxowW3186g6Byh/U8PF2IEuIvk7S2hjvs8RJ0N/kYKIMzxk+3oJ2yGmYS0woBnR5G9KuxyMxLEOeiZAk5ZVRJxSrJ2T+gAP9NGpZRNhObSek45JAZ8WlLcSfKRKsNHre7eWKfAp2b2YraDYXIZ8d52OYdSzEbkXHN/RLQg//9noHt0Gpbp42N/VVfZ4OE3zP1j3eAQLud1N523qgM6P79GgoJgxJyf+ctDk1+5+tDJG7SQjH/Kze7otMqPvfZrNP2ha8AOIwxG40BAjvu/8/j2R0+nqPasc2mTpJVhMwnonYP1la6mnTJghXbi1HMP+FvgDBS4YmF5lVBjsb14Gd/ETehTTZINdJvhrWmIl3JS8Jl44pPHCW0rKXk8Imy/4XrVs+kKkXfHqgQT+IlJ3zJ/wILk9S3c1vJGQQEbnBz3/Sg5N691vc4JaFf/s+P8WB/MUwxHTpaHMPEWcDmSeN1NVgNyU24csEapq6tv+ZRYO44AuV33LXNNNVPotEHtqVRh/krptTbpN6rOObnflfi99LzcClN64S1bNPqi19HAzH6InXaySm+DFUn3JdD+f0+nRo6nS83lE73jw2iRHHWkQZRVBgytGknF3XtdxVk4oHn9rQE2cZ1wxQ/BCOzv3bB+lPM+v4CZYlj3cCmKDSBmeDs1yyIS49Wu3msH7paJAvehEK2nKIOQSD1liyvXso6v6ao9OWYgBffmf9sDcaLrPqe0MXvqEBNychGOxHDVzonovOIK9rk7k5G9/oGsrmmXS/09PbvmOJnMJhv6kETuTeotKVwh+idCvvXuFApSlUm5lx4Gvog7oVobaWV/Ngiywt26jRFZtxUxQz+B78MST09dwzURO1iTuhWtf92z+TbVByiX7p5Xh+mBGViVwkRO9dAMIfhM4iqQdXAXesanZgeDyO9RF5Ks8/1L+yd/eYftY3FBhmMZpA/ypzfePU5Sgh3/ZgRMFPARAcZzcNYPjhcGlv3seebUgjqgNpR4pKh4O7ZN/RTt/4m99gptI7avt3q/4q222gObcZHefpar5I/lnql/5TxzNtLdRaRoIciUJxSnzQh+iXfT09yLS0jvhij364/VooBDY5xVQ44jVir1lNeUOXstqF7Z9H9dBhgyEq9lUirIOOfph5+xMKotaTJqlqLx2flDRi7EVZiygZNisazv3H9kjIBU73JRvLIaYDpPF/FF671rEhxloy7aUmW4e7TzvvT9uv1/PDmk+Y1ybSeb+X8AFl+rgSUTMVi6PeEGPkQtk/iJQcs+ghWVZBAs8SmjuKykGIBZr8GnrMjOVej8xZVmiY3I0VHEVZSdZBFqSYoo+j0I2xfm3MqjDpSOlPQ906DstJ/COZkwgWLAxWoP8WD+y8w91fJkDscbD5rry7PVcJjPM0V3l9MribiIWVyL/lxTogVOclbSqQ/EQ7RnApbT0ZmgUgw+17lXNeoFvtdPATG6GhHqMQ9Khck8q8bWEC3D2EALZD9ZBcyxsQhL3mplJ1T1OpPnkJwe3PmcMHiBAmeJ0gFuxIO8bYXrYBV2hF55inbjSgjYzNT5l0tNYxYBE5tTffm9aru/8bGXeksZt7yj6nvvWJXsbm/iAEHr6PSmQJcQUiSQbBrGRFP1vheuKQX8PTAcQBkV+H+m/9JCPOwCErFr29HcDmqQlUJPIymO5a6Qh6rex3PdwDcHyOnWoLD5rPRP5/UNg+hDxhbd8NkBRQ3ByXYsAniDxlQ2DOrgI5XMW/uIcJzhgrpPc4d3qFWxoB1/KUNUV4RBONMFzQ3TPSG6V/4e0Wc9JvSVk3NqTTicJg+XJYXBYV2IDYPvCBkl2/8cwu3RSLnZEDsbgPd/V/KCpwG6bdWi8lJ6VgkhNk68QEhC9dZjlp7QW8ImlXeoXpIbLnYwgYmQsPXSIBIwPC5rwx+vI7gVzwU3x4WOta4i5BWi19gc2fjn+SJmNbprq+k4hIJrLkwtxL2P0Kan7koaR8TH0b7kcEqejNGIVbLQ1KSk7aNPxDbO1C0htVj9CzJipBeVdE50DcIzTQSlEaBJd1xtdqLfREY7wvj3wbRs9lfl7cTw67CtzyMrjymWgMRcB1BLWRu6sXGHVN8/atFsUfuHNi41SkKbxVaKXCt4OQmqB+2MEGjSeyTye7Z0lXmfd890pVqq+VBOCqafSdq0vXRhS45qpwryqlsqpaKwQ9bf/lw0uky6ffaeR+YzlW0iumwu8SZ5jwMz74mbdN+TgeL7z+JQDOQ8PNnZdbSnAK4TNlZMH/hFvuNelropdBu8in19Q1wi94Lyqdory78untoHzBUrb/IA08fgId9GOttlhAtRjMASLcqRoiHI7xJVYpsmtYUY9RurvczuDp6aQCbMTe78MXZmdAxQZgzm64sdVUU5e38w4T+x4ADtvDmMDQ1cgyiMqWV/4rgsXJWuj+bcZdvUYFZwZ3nOboLyL8Xsbndn9df0O7qTqLSMKssKyNalZ1niTexxAwg/6Z8MBQwMlRWT8MC6VMLEFcKs3mDTxKejRSL1S6fbitvgjjNUlNP2bTSdM5snSnlf8zdNynqSEud+DO2pe9xuZZDRqPyAfpZ16PgviMeSqWHAwVZUzd1DTcXzEFbv/MXsViEZ5txkF+cp22EfNJ8L81101DvAvuoK8JahGvoUdDwG4zN3IG+xgckbqrwVh0Jsfql1JOa6lMY+APINzoMoPGAbTbM3Sk1ybZ2bV+OkehuJydmo/cGmrcJ+qTrJgT03Y+Rz68qhiGfuW98QAO22yQX3uWtWdh6XY6HqNwMyHqRshJ03ZGAp89nIFCb9OqSueNVKGWZFtDl+AYRkgHA8W4y5/TYgBs3MtHKOYtXfBQXgF9TUpgk6MadXF/MiHRB/kfaurPSDLTJ1K1mwui3JaGM2x4531pGTnAsUbWF0qJjGlcB8Cgs6l1d1ID7YltBkHyK9DRzpByrZbznBMmytegoyAFS2zrQWZcUmtXnwEwOXGSaLPmTt6/nl5pJPRoy8kOgaZdq8QwrbvDRVsCWyjqlPz+61HcowpL8fTa+KvZHm22pkZ6xik/346UtfO90dfznvNyV7sVBmu78oP7wniJSIp4YHRK7yCo8tUPxKkcCU5dzLujDwnnrxafHWsjhBjF5+xBhGlQhUk7BLNfWNV9HreT5jaFdAeSwKA3wlk5g+bar11obUUtfJBD+CTGwajbnYJUntJpvKCURhFeyTzFn9ikdLFvmAerqvvtVYhyIduPS75hcJJG1YvelMYGI3HrfHnrgoN82IZJ0fc0jx9ZsmK1/4h6SEjkyfxMEIKr9RBg2LdDS9kCPMUCcwMLoqswO6M55nQstjP3wVy9FT9OKINiAkMZUnovitDoZtnuqJnyUBMZ3h7UdB/zhhNtRmjcIwd9bpbXoE1DIuR2km9UlD/WxGCQ/ItBkOolk1PglauHeSKXas1xBZlOlQdcrsuKdvGz5G+LHivuoci6Rph4Y2IGeSb3ESxL4L15lr5ezcud5bol8dLo+/Ae+BeZcyyrz8fId0sB5ndYwtgM/kul0/Oh8gx3R2g+KGSHTJ0MxE+L2xDCrGeHVpYF5nH7oHtiMYV1niX0jhwUxTz2Om6ZxWx9KYU98LqAe8xzx/wU6bTpVGZgzlhq693furIcCpNftiHEx36CWSWcgCIQG4LItXp1pzZvwP3iKGdIz86nGN4u9wjwuZYUgym5muAwjjP7/8rQQ7xXeuSerUCJpUBF53CnVmBzAq+oarKt9R9sfcJF98AxTOioi9NHzj4uONg/Mj7t+F1dYpcQxXSvoOSVxeWRCND2XdamU74yYKPllfmDNhYmGrFvrc/qwDCzDowFDnK62oQ7WA9LHcohkbAPY9ackHAV5ILaqarj4Hha75tfiG3ERNiFml+gZU4aIvVyjzNmTRS/fWjA0M1kmelH2AvZr1AzW3/U9YmJoKCuF+PKQ+EK7tz2UkMPFp7Wdd4ZU0h1KJqgLLiwBKbr0p/4w7YjylUmnoVCVb4V4f5oO5KAhT2SpOh8+I/J0si3zVFNNaGj13RdAlRSRuOjE3xZvIgoqpCgsM4/TqSfyJ4lgxTWlZ5P2zgo+zpeb3LGnPWWKb9sZECctdIaotkNfNVqcMmyLLvjpWhIwx5bE9N5vjcSfLqop/McK+XtmieDFjhFkW3cuR/K/XOc2RgZDZcNS0MYzZBpCn6YTsPQi2wmQ/sTihZ/HuPEoeCj10zfRwNRL5FaiUcBcdiYuBPsxHz1lkDzons6NGtoMgEt8UKSG05MACVirbz/7c7TrRGOgFtTk2K36Qb+G/kgCOb3GPbGyZ9BYi+oWFqNgjOX8vZz0c+VBKRlLG1zxO/WQeiZXG618y7JtmtigsLNyUrSJ0BvPiBKGaHbxLt2RGA7+FKYu+nJxrRfKCz0UlZnB8fDL0UvMTlH6gM3a5MhbYf37D+QuEf67K91UFtxCKi8xNj7lBqfnAfXHDkFbSF8sRs8+YJMf/wCuTEBmVDTGB/YQ2QXEqJ9nVK2lzR2vgPeAPq/KI9X/p+77wQzLsRv/jusPvoGHaHTy13GYE3VX5ZnJH1RviaH6mdb57zhCvSqSl3ZH5MjIHEjuyQ8t7Hb/lMOdxJ2u1zZYGHFxzSiUTIp5/ZMBdu2EgpimLoTsUq7US/sD5hfUhw0d3zPBmUb4omGRlffATi0hg5hnFLF2Gk4k0iWeBBRK79lEEx8yuXIInteHtFYu42n+dSTA+DMppRjXHixE8IFvCtH/xULG0/z6Dcjt2o6Gts44MS+yWHhLezLCBwlyFLWENgiarbMQ+Vd+dNrXxjDwR/N2JwvTEajDFTFYu064iAILMthNPTHYLulh0XzYpr/DS2SAZ48aDfQsEcaWpzTNcB+0RbOaqQMyMSPzWcKjzYDmHAaDu3MF6YPAXkQJFIb1Doz4Oiaw6nKW1B2qIX8s2PrUClj5j5hDA0Pvy84YtKh3v885+uyyH3tQbhx3CzPjy6+jaKbjk8YxK27xlN0aFrL1Tse6E/3eMDyBDcciSyV0LiMOavGQi0TAm08AARhaCnZx5H66zlj5R9FwV5fMspX0BdNkFWlT5b+dsm1vsZvxa3Vhp1Et9wpspKqy85zmJUx+G8oCJcaM6rDfOeyFy97iYRD8Ed8LJSyE9OFR1rpu1t8YxWf+qGtOEBJS6aTCbYtf8o+oO5YixKO+4dxXO0wwLP0twKnBHgxOSNbvdvBLywTeHj10IXe+6+LyGLstriNOwt28Z1djs/WSlVLDUZtkm49nMqqcrlb5P+aS9RzGdWsBaEpvdUA23hBQDJMOGwhA44Zr4ISLyk3CNjv4V21eWSJuDAUmCGw5AA9mxXoak40ddyL1J+Oz6aB2zeyfCskXmwUSSmsljAhDp29C9JhGb17jwpLxicTvDBqOcVYfk92D30NkMSEqLjpuNiBV/V8rRn4/PIN+Ned8jkvzplzrp6+VfTR0CmahxTKWggb6EOBN7UIyUDE5y/MNZX5MBpbBFGdMUexk4+hyI2lII+zIngdZLFFmPLkxuz28vfnDVV5VrgBLZQ32ugvgYfc8G7ZUxjBMQSAnTLm4wpQPuQDRy0ZfIpq+QBpcseXIHN66+ChIJBTRI+RxyJMtUDB2Em8QGs5oztYwK5l67EGWyQd0HR+bXrWw4nbIuT9V/f1dqAfEt+eWrt4rx8vTLDE+rAvc6ye4igOlokPqfUCM6l1viIpIAmxX0cJ9zpDttgwwsUMbq7tn1HLaqXjau5J9krhjczdi/51auTtODzA19i1NSFsA6WPQvS0G9S7FVNMeCXE/umYZM1H9HtqWZHVY1QaY8hhnVVK7SHcLLsxLAQmGSpCenv3jEQOp4RcIpx7saR002Ifloyrqqv7LRzOUmAKdJWLqnpO+sOZcj7+GuSjCnbox/hKUUHRRkqzM527x9ffR+2j/Q97z1cAIB1k0+3G2YJDGzJoPoS5Em089geG7wBdJQFs8G8nscLB/UOJJh2qn5jQ9OUGMlaDqk+xjMpN6fwzw822XmsWiWan6EzsarTt24RCzvAAuLzU7jcBPWWAWI+5X4ojXwOyFmIgsdOm2CN6cmn01nIF6tMqKjTclvsidW/xdy1Feaj9zUf7Wyk0JA7obMr6bUPwFs3EV2BNUKGF5uVuV/NYBhuwjcKKiS0ol3Ssl8GHzPHurtXb3AYg/vSlsZIXj7g/ffUk+opbmgMsP2zvRDrKTMheFLgx4w5jj0wAUkS8C/c6DkZP2PNzZTZ6L68TF+ITZcJb+guM8Uzy1T1D67cDwNi+14cJKE+a8wvVoyiAY6e3h3TJkGuYgAII14r645/Z7HUlE28MQuRh9nkkdPWaCqe3i9nl6auAnsfUXN3uwOAKTPOM2iTREKyj+IJJtNzjL8Aa93/CjOnsMh7xNoQeMLSMlHFWV1gCVcVXCQnI+4Osh0SpgL//7Fo3zMaOJMCRj1wv1ypPQbkZu+RbAJ5zDDj7Y5uZuq7J75qQlbspnMFjB+rVl5bOzH57UrXy+hU/mm1qIYEoWjNrknfSdck7MwoQmfouWNLCPRc5zlAz9c3mP0VyQ/Xh6dP8543n5124u60VgG4Db8RUtLtZMgsIgkRFUKP0/K/C9og7UjAhs/ok0bYU7UYn1Ez+/lsdfY8USasqgqrP6oNHxNLXHZKqOf0VLh86fPZMDrzy8SLCx6Asw3qEzGRcPYv8DiIF08JCiiv4Pxu3GSiTiOxq9/y6XHiqt0prXbG4ed3LFSCTfCSZUkpiw/niwPUCuXVrZrMtVddI1WRJStMg7KdqSVNVMQFDiuxJNeY3qmGX7+KgdKIKjcV7PUEj2tvbk/okX1rDnA6Ogs+Ri2KJK0lbkdMmsg1jXhgqal0Tfr4Y/Jo8iSgg0dFJzLYRu6C6WFUc70PKwlUXTMWpqZM4sceMWtsZgA/j/TdY5xB4x3Cvu6IqkFkiREJHMTddDv4LcKc1hwqVhj2NHOqA+PB8TKNrVd16+KuiooH+tJXBqkrE1Tc7gbpOOplmXki4cmO0Alg1qMNZgK4q8hW/XSxJSRSy82HlkXtdLixxiNjc1r9/mnu81Oe4kODyPNr3WL7X7a+x17n+P9VBgZGV2YS3ftXQ7jllv2ts92PEB42Tttk8WPhufDiqA3gTsV7RRyr4InQLVcwFpI/l75UvCOEnP2VephMwwOtI3cbyH2sQ3dDQuKiruSm1TG8FdrXzuQfVTYF1KSimBhrz4eW8xYOaiWDny8zSwsBCpYlUyzjuNp57/nvXDfqk4xU3dIQgK2jCST90QeUbBwPYBvjldgcYG6z9H4aC9gPSKPU5d+Pe13oQ5azXSrGMK0lrft1cNQadckTEyKsOzRfIiCP7kckvUGmceYxATW5cLde0KP8g9qst/f9mCDyNfpM1aEfh+aYyKASmWMeDbQS9lDteuudgWoqsUMxEvaSG88sS/5lyKFf5lGuPxnlJSvdvYavShmrfpirRmW39XlMSa6uaM5h7DV3G5D3gkLV5sRhQxct0kq4Iq6qj1K0pA+Q3yFLhUXwcL98IdmOZWaHRYPujhkUcCu0gTQQrBXcE9SLZ+1U0w7UQ33vxCxAKy/klOL/xLCb8q84xTSyGHWDZiQ5LPespVqw2tj31i5PIARLp/iUDiRjMjX4Dhfh0YgqByjooCi9HrJzKusCvHV2GE3qGjYlCvapsX4k6UnWKGerC78AghRIKvCi8TQxF6CdCNNDcQSN0xjBsFTciuzPYsj8zRpcJm79LctcqFQ903zLhnGeXlQ5OQjZ8ErZynPcLEAUlTCfZnL3zeByJGIZrTxAMONf6VD0qUEEvFZsVS3N25CstHhc81SZ+lXot0CnEUPVO/ABIDNBtk52vXwIOdJm71Y0eGRrZYcx0pOD0BJpkgDkXH/0MqpGHRbKKgZEIvUpg/eTceu23Zaxy15PcTrYXhjZFUVvVqmDtErX4hGcdfywJiDOVnkPNGMs85C7TQsmnYIVVzro7vnvJlvTkqdRm0eJkPB6WTObtJP8rS4Z7G8VyTgfhJ9zJxzpqfcLt3hbLKjXhdVcs9KvNbDv5isL24MSEGAfM2ierc4b//sLqTGiMG1+rBc8MrtXDozBHVjzLK4En+K4jqXsnTXvk1dhrpi6xOHt4aTZbxy1KjdZgQTBYExfkvDsaovFcCgH6LdOiOD42XAYDmbluIHsh/Ldhs0gWhdWg7Se+Ov3EZIgxgtoIbCSZG/oqcDMNlsHqiVBtkMBCK7/iHcGzT1pWoLoq+ygCtlvpy+ZXM0dEkH405DN97EoHfIHpuHpBvos2b2EMPgtIkqEurxcOTR6dv0QIR2mSXNL82LHGkRFYBwDbXImQesaTV8MpeEAwHzyAqpDGRP+9T2kX5lStGVKdUR0fCSytfqix0KqGUqhtCRglbKsA02gRiyWEPxXa9a7hsXI7AL+P2dRKkiYhISCt5bnFc/Ib826jrKP3Jn91IjQljz0eoOShaVi95dQ6OvsKYNUSEMx5jOBX6nlBgKJ71fLYz1y6yVycXvVBRAvbOJTMDyJzu68lglKCa+l6pSBXW9tdXNwuV6r8Qu5LLZumnAwojMuqVwip0323r+g3QZsNSRMY0fVi4Ln6nLEVQGKVDSKFS6sN/q6YyL53WphqUWDG+mhizWXarcM0QrxWgOC+n3nyQfwFS64wqqKvVKWu9ArsDwFGo7uwCjVhjKZxCWlVYhIWolGgsgxOz6DOZduD8GoPU0Ea0sDFLInccSn6j6rRGbKxaQWtf7nqtJDbrcFDFOI9DAGLoPqIJ5FZERRNEFj0Nd4Us5oDjrtdMMbRCefM/P27tiUICLXsBPfQ+kt/a40raD1Fzj1qIdrbdVpJnpBmajE0pZl3w3CU2vImObWAgwGxOl8N60CZGMizG9PVTx1s128gORSxp42ZUL8MYpwg6p4C9VKAzTmsojVu7Y1Yhg1w+7CjX2PRKhsRfHqSIwwa/6Y2N3k66HJl7L6/bD6Xf3V4PPwWN8lxhf6zwMkv2YI7HNl8VZZWnKw2tXbya+ti0HhNm5zFv1Yh9S7RgvQlzEkSkndcYpcaflQbHH3R7sCfgB+jnwzi+yIRh55HEmBdznKjerkzQVjY3JVQvFAC4F1bE+43mFAFFdqBrnudjT0aFBXN29XpO47RoNCIrsmdgXpnFu7QzPvPsUjNMxyqMeI306Ko3wkVntaK40RY357DK4ls/ep/2W9tx8ybeFiVK9QRsNmCaxm9dh8FZEobf6nHHJjyVWTtzhjXM03xgrv3HZAukOrp+yTYUEQNzzo2tJdwVSPYjuvd0JgvGASx4FjDoQlWW8eN+Wz3GwK1W3pms8GJlhitnlWP8mSPjzknh3aiYQhqITn2/AYHd2yjPySB1ubfcqaVWPKNmdYjOfV7Dl49beVDp9rBYz/iXFmOCMKw72d4PuEfW66n23bK1N85o2eCpQnKNj28tLAn6NZjJxaa79IKsMqmzZrJLmVGWWnZapf67m/YcxRIrjtyGwxVpaq8HDjyd33QHPag/eMPE5YauIMEJWLv7Ojyiq25VKnl7z0XvEDU3lgNZHSziE42jSrsHEtm7ajFpUN5mJ1jqaVGVEAJg8kVHs/IyQW3zd4Murgz2XWsA0Url90WEvyIrYlrNvv2Mi2CIXTLp8fAcpWRIXyDGn/gAwTDwF3zykqoE4RjAuBw67GyEANXRbbnHgppJ4PnV4ZLuRWQPHMMvUFzhoW7YOovkKUNbgPEbpdOdG770pTBHcD+nmBZys3FarBU0SUzmAceZGkcdYzazqBcGLc31SeYil093bCN8c2FWglWY8KXldjAT4148X5ZusWWd/znlLUwCGyZSPcqk/a0tU11lCuR41CRtkt+J7klzBlOljZo5hFLdzACVj5EPfo07fuuDFC9z1D8R0HOg7Vzd5bWKgPC3GbKN1vZ1DOwNXY9vQWYuwafvM/jkWPYmWMbyrjg1lgnherf61cryCYlVA+ci14ofy41AlqZR3UPmbtpFnvxFF7UsCQ8+ceHg52oCCOo193lYhMV0tFc15889JWl/UJgXCYpBcmCAgnR79WL/Xp+3+ZB1sho+sYTpD9SvZ4qpG8Qmbtn/6yEzGuJ5AuXHaKByAx7AF6efcJ0Twi4LvxtfFmGNZZkYWKajRX68ZXsQHEu/FlzIxJc3jKHbb9WpvBTOcdZRmkM6PrUgMfIc7HJk9e7BHKdi5l71RcZFoTwqS2I7QwEeiEZZrmEveC+LLTYw3/w8Z6k+FHUwx1hKxb/dFIqN7lMNYmuvvozPFj2GVY5XusW5ka3sJODaI5HiuMRYMsZffRJ1tDgbKg3ug4GqmlB+JnQQYHt9MyT0iBjWrILxYEKnDw4Ld5wTK+kTjVPsjg1gFlCbX3XaOcqJqmf0Bunl2C/+yj4DtbDlOH0lX/LPGURulKTAfJIqCOzWj0geB/yuPCWP4yD4viCIuVV6xWu/MeLZt7sJAWfiGt0ICdjRGbMv2gln8cSZBFae0M9mP/QcAq4CBfA5mFrn/WfOkAUxrFRdSd0uY8n6HwoEn7rtS5RqmW3MNqkwBamXjHEPrjec1CMfv5dNKBw+lqgVcVXDR2M6ZUmiOOh4S8O0KBVnRZ8iDnjoMrBWs5k62/fCnj9/IJZjEDpTxmPhX1llGQ/5to4mJV4M2VhOmEY0UCFTc+yk5UB1SzKf5nRJdD94kQNW3z0SyRGxATGhgzHCOLxevQI17O01N8P/8P1c4A5P0DWkurNgthXB8F5KdQmfNEJzBErvbXfZh+ZuogOpovcoSA8JIlPQrm1U4pIKr9wEi2bJMEzG8ZGwoNqYUhfnjyF2WYgMqNpEFcl/glBjWPikb0EEtgYTAGjUGiXCzBZpfpobF6GgoJ4Tnm3Q1/D8wrH2VMG3nvWfYmzi45uxVwis6YuL1l7Y/WbEhWPvTrMZ4iqC03vBpYcVNHXE/gy/rOolGst0nu6BWuVY+n4J6V6+DQIj5BgBAeWVlPfqUw83JLUKibG/6MhvFpvGRwzSgQWA849cZMwZlVJKhJyI15dLqP4SjeFkGJe5kvffQKq6mzzoa/DAUl93XLshuvhuYarzTDsZ/4GzGFQV6kR+5ZPz3prW+vcs3s8hhjsGITXFkbNw3Lphrri/7Waz68ZZ+FI3yBwzschTVym/uudVYcvOEhFmn/RPkHM+sEaksqXaiHcWa8eS7zKRKdbCQKh1qSFhdc2FX4+VhUoDyqNF06NRqiiZG6e3m+aUgenR+K+oo4rpHvXfJTePANsb96pkdMgez7zumPv7wxepGMoL6ZJ4oLL9Jlr56uRx+lr0IDgLw26GZ8bwpQrYtyu36eLD+HS8aKREVRFx4feDofTNOiJ6O3JdkP56WtI3wdoBtL8CkpT/msaSKwR8zpCpRvEvfhI0m/2/gKdR5uuhwmEyTpy/YwKYKY2tpECTrNK7xXcYF17qk8Y3xyejKnkYER0NODqGQXK5BVqEb8XBuFzw17/vTKevyCsB2GjkcFZEWBfFWFwibVGheF4rcQdymtmEPdoyNcC+v+UJQ+by3IGQmyevADUb+pe9jRwAh9kAjoMugaoQNBkHUIsFJ3HJ+c2M6Ydy8aPs8wOZInTj0J6HGsmyv43k3qB1uiEaKj0xdNVnjW/5BFPww8XNMOk8W6KwqKRaHt5uQ5xhDkbuO2Lc4Mn7+eaSF+/HNq40HtjJg50zYYtd+Pnt7719oLvgs5NifQjhhP10YvUGU4zjBLh1TJGfLkdvNagh+mhRsdSa/Df0y0oK8YZKqFOKoKAnf/bkSCaKc2TxLWfa1KmhEt75pKNS6E7NnfFXyh3e4vZskiIF//TRRvgE81XXw2C0tSfRhPESpt4YKPzCuV+BI3+IDKOjpezzJlLGgdyDYo0ZcuncyLI6Ybz6cbg+TfVInBoOg+xI+eq5FgN26E9jWgmZx7NHUN2YC/2Rbqm4SrpjOkpps+5Z6TeHccPENztGMUeAZoMwIIwtDZTxMfVCp5xQMlxyrWWVj6NqrZ9dQ+tDhVfVFo+uJpC2JDrEYMnMXbgHJEg3gjuDAcXhVOFAI04j4/lQddOMWcUsinHnHz62jl3M9IV76SMSlqGWLL/bo5NPrvkAFOLTPLVXoeQvXOFZvdzfGO0jR95VIM0U+FeCEtUGhpmnTEoKRj1Eva5DVGYICorWcyVjTjYWmBqRZaWAL+zilqWMOMUg4tyMJSMhDlVSzG3FE6i3ycsXHEmzuS5JkpyTDM0toHZJiC4XmYuNgnCjGk8PnVYe8DbDA9FLJ6fTRqMQtrOACNxFUMoRlKSidgYcZRv5XxVSKZIVxke6GL8e5azRUGx3jFV7jIuHbCfyS8UD2Zl69aEE8q8y5fiPfdw8eoQLacOEzYSTvaPsCxVFvh+/7iq6Fsc9F/QCAepf9e1RWcdZ+OVLBn06c/DD7Sb94ZSBaF7TxRGYmKYSdXNtpSXmJYauUFcMJf7a4Pxz0INcmr+MK1sHlX18A3K7Oy55EQkzHRf+k+HsmIwGPzkQl+WGM98Ymee3rqyOW1eqbyyuH+aZCefTLeIl4CAbTH+w+GGJn3SkbArF20rvnosYKaQhKV0ppTPY57LOSVbbe+10OuuPz6AK0h4NJF1qVZ5pic/0CQEsTZ6vcg7ICX9VfjNxHnnfXR6qwoSXTg84/pSNBIOFb1XJ9grDcaQjN7VihDjrARzPS88jMdemSQPo2LOEaLauiooQ5Tp1F+MXVSEnFzZx3uyOm1KN5sMynrRvfe4hn6YzR9w8qleSagrPzw0++tyoVM7ApikKNV8vTbVsLLjRT3T+Pc1W3wFRfSRNV0Ll6ad4PxJ2M6zpoxkdbSu/Q/3806XI94NHx2SHI5iSbeV9noNFKycePx1MkznKTJhxwfv9oDBzOGWLoR83aS+pEyHr+++0au78jgwslHbyFliMTFn4Kn963x+ssiBv08VKkNWS+/GY4OwEVHlFN2VbsFpp4AMNOr57hJ23M7KaDcbZpQ01iyB99UKsY3YdijJobyuOhF3jkuxjMiYX49R4fI76NTSpF+GoEM6Ym99P5cnpApc/28Z1S6QwYwEVC87Sxt1PNCDx/XViSXNscTMKI+XU+TraJtzmTW1JmUYdWNBYgiiKTHuTrQsvYiyKDVbA9X+X77cnU2neAxK/F083fym09dDt4SR/l/PsdgtosxEGTAytf2iXB7Hxk6fh9G4+VIyuZ60Mbbqle4q8RCJYGRK9RDMDFkdIZ2hLOS96qqPMw7ffra7HdQzbVbQX296i6S8pftfaZVEwPmh/6hQwHm2sn4gRP3npBKTN9FNwG3SsPjAHq+ge5sK2FGnDGk6BVRdrgpazrarOJxmYM7A5W3rF5GrmOFQ8DvW5bh6F3o22SfHy0fMIkRb+69F4ButWN5IqScr5OX02qqndn4klITXv+QXqIAQjG91ug8b3ppwsRxj5qx6Evz7oBHw/I9+7U5KnGRbeUyEYJQDriq5uQRmM7qbkE0OnVgj1aktQcswz1btFZR1IZz6F+UGwS2Bruv+Ts34ggaId6UxF4k37mtw4QXiAlKQYKgsjlTGGY7PDGw9E6TotHqwXnKxdqCi/6DrD0gRjNGXn0PqU/04eMiBjUOqchvWSqxsMP90WWtY0Hwk4VrXyU0x5k9IjVlpgLXnDt9swW/apYFY6cbJABt+eJPOijCDSwa2Pt0h4gzSSEyGaneRkoYrYTR8W7Oz82S7IH18vE7L88unCLNj0SZlt3ugfFeyBiH8kqn7zqxSR0GJ16Reyv7X3mwoWrhCCHvlS9EPtqKs3tQ4T00gIbg0IXhoVKbo00XdUbl2NqkP1KJb8HAMB4U6TZWKI7ePTLE0JwrungSn1OCmV4yeuJK9cGvaTTPJ9JNqy0IMMJx6l39UnlPgx6T9rv9LUSPqax118Jb+5yzZh729s5AmfKu256kg62yiXOMd3GKjzslZGBpH04TswW7KD7QMYFEoD/mYANkQa/nu/Dvo6C7Q8HogRCchVODp/xwEp3EasVPOIZTOn7IwuaGPOcnHfJhUZ67oSo1VQ0I+NwnxaEkcduI3W6IOyAvtSnBtg2zvzxkIdlAeZMrppn0jzzwyvYa5NCDoeYMnJgEBsCwXcjKHjQ7/o1FQjG7z8M7b8q2lSDIiInozddaQhXznGb0Xuus9RG0qvbk8gPWREfhKtRYe0M/aMnMOHaHMgjV5yh61jaK5rm3UkzVu0s+aTELB6z8Ky5Q/Yh0j1LYhoKpuqrEdQ+zJPmjugxy2y/d1TsDdHOTnjtofr2aeiBHppxl6vG6d/gqXH9+7TDhtkYVle2TZbIQ4fiXqsxJRiInnZ1i27rzwFl+Vc8hFFxQYykA7tK6PAIreR7+NFbget61bgNVZFMrqHVP+BAtUtQ1+AwFqZjNh0AxOqFBv8IN/1aMqlRIUvFRHDVKxmROXKel+8ky4Nby0vr+iOIMKcjrDM+JwwJIVzD1QOmQhH7ajyTF3eN8Xp/aB0d8svyeLwpnvjr2TM3dlzR3+QYWuo5zWc73G7Omhx0fdqwZAFtOsyyJfPbHgg+FC24VW5onZOMWvI4Jvyvtzu1Fa4/v0ZeKkcT6ShyJ2elHBSJCPByKCHknrbG+XsdO0+NXBxP30VqilSzhvquM62B1+P7w8P6b75ck2qlPMs4TdfAiBkJNAQXTkpBSm4wry9aI23D7QurkXa8fjcpZxrU0DD0N9BIsjMYyjLGnDrmq6ndjAUswU3oeIexwDhm1M+NWs6ii9TRKz/9XlxJt2lszXdY00/jUq16pynRUyWeZz6C/PaLgrfCloPN4hif0QU7dpPJefN7JwxNQDwpx7pgOQAdJJtWnWoQ/0g85mi7Qg3tgmKthnrDRNhy9DwJSV/+NlmX5LQknJMfUWUTGQRTligB5f44YMapKj27yMuPbeL3K4Ja4c9tkmxmfjCyDg/LkxNOPaZFaqmahVRjl2hRDq2zTtMFOrJ5UJXpIDlSHo8a1NsOUFurcCC8EldDLhMym9FGy7qeeAt+F4kWMwTfEfGqWhaWPDViQqhe18+wLZxWQplYwsOFQlsF1PwcqNzJltzFD04Eb1BtPLPqcP1LoWKb9rwq0w21fMyXI7p2ovuLxsg+hGGGZzfhQJuHnNB6fdH7Gj0AylaOG19HSleZGuSLm0OBGwHvCZNPHtKz/gA9G+CXbsRKfCTwZRcADASWowv3d3SHu5tG40pHJHYS8+xLLb1kAau3EBFs17XZQzETKfcOeRKXNmXHGNKNB8CZQ5kIKgo2jVTQ5DRbCYqoPQBF9c37oFFjDsfBKXYRi9D8u4oHjeonM7E0TqHKxw3V4KZVkbnyD9cb5g3890WObkN/1a9CkIacpjxCOrbyUSFvcty3HFj7HidCvHkapHjuuzQ7UECB1T6bqO6fy+tv0O12ysmrkXpdwfeCqzuUB6H31yznIiFJIeXp1tNLPI4VoJ0YNhCkMr6rOC+7ChB83EJg5tWLyHvFPLnAQZWinrRUcyPL3Ni4l4yAFHCPkOoTea2KALappx/No1aCrromQgZ2y/drhaHcTjOMMMdrVrJoDtFTfGNw9VFqm41tFKfVZDKxcgl57Vid+YVxUk+MICfrzFNOLMemjhDmHssX8PRyL6bbrgTMCo2DM2M8X/4a09/+13lu+1ylWhq/nlRkr8EQ9U5D6V8lXmoMTiGrLCr8D+WEy+frlC8stkB1o6IdWwJcKV1z7+DmdYU5KBVLI6vGdZoEajimGmyzo47dHr7W27e75jWsK0PainrxxuSjwgjffVg7OF84Kl45MG9dwTZldpSrfJ3A7drfW5P57fD/mnVfCH4KMp6i4NCsmx0yaP2Wf0+yh8qL3IgNXW4gQc4alwF+3fiDZIkZGVpUg46yuGrU+Q+fACfyTJ/ewtV0YJMBQGl+83V93sJZkvjvn9LL91lDqYeRS1AHbPbA22pcg5xBuDmthXfW2WDSPSpibZZ0vtgJXJbfl1JdtTggLv8KaMdcWPLFD2DAsfGGC07Loj7G0XA77iGWfW+DMLVfQkAotlbJ40DrDZxQ7fW8S3v0XdvREoR7EB9fbb3hWZWEOgCLy4iRMAAx6gl9CqDUi/puLLfyybB9ztl8/MwcHQhs+w4cEpNOgmfthmd3MaPMRNNFOGmHToq9sfHIVtgxfF7FwF5x5z8qOq5LkZmPK0LBHvugTJm+XgLxC9ZJ13LTXX2ryuttRWKgn5neX5zyiCdsc7PxfJnpjeEQgJ0KCjI0F1W5F7EP9FQjj9LAS3/3L9xmQkCKTCClsewtJOuGRQDI3pDCPsk7+bRxUe5cuLiFatCWTz1dMTKyK5s7/x1TFHZOLCLMYuGhi+bny9lUosh1W93WHx0sHdUJUccJlhD0F/rQzuKnOWziwy0RDfA/r39XxvyRIuaxEctS6hTpp909+ClUlFinn2gBSY8Oyy+Zyfi3tYhnKr6aXg2DDmaNSdRVJ/eiwxdyoJ17APlQ1U5e2LYDkfK2wvAOtvWIvq6L4P7+PinLVpBVJIJ0k2OsItRbXAZydqiiK1tAPoAEOcwxrcw0/ttHG3dvUyKQVccAokgbbZMBSYFOtqbbgleuVA1txXQC4ors5qNdhqZo57er+IgsLMPSOw2HziHwgrUKMfmsgEeab6ZGyt84bhxqDae+XI/2UMXBIEhe+BUi6QlQFRYwHbxPMzkig3yDpU37gcCHcthGLaQNGbu/tH1eAFm5g+9IFbYW0JriNTty+CG7XLbv5X6A/mQoIOhB0QsGgIiwJADMAYhWjgQ4wM2b/FviE/fRqrIU2ZrZPX1jstKECHbw3TEzQLi8IKOf1Edq8+2+oyq6AOnYXgYxfgikiXROpKa1R9xkwImfnm8gTvKH4E0v0AG2hSFAmrndOPKYlm4DS6A3VjU3NBYx7IYmDVGpuEvCHKbuQiS2TB2z1FJaKRunP+4gP4Tr7f0S+3lbXdiRBs+CTf0ijr8LONQrSCMrrGCnl77ZEH/RrahkoPTagZlW2BdA7xUSCIeCSRltaKTCXJmq6BhF82DiHYgRTTVRSQ0/Y4TTU68FYTvIEoFLGkoNfao4qluLnKGapkqGBHHtybtAPFXJXnq2Ao2VuVm6yIn1ixbYB1fq5uIPhrhOoaOcl4Y7hm0ryApCQ/UW3cXHz/X6NOl2Ljv/63kQ+zBGQeWZy8ztzW+nRNZIeV4n3wxzo2wupFd3UBGqsO6hYYD1jVHPuU58czUrHLWxPvfnKHEFJgDaNE5+NcdEmLdmTrckb8PoNM0a0RdBcs0hg2DUHG07etcv7bzQ+32xYIXyF9ZAkxlhwSYrmOn3VQGFnvXMe0/40wNoDPNo62eTC60WE2orikxzfznvVz9vc7Pss+a1G9wXfupe6rWjS2GQsBo6ofzA2zWAoxyW9GzBhIINK9jPW4su+M4f7ytNz154rlgPtNRCJEVB4GchsRij2UBXRlv47D/dSmDtLdvkQbqgW8wqEdihkKQT4aSPwXmhDlm2+jRGKuydttYJHKwYZlhsc9gYwmX2WOPKyRWnnNog2BPajxdQkA7H958MlZ4082CfaBZ2/lytsyEtUPydB7/90gRK4QwwxK7gWqbJk7DTv0Xdii/7RZKIDGf2EGqrnzgDkQ7XpxbbWupgd96fCGfkNwyJQt9Yxp7UmiDoz2N0Ubfdu28w2HwW7fKZrnkQ5Dr3uk1Fw8DLK1plY3zh2Rd7QZWz9f4xGaHul6V36OOhQKIBKsuNDwnQCymK8+ggp+KCuToEWiKDoPpA1/y9GytrCedP97gMS3NCPut02s0AE+1g0ckgqL98k/3Q3unNkZuMEO02VDcFobgMS3mJQqteZJSJVVyq2QUH6BwyCbc421uki7M5g067Out3HGu5bwcXoMaL5pwzCLcRJbfEcDpKgyCT2ZX6oCw1QAOLXqxR8Z4Z9jUZbYIpTk1ErHzro3kyPYhAEl3qmFDVsXQQaHKxdoERnVPhPivqN5JirgaRU35gG1TANFIwerSTrkMLaxAUVZ/0G6DomLe+T6Sbzy7F6wZZZoUqHl2ZFGpRGzr3NUahgMPny52ypJhAmh/vE6X/jCbMpMWh31RRZ5+fO4KNGDZ5FTq/Aa6bjzXA3du32pwpIWQwzSPwFpvzpZZJ+wvhan+UHO44+BZROCoUgv+nHAanUUydMUG2xRlN4TzaZu/XUiKGwH/bfcRbeQcbKmigVdjDlt/uQULRnhCmv6N0wJkE9PhyRynf57AGd5r8K9BIUlUAdNbVEt06HUgKiR4Wt0bRl8kGta4C/2GPL1t4G1OUM9RW0B3OWLhxmVbfKyJLzpldtXECVBaswKvPKRXR0udQ6tukgdPEU16zCrmJKKhVVZCAQSWB2VsPrLKsWtKl70O9AllApNJ/LtOEfnWqz10DDWZlNHZWouRvlSl6kcqoqS/7D5sZYtI8OSgXhJgH7jMOUbWvXXcWwLrP9RR4/v6oXTvyQ/OyScqG8K38Ce8WSfwPWIl6LoUmp5uCh1A6Qx0O7t5Nxsxo29kXLaHLLzYi64pwRP/wAFHIYNyBqpTpyHdyh+MQrlaHlhYEEPAmKFYAhLSz+TOsYOBJtU2n+CgftQqINTdNo8VOzkwwL4uUyDvBwpgPGx9qkfGg9jsRKevbWGvprSYcTjfnOj+PNsje6TUsKrYTezpG8Im2Oby21VEBS7oKWjihJp/51KBCckwH8uhCDA//Jyk5F952Gttg4morPh5YlaHy/FUORga92DjV+n6J7QXXvYfdZx2Z2wUR2eLL+whziZmUSwQYSnFBEMcvKkGWCNNt8Bti30SF+SU2jozre8rtxRkkUoVNqBAyaHBQKWO7kiHUaKywHNFNFMpR88CQLSs14mwijdBE17OqlPNowq1QDwjKv7CtdkLQOyKe3zHP68uQzhQmJaBA78HkqQeap4Uc4e2HK/53G7RHRQ0ccJ0F+EjMCQKlmC2nterw5G4qkaUWSPEcRIuc+xuvkeqoWDogQXqDx1OrJ+ia1QxlOnrXaW3zTaLy/LbWWQ6VCGWwOjtJXr7vBpnXyJ43Ki/xsvFfSl9o4BOQCHHt4DJwRAWt+ao8V+DHAGKzRS3oScf30DsO0izT9gsy4Y1kgi2FNqG95Zxy8faBNLOEhdfolPtsizkN/pDv8hINersIGbVMjEUxw4+2gMYZjFL9HZijZCi6m7EDWOKwaf9PTe/bIe8KFFpRltcb4zCFuuA68LhCO+tDUICUj1iRUyaBTslpmxiBGlfZWqV/EXsGaMd0ktqvw5TZ4JvupSw/bx0MBGbg2cDOTncA/3vmIA08dNg/Q+URb3JKTz8eQC63DuZfGcxdoVtD5e8ga8Eshy0qG+mzYDZPHNMG4o12ntiTUlkkLK9pffmp6YQxtStd+MDZm1WDE8FeykXZF6kWJVmPJKIWW1KgnmCiQUuKdXfjR4+jNrT1yyfw1eGXy3Cby05gBmEHmQc+4tpkwmoHcXuF16jtDXDjALGLQfAv2esGAl62tm++QG+aj4CAbiwN4FHgDH+4Aoxf8gsvGr3dMtYM78EZHDlwzBMLo8qvbPHaS0IMbXAC2BbrNxTTOcusq0XxsCxdNlqXSLTLjbPwTATVnvqL33HMwSO9FKLaIXRep5DRwMLUpX6uDbX0ACKuVyJ1r/FOF74nSYF4GyrR2dmCTBaOC3RE4jiF9460OMCkVmRjqSWtCDgQkL8sIGEPC0q98LFz0rIXCijCOlor/l/DOWj8rj+rR3Nt9v2RkOgc5LcMCPvYVFp6k5IuDDJ+rXWrmUyT233GnsY4LdU+mOw3w5snVqMDXv2C0RS+Rsk8aH8O6QPs5lMDs9w+HBIGApy2K/qz/lwYP0u75I4VYMjb3b7NCUWNDJtTmZMx+2hC0TvxaUoNIx/8ycHWoFiHvpVAUk+58OaSOkg5J6HU+/+iT52p/C79lCyWD0bMsCBL/f4o79cmoXYTA7jlAxW9UVTi0ejXOAhYo1BeSUc9VjvMgdcsEi8nV/GQxkh8Gc/8bPKYo7nxzxvV6+0rpot9Wqp732UXj1Y1bC/WIKxB63BaDZSVwBgYRIFptEE7ygcOawAARGCsAIt/awSBmXyoVy2eHO5PyBXVDvOoRIop24Th3GP1p6LkTcNY3RjeP0CAxzuwFhXXqAICmpwcxBRZQpl3gLG/RtBmAWKDBmWSSZ+uTe5hmlvjvdW9P5I0n+SqkG4/NC+oneRVSRttgAAlgIsG2dsao8WOJaEVrenT50kuymlpNma0Kta1bXFqBWYJeUUGKbwkB41JfmGkO+AqvMJW2UBorHFRB7dC/WGgfCTVzHHhOQVCPC4cGEnfHSGAJdv5stl7iifrHhpi3gues6zfA00oM9N8kQJtPEbQG7G5iYIyL2gh/2o28cxOodbFIPgry8Wi6rrND1k4Adq637HRkWjk/oXtKqjCwYBerwkGBaEBOMuRCjkutXGw6Qf4MOL85Md3XDIV2cXfUn1dAs/OsJDSAttMlU8xxmKGPxuRLuWHS0w3Oak03EMzaBngZU+2YIXOTGKDA7pmpd2i+z0SA8kwZeS33qrjoggtushFGrftxK7OEU5dgJMcRFLNKEpyRfux661UGjEVnIshznFU4xAq6hinUm9tgog06PYDP7VtmhlPGV+fPlwqqdJ0UL2LYViiQ7E26WJYEYiqrUQ84u6vZZbIj9V2nwr+ccIzxFjaxDTPrR1LbZtvB0TJasMR/cEfKzFB2XxdAOGmcWOzwpFdav3DC56FWKyYMjW+RCdJo1ycIh1NS4Hu60Arq8KyGVghsAmkFgfj6k8ePEMU7z252aFQHUsj7eV6Zr9GAhP1ibohSwewpvWS+Ar5hnGuXiLXBTf2/J+ju6N13dAB3dzNycv65DMDWRWJFLx55n0oGh6WPyg5DH5/BCiTCghzb5P8ZaJG/9rq+gJWO1wUMVsc79ZsduiPCn9LEkwZipu4e0vl9QxCguX84NgOwAtNagnmEyi7x+PCj8pwsiL0BZxW1jpdd0DY+sJCsi8Mm/94NHwcCpk99P8q306ixYRALr0Kr5LYIOVrjx5LI+xt+9VW47sibXr3+m1uH8eLTQoItCIkLksCPo98UPyLWNIsTLMiAi1fiuij1vOHS5vOLW0i6s4ongvkAlNvB9LfYjrsBP2n2YX/s9NaHTgahPIWSl8JoKpvIpwChu5vdPJANmlYcYqhAoP7uBxhawez/lhjInfudA66x3+6rHtZ8jEoDfFQyobT8PqrL9u52+15q7duLTHmv/xax1NI/7HjNPVez43uOPAoC2KqunadTYOGrJk7oOa4GqOKEvVrMlN2GVHadk6oQiCdkpa5km9GVGum+MHBtAFfUZZ8fTrDGKkq6woH0JMdBw9T7FPU2dRlvAIdCf11IZLuA5ldjiUMosd6xOyPX19JKCzxdX9Wlo9AOy9qSAdBD1QEteIOEZo5PHD3J4B2LKTCUf+Qscc2YqeMd13cp3kkYEB77kNz5xAuFBHHAVGBCBtBDv0yRzD9el1nLOeLo9SdFNdkuoKDTqY7xxY3U9JuLZSsmbBiP6cp9Ikoeia9mCn3lceQGGvObdMQSV3jl0YbQn1GZoCytMdI1zQtRHaTje9zZzvQBCx39AE28Aop7hDbOKZekLpdEd7KSV4riU8C2+j8AlyvzI1NHqWkfbBpQN+n9chCzWJW69pdBZ/b4UsMpse8fRH1RkSsVqXSWsGmiRgeBjb8kWkK8ShutG6yyBXCfPSl6G0WDmk82/Q5Ap4RP5O3UoXFKqOSOupfUAUBh5aUsA106ZvPyDNORTz7SCID4LgGJIx8uCuIIDWAoCvam5T3swxg82dQPMn7JkooWfxXVSoqnf1sXMFlDwxRWu0gomdi1NiA+fOreceAIYk0LFMjGUrH3vnli0EUs3S0+tj8T3mk/N0XAQGHlsHZFvrCoxwWTOED8rtwdB5zeBhRkHJ+gF5q/XdzsNS4WBo+sTB7ej1HE34mPQazdCVuo0JSwIkWbWoVyCAWA8T4zxY6XbA01UT0madX0iTpKqonJ4SKXmU7DVVMcQHFe9H8LNCVJAo9Hj3pSN+NJdracTJ+VgBtTzOnInERhE9BZ5Xk/TWlc/mA5Y9MeP+/VjmR51ECeqpiJumBgYR+b7xYuMPJQR+4qLfqf+fAnsgLJiLFViRI4KDk1huEFoRxeY30lhaM/yu+tf2n0h9qb4r7QXs86vS6tmeEwuMchDN4Ys7CeltXo0zCj446t3+6LICc7k5rMoWrPsWZOA/1lc17vQxqyImWOe2GiXBnISwwAFmiuRWEj48W5MuNBqyhZuLa5SAaGNWgjDbP4Io+bd7K3zHRA/EIrQUL8S4GXcDluMog1ISVmVaxoiAPbzZDM87I8kbKXMYpNNC1ki8o3ZdYggbB9+cuucGi0bU3+6LG8xUpB4DXLV/qoU1/uYWmsh2aFznjaQj/rHpGUFyM3TPXOnYafTx97jBaCUN92A0n2e+wWJfOyIT8RKmRN+FPJ13SiN9XGkvGvK2KuXmRdw9OhjyC3j5p1HGe/1/jyifiEWFZ8tuUg2pfcB5qk7hF7flTJjLIUqPSsXPjgCddQw0oDP2AAMJRRijw/wFCBM6zFHTcc4idPqESJ8yqRKU0Gf+oBITRjeFCWGRdxkBKIFGYfu2ZqFR6AEty5i6jo1KuFN10PJKUnBg5unhd3Kjfl/Agmn9NK7GmPoC7vzTsnvNhOIcr9MUZ+tb0VJ45GBQUWrzirzqQ1/lD8a9sa19Nzt59RWBJCFafvBn1xdxB9zV9amUZINg1GS2L6H/yBHm8Cm8xfryrm8zvFKC5ZnPhhEwVaxT44r1sitGoIKkUNgLXsaVv2HlwnJcu+nCuBUkYXZ4kbqi5ROq4baDC6AMEV0CCsdT+6Kxn43e8PLOMq186c388jgXlja8sRFJxQSqEUhfvp1sNWEGU9AZVLpyAA8hjvGdWQXloZqaW1DTjsGATSsGwDrC6jHxhfDH2uRaUHyoQUYXm4NDgNug1UjrKEEuF6P4QPPNAJOXdbM2bqdAUz13mQuUdL8TJJ1JmsBN33N5QldyPQ1FBu/2lGL15dzgj7cbEH+IrEC21SDCO0hQ4Xv8KoXksfatT8fhj205eXMmSHE+unGifiRqNxp9rxCWGtabSmPEu8i0m2K9UYOaqPzLSSv2yhuGXY6qA1Ae+tOOmSUvONGnYzCG0jr+MMeefb+cQHVF4Wmq1G/S6DLAJLkRBWizT1otVPyov4HUczgReAAAA=") !important;background-position:center !important;background-size:cover !important;min-height:190px;}
    @media(max-width:850px){.yani-stats{grid-template-columns:repeat(2,minmax(0,1fr));}.yani-hero{padding:22px 18px;}}
    /* 16.4: single sidebar promo, no duplicated text embedded in photo */
    .yani-sidebar-footer {margin-top:14px;min-height:105px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;font-size:48px;border:1px solid #17436d;border-radius:14px;background:linear-gradient(160deg,#06264a,#04152a);}
    .yani-sidebar-footer small {font-size:10px;letter-spacing:1.4px;color:#8bd4ff;font-weight:700;}
    section[data-testid="stSidebar"] .stVerticalBlock {gap:0.55rem !important;}
    .yani-team-crest {width:35px;height:35px;object-fit:contain;vertical-align:middle;margin:0 8px;}
    .yani-club-header {display:flex;align-items:center;gap:10px;}
    .yani-club-header img {width:48px;height:48px;object-fit:contain;}
    /* Step 17.1: consistent club crests and responsive match cards */
    .yani-fixture-teams {display:grid;grid-template-columns:minmax(0,1fr) 58px minmax(0,1fr);align-items:center;gap:12px;padding:10px 2px;}
    .yani-fixture-club {display:flex;align-items:center;gap:12px;min-width:0;color:#f3f9ff;}
    .yani-fixture-club strong {font-size:15px;overflow-wrap:anywhere;line-height:1.35;}
    .yani-fixture-vs {text-align:center;color:#48bfff;font-size:17px;font-weight:900;white-space:nowrap;}
    .yani-crest-img {object-fit:contain;flex-shrink:0;max-width:40px;}
    .yani-crest-fallback {font-size:26px;flex-shrink:0;}
    .yani-fixture-teams.compact .yani-fixture-club strong {font-size:13px;}
    .yani-match {min-width:0;}
    .yani-match strong {line-height:1.8;overflow-wrap:anywhere;}
    .yani-match .yani-team-crest {width:29px;height:29px;}
    @media(max-width:700px){.yani-fixture-teams{gap:6px;grid-template-columns:minmax(0,1fr) 38px minmax(0,1fr);}.yani-fixture-club{flex-direction:column;text-align:center;gap:5px;}.yani-fixture-club strong{font-size:12px;}.yani-fixture-vs{font-size:12px;}}
    </style>
    """, unsafe_allow_html=True)

    # Sidebar navigation uses callbacks so dashboard_tab is updated before
    # the radio widget is instantiated (avoids Streamlit session-state errors).
    st.markdown("""<style>
    /* Step 24.9: Sidebar content must begin at the TOP, not below a flex spacer.
       Streamlit versions differ in the nesting of these containers. */
    section[data-testid="stSidebar"] {
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-items: stretch !important;
    }
    section[data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    [data-testid="stSidebarUserContent"],
    [data-testid="stSidebarContent"] > div,
    [data-testid="stSidebarUserContent"] > div {
        justify-content: flex-start !important;
        align-content: flex-start !important;
        align-items: stretch !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
        min-height: 0 !important;
        height: auto !important;
        flex-grow: 0 !important;
        transform: none !important;
    }
    [data-testid="stSidebarContent"] {
        overflow-y: auto !important;
        overscroll-behavior: contain;
    }
    [data-testid="stSidebarUserContent"] { padding: .5rem .8rem 1rem !important; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        justify-content: flex-start !important;
        align-items: stretch !important;
        gap: .4rem !important;
    }
    /* Streamlit defaults to a large sidebar top inset for its toolbar. */
    [data-testid="stSidebarUserContent"] {padding-top: .5rem !important;}
    [data-testid="stSidebarContent"] {padding-top: 0 !important;}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {padding-top: 0 !important;}
    [data-testid="stSidebarContent"] > div {min-height:0 !important;}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.38rem;}
    [data-testid="stSidebar"] button {border-radius:11px !important;min-height:38px;}
    [data-testid="stSidebar"] [data-testid="stRadio"] {margin-bottom:8px;}
    .yani-sidebar-slogan,.yani-sidebar-footer,.yani-sidebar-ball {display:none !important;}
    @media(max-width:760px){.yani-stats{grid-template-columns:repeat(2,minmax(0,1fr)) !important;}}
    </style>""", unsafe_allow_html=True)

    # Step 26 — responsive-only adjustments. Desktop selectors remain untouched.
    st.markdown("""<style>
    @media (max-width: 760px) {
      /* Preserve Streamlit's native sidebar toggle and drawer behavior. */
      [data-testid="stSidebar"] {max-width:min(85vw, 310px) !important;}
      [data-testid="stSidebarUserContent"] {padding:.65rem .8rem 1.25rem !important;}
      [data-testid="stSidebar"] button {min-height:43px !important;}
      [data-testid="stMainBlockContainer"] {
        padding: .75rem .75rem 2rem !important;
        max-width:100% !important;
      }
      [data-testid="stMain"] {min-width:0 !important;overflow-x:clip;}
      [data-testid="stMain"] [data-testid="stVerticalBlock"] {min-width:0;}
      [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
        gap:.6rem !important;min-width:0;
      }
      [data-testid="stMain"] [data-testid="column"] {min-width:0 !important;}
      [data-testid="stMain"] .stButton button,
      [data-testid="stMain"] .stDownloadButton button {min-height:43px;}
      [data-testid="stMain"] h1 {font-size:clamp(1.5rem,6vw,2.1rem) !important;line-height:1.2;}
      [data-testid="stMain"] h2 {font-size:clamp(1.25rem,5vw,1.7rem) !important;}
      [data-testid="stMain"] h3 {font-size:1.15rem !important;}
      .yani-stats,.ya-stat-grid {grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
      .yani-market-grid {grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
      .yani-hero,.yani-pred-hero {padding:16px 12px !important;}
      .yani-fixture-teams,.yani-pred-fixture {min-width:0;gap:5px !important;}
      .yani-fixture-club strong,.yani-pred-club strong {overflow-wrap:anywhere;}
      .yt-summary,.yc-grid,.yi-grid {grid-template-columns:1fr !important;}
      .yt-tip-head,.yt-tip-row {grid-template-columns:minmax(0,1fr) 66px 92px !important;gap:5px !important;}
      .yt-tip-head,.yt-tip-row {padding:10px 7px !important;}
      .yt-tip-name strong {font-size:11px !important;overflow-wrap:anywhere;}
      .yt-tip-prob {min-width:0;}
      .yc-panel,.yi-card {padding:13px !important;min-width:0;}
      .yi-pitch {min-height:450px !important;max-width:100%;}
      .yi-avatar {width:32px !important;height:32px !important;font-size:11px !important;}
      .yi-player {width:23% !important;}
      .yi-player-name {font-size:9px !important;line-height:1.15 !important;}
      .yi-injury-row {gap:9px;padding:12px 2px;}
      .yi-injury-icon {width:34px;height:34px;}
      div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) [role="radiogroup"] {
        flex-wrap:nowrap !important;overflow-x:auto !important;
        -webkit-overflow-scrolling:touch;scroll-snap-type:x proximity;
        padding-bottom:12px !important;
      }
      div[data-testid="stRadio"]:has(input[name^="yani_prediction_section_"]) label {
        scroll-snap-align:start;min-height:42px;display:flex;align-items:center;
      }
    }
    @media (max-width: 430px) {
      .yi-pitch {min-height:420px !important;}
      .yi-player-name {font-size:8px !important;}
      .yani-outcomes {gap:4px !important;}
      .yani-outcome-card {padding:10px 5px !important;}
      .yani-outcome-number {font-size:21px !important;}
      .yani-score-row {gap:3px !important;padding:9px 4px !important;}
    }
    </style>""", unsafe_allow_html=True)

    # Streamlined sidebar: navigation, appearance and account actions.
    with st.sidebar:
        st.markdown('<div class="yani-sidebar-brand">⚽ YANI<span>DOLLARZ</span></div><div class="yani-sidebar-tag">FOOTBALL MATCH CENTRE</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="margin:9px 0 18px;padding:11px 13px;background:#112b49;border:1px solid #2c5378;border-radius:11px;color:#eaf5ff;font-size:13px;">👤 Signed in as <strong style="color:#69c9ff;overflow-wrap:anywhere">{safe_username}</strong></div>',unsafe_allow_html=True)
        st.caption("NAVIGATION")
        sidebar_links = [
            ("🏠 Dashboard", "Dashboard"),
            ("📅 Fixtures", "Fixtures"),
            ("🎯 Make Predictions", "Predictions"),
            ("🔴 Live Match Centre", "Match Centre"),
            ("🏆 League Standings", "Standings"),
            ("🔍 Match Analysis", "Match Analysis"),
            ("⚠️ Risk Analysis", "Risk Analysis"),
            ("🕘 Prediction History", "History"),
            ("📈 Performance", "Performance"),
        ]
        for i, (caption, tab_name) in enumerate(sidebar_links):
            st.button(caption, key=f"sidebar_nav_{i}", use_container_width=True,
                      on_click=change_dashboard_tab, args=(tab_name,))
        st.divider()
        st.caption("APPEARANCE")
        appearance = st.radio("Colour mode", ["🌙 Dark", "☀️ Light"],
                              key="yani_appearance", horizontal=True,
                              label_visibility="collapsed")
        st.divider()
        st.button("🚪 Log out", key="dashboard_logout", use_container_width=True,
                  on_click=logout)

    if appearance == "☀️ Light":
        st.markdown("""
        <style>
        :root { color-scheme: light; }
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            background: #f1f5fb !important; color: #15243b !important;
        }
        [data-testid="stSidebar"], [data-testid="stSidebarContent"] {
            background: #e5edf8 !important; color: #15243b !important;
        }
        .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3,
        .stApp h4, .stApp span, .stApp small, .stApp li {
            color: #15243b;
        }
        [data-testid="stSidebar"] button, .stApp button {
            color: #163251 !important; background: #ffffff !important;
            border-color: #c8d6e7 !important;
        }
        [data-testid="stSidebar"] .yani-sidebar-brand { color:#112e50 !important; }
        .yani-stat, .yani-empty, .yani-match, .yani-card,
        .yani-fixture-card, .yani-analysis-panel, .yani-market-card,
        .yani-standings-table, [data-testid="stMetric"] {
            color:#163251 !important; border-color:#c8d6e7 !important;
        }
        .yani-hero, .yani-stat, .yani-match, .yani-empty,
        .yani-fixture-card, .yani-analysis-panel {
            box-shadow: 0 5px 16px rgba(22,48,83,.09);
        }
        [data-testid="stDataFrame"], [data-testid="stPlotlyChart"] {
            border-radius: 14px; overflow:hidden;
        }
        </style>
        """, unsafe_allow_html=True)

    # Navigation lives in session state, not an invisible radio widget.
    # The old hidden radio occupied a Streamlit layout row and caused
    # unnecessary blank space above the dashboard.
    tabs = ["Dashboard", "Fixtures", "Match Centre", "Standings", "Match Analysis", "Predictions", "Risk Analysis", "History", "Performance"]
    if st.session_state.get("dashboard_tab") not in tabs:
        st.session_state.dashboard_tab = "Dashboard"
    selected = st.session_state.dashboard_tab

    st.markdown("""<style>
    /* Remove unused top padding without covering Streamlit's toolbar. */
    [data-testid="stMainBlockContainer"] {padding-top: 1.1rem !important;}
    @media(max-width:760px){[data-testid="stMainBlockContainer"]{padding-top:.8rem !important;}}
    </style>""", unsafe_allow_html=True)

    # Real Johannesburg clock, refreshed independently of the main page.
    if hasattr(st, "fragment"):
        @st.fragment(run_every="1s")
        def yani_live_clock():
            st.markdown(f'<div class="yani-live-time">🕒 {datetime.now(SA_TIMEZONE).strftime("%a %d %b %Y · %H:%M:%S")} SAST</div>', unsafe_allow_html=True)
        yani_live_clock()
    else:
        st.caption("Times shown in SAST · refresh to update the clock")

    if selected == "Dashboard":
        st.markdown(f'<div style="font-size:15px;color:#b6d5ee;margin:2px 0 12px">👋 Welcome back, <strong style="color:#52bdff">{safe_username}</strong>!</div>', unsafe_allow_html=True)
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
                total_count = max(1, correct + incorrect + pending)
                status_rows = [("Correct", correct, "#12c991"), ("Incorrect", incorrect, "#f16b77"), ("Pending", pending, "#f6a83c")]
                bars = "".join(
                    f'<div style="display:flex;justify-content:space-between;margin:12px 0 6px;font-weight:650;">'
                    f'<span>{label}</span><span>{count}</span></div>'
                    f'<div style="height:10px;background:#31445f;border-radius:20px;overflow:hidden;">'
                    f'<div style="width:{100*count/total_count:.1f}%;height:100%;background:{colour};border-radius:20px;"></div></div>'
                    for label, count, colour in status_rows
                )
                st.markdown(f'<div style="background:#132b47;color:#eef7ff;padding:22px;border:1px solid #2a4b71;border-radius:16px;min-height:225px;">{bars}</div>', unsafe_allow_html=True)
            else:
                st.info("Save a prediction to see your breakdown.")
            st.markdown(f'<div class="yani-breakdown">🟢 Correct: <b>{correct}</b> &nbsp; 🔴 Incorrect: <b>{incorrect}</b> &nbsp; 🟠 Pending: <b>{pending}</b></div>', unsafe_allow_html=True)

        # Reuse cached fixtures to obtain real club crests (no guessed image URLs).
        today = datetime.now(SA_TIMEZONE).date()
        upcoming_matches, upcoming_error = get_competition_fixtures("Premier League", today, today + timedelta(days=7))
        crest_lookup = {}
        st.session_state.yani_recent_crest_matches = {
            str(item.get("id")): item for item in upcoming_matches if item.get("id")
        }
        for item in upcoming_matches:
            for side in ("homeTeam", "awayTeam"):
                team = item.get(side) or {}
                crest = team.get("crest")
                if crest and str(crest).startswith("https://"):
                    for name in (team.get("name"), team.get("shortName"), team.get("tla")):
                        if name:
                            crest_lookup[str(name).lower().replace(" fc", "").strip()] = crest

        def dashboard_crest(name):
            key = str(name or "").lower().replace(" fc", "").strip()
            url = crest_lookup.get(key)
            if not url:
                for label, candidate in crest_lookup.items():
                    if key and (key == label or (len(key) > 5 and (key in label or label in key))):
                        url = candidate
                        break
            return f'<img class="yani-team-crest" src="{html.escape(url, quote=True)}" alt="" loading="lazy">' if url else "⚽ "

        left, right = st.columns([1.55, 1], gap="medium")
        with left:
            st.markdown('<div class="yani-section-heading">🕘 Recent Predictions</div>', unsafe_allow_html=True)
            st.caption("Your latest saved predictions from Supabase")
            if dashboard_history:
                for record in dashboard_history[:5]:
                    status = record.get("status", "Pending")
                    badge = "finished" if status == "Finished" else "pending"
                    title = dashboard_crest(record.get("home")) + html.escape(str(record.get("home", "Home"))) + " <span>VS</span> " + dashboard_crest(record.get("away")) + html.escape(str(record.get("away", "Away")))
                    when = html.escape(local_kickoff(record.get("kickoff")))
                    result = ""
                    if status == "Finished" and record.get("score_home") is not None and record.get("score_away") is not None:
                        result = f' · {record["score_home"]}–{record["score_away"]}'
                    st.markdown(f'<div class="yani-match"><div><strong>{title}</strong><small>{when}{result}</small></div><span class="yani-pill {badge}">{html.escape(status)}</span></div>', unsafe_allow_html=True)
            else:
                st.info("No saved predictions yet. Open Fixtures and save your first prediction.")
            st.button("📚 Open Prediction History", key="dash_history", on_click=change_dashboard_tab, args=("History",), use_container_width=True)
            st.markdown('<div class="yani-section-heading" style="margin-top:16px;">🏆 Explore Top Leagues</div>', unsafe_allow_html=True)
            league_tiles = [("PL", "Premier League"), ("PD", "La Liga"), ("SA", "Serie A"), ("BL1", "Bundesliga"), ("FL1", "Ligue 1"), ("CL", "Champions League")]
            league_cols = st.columns(3, gap="small")
            for index, (code, league_name) in enumerate(league_tiles):
                with league_cols[index % 3]:
                    emblem = f"https://crests.football-data.org/{code}.png"
                    st.markdown(f'<div class="yani-league"><img src="{emblem}" alt="{league_name} logo" loading="lazy"><small>{league_name}</small></div>', unsafe_allow_html=True)
                    st.button(f"View {league_name}", key=f"league_go_{code}", use_container_width=True, on_click=open_competition, args=(league_name,))
            st.caption("Select a competition above to open its fixtures.")
        with right:
            st.markdown('<div class="yani-section-heading">📅 Upcoming Matches</div>', unsafe_allow_html=True)
            st.caption("Premier League · Next 7 days · SAST")
            if upcoming_error:
                st.warning(upcoming_error)
            else:
                scheduled = sorted((m for m in upcoming_matches if m.get("status") in ("SCHEDULED", "TIMED")), key=lambda m: m.get("utcDate", ""))
                if scheduled:
                    for match in scheduled[:4]:
                        home = html.escape(str((match.get("homeTeam") or {}).get("shortName") or (match.get("homeTeam") or {}).get("name") or "Home"))
                        away = html.escape(str((match.get("awayTeam") or {}).get("shortName") or (match.get("awayTeam") or {}).get("name") or "Away"))
                        when = html.escape(local_kickoff(match.get("utcDate")))
                        home_team = match.get("homeTeam") or {}
                        away_team = match.get("awayTeam") or {}
                        home_crest = crest_markup(home_team, 34)
                        away_crest = crest_markup(away_team, 34)
                        st.markdown(f'<div class="yani-match"><div><strong>{home_crest}{home} <span>VS</span> {away_crest}{away}</strong><small>{when}</small></div><span class="yani-pill pending">Upcoming</span></div>', unsafe_allow_html=True)
                else:
                    st.info("No Premier League matches in the next 7 days.")
            st.button("⚽ Browse Fixtures", key="dash_fixtures", on_click=change_dashboard_tab, args=("Fixtures",), use_container_width=True)


    elif selected == "Match Centre":
        render_match_centre()

    elif selected == "Standings":
        render_league_standings()

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
        # Step 28 — manual, quota-conscious API-Football statistics diagnostic.
        # A fixture ID is from API-Football (not football-data.org).
        with st.expander("🧪 API-Football corners & bookings test", expanded=False):
            st.caption("Test a completed API-Football fixture. This diagnostic only makes a request when you press the button; it does not change any predictions.")
            stats_fixture_id = st.number_input(
                "API-Football fixture ID", min_value=1, value=1, step=1,
                key="yani_stats_fixture_id",
                help="Use an ID from API-Football GET /fixtures, not from football-data.org."
            )
            if st.button("🔎 Test corner & card statistics", key="yani_test_fixture_stats"):
                _stats_key = st.secrets.get("API_FOOTBALL_KEY", "")
                if not _stats_key:
                    st.error("API_FOOTBALL_KEY is not configured in Streamlit Secrets.")
                else:
                    try:
                        _stats_url = "https://v3.football.api-sports.io/fixtures/statistics?fixture=" + str(int(stats_fixture_id))
                        _stats_req = Request(_stats_url, headers={
                            "x-apisports-key": _stats_key, "Accept": "application/json"
                        })
                        with st.spinner("Checking match statistics…"):
                            with urlopen(_stats_req, timeout=15) as _stats_response:
                                _stats_payload = json.load(_stats_response)
                        _api_errors = _stats_payload.get("errors") or {}
                        if _api_errors:
                            st.error("API-Football returned an error: " + str(_api_errors)[:450])
                        elif not _stats_payload.get("response"):
                            st.warning("No match statistics returned. Check that the fixture ID belongs to a completed, supported match and season.")
                        else:
                            _stats_rows = []
                            for _side in _stats_payload.get("response", []):
                                _team = (_side.get("team") or {}).get("name", "Unknown team")
                                _by_type = {str(_item.get("type", "")).casefold(): _item.get("value")
                                            for _item in (_side.get("statistics") or [])}
                                _stats_rows.append({
                                    "Team": _team,
                                    "Corner Kicks": _by_type.get("corner kicks"),
                                    "Yellow Cards": _by_type.get("yellow cards"),
                                    "Red Cards": _by_type.get("red cards"),
                                })
                            st.dataframe(pd.DataFrame(_stats_rows), hide_index=True, use_container_width=True)
                            _has_corners = any(row.get("Corner Kicks") is not None for row in _stats_rows)
                            _has_yellows = any(row.get("Yellow Cards") is not None for row in _stats_rows)
                            if _has_corners and _has_yellows:
                                st.success("Corners and yellow-card statistics are available for this fixture!")
                            else:
                                st.warning("Statistics returned, but corner kicks or yellow cards are missing for this fixture.")
                            st.caption("Recorded statistics only — these are not pre-match predictions. Each test uses an API request and counts toward your daily quota.")
                    except HTTPError as _stats_err:
                        if _stats_err.code in (401, 403):
                            st.error("API-Football denied access (401/403). Check the key, plan and season coverage.")
                        elif _stats_err.code == 429:
                            st.error("API-Football rate limit reached (429). Try again after your quota resets.")
                        else:
                            st.error(f"API-Football HTTP error: {_stats_err.code}.")
                    except (URLError, TimeoutError, ValueError, TypeError) as _stats_err:
                        st.error("Could not complete the statistics test: " + type(_stats_err).__name__)

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

    elif selected == "Performance":
        show_performance_page()


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