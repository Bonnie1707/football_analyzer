import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --------------------
# Page & config
# --------------------
st.set_page_config(page_title="Football Trends Analyzer", layout="wide")
st.title("⚽ Football Trends Analyzer — Fixture-based Head-to-Head")
st.markdown("Select a league, click a fixture, and the model will fetch both teams' stats and show predictions.")

# --------------------
# Settings (API)
# --------------------
API_KEY = st.secrets["API_KEY"]
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# --------------------
# Helpers & caching
# --------------------
@st.cache_data(ttl=600)  # cache results for 10 minutes
def get_fixtures(league_id, season=2023, next_n=10):
    """Return next fixtures for league."""
    url = f"{BASE_URL}/fixtures?league={league_id}&season={season}&next={next_n}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return None
    return r.json().get("response", [])

@st.cache_data(ttl=600)
def get_team_statistics(league_id, team_id, season=2023):
    """Return team statistics object for team in league. Handles API response shapes."""
    url = f"{BASE_URL}/teams/statistics?league={league_id}&season={season}&team={team_id}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    resp = data.get("response")
    # some endpoints return list or dict; if list, take first element
    if isinstance(resp, list) and len(resp) > 0:
        return resp[0]
    return resp

@st.cache_data(ttl=600)
def get_injuries(team_id, season=2023):
    """Return list of injuries for a team."""
    url = f"{BASE_URL}/injuries?team={team_id}&season={season}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("response", [])

def safe_get(d, *keys, default=None):
    """Safe lookup nested dicts/lists; returns default if not found."""
    cur = d
    try:
        for k in keys:
            cur = cur[k]
        return cur
    except Exception:
        return default

# --------------------
# Normalization helpers
# --------------------
def normalize_form(form_str):
    """Convert a form string like 'WWDLW' to normalized 0-1 (W=3, D=1, L=0)."""
    if not form_str:
        return 0.0
    points = 0
    count = 0
    for ch in form_str:
        if ch == "W":
            points += 3
        elif ch == "D":
            points += 1
        elif ch == "L":
            points += 0
        else:
            continue
        count += 1
    if count == 0:
        return 0.0
    max_points = 3 * count
    return points / max_points  # 0..1

def normalize_goal_rate(goals_per_match, denom=3.0):
    """Normalize goals per match to 0-1, denom is expected upper bound (3 goals per match)."""
    if goals_per_match is None:
        return 0.0
    return min(max(goals_per_match / denom, 0.0), 1.0)

def invert_normalize_goal_conceded(goals_conceded_per_match, denom=3.0):
    """Lower conceded goals => better => invert normalized value."""
    if goals_conceded_per_match is None:
        return 0.0
    return min(max(1.0 - (goals_conceded_per_match / denom), 0.0), 1.0)

def normalize_manager_rate(wins, played):
    if not played or played == 0:
        return 0.0
    return min(max(wins / played, 0.0), 1.0)

def normalize_player_availability(num_injuries, key_players=5):
    """
    Simple approximation:
      - Key players approx count = key_players (default 5).
      - If injuries among squad >= key_players -> availability 0.
      - Else availability = 1 - injuries/key_players
    """
    if num_injuries is None:
        return 1.0
    return max(0.0, 1.0 - (num_injuries / key_players))

# --------------------
# Sidebar: fixtures list & league select
# --------------------
with st.sidebar:
    st.header("🔎 Select League & Fixture")
    league_id = st.text_input("League ID (e.g., 39 = EPL)", value="39")
    season = st.text_input("Season (year)", value="2023")
    next_n = st.number_input("Show next fixtures (n)", min_value=1, max_value=20, value=10)
    st.write("---")
    st.caption("Click any fixture to analyze automatically (cached to reduce API calls).")

    fixtures = get_fixtures(league_id, season=int(season), next_n=next_n)
    if fixtures is None:
        st.warning("Unable to fetch fixtures. Check league ID, season or API usage.")
    else:
        # clickable list (set selected fixture into session state)
        if "selected_fixture" not in st.session_state:
            st.session_state.selected_fixture = None

        for f in fixtures:
            fid = safe_get(f, "fixture", "id")
            date_iso = safe_get(f, "fixture", "date")
            date_str = ""
            try:
                date_str = datetime.fromisoformat(date_iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = date_iso or ""
            home = safe_get(f, "teams", "home", "name", default="Home")
            away = safe_get(f, "teams", "away", "name", default="Away")
            btn_label = f"{date_str} • {home}  VS  {away}"
            if st.button(btn_label, key=f"fix_{fid}"):
                st.session_state.selected_fixture = f

    st.write("---")
    if st.session_state.get("selected_fixture"):
        sf = st.session_state.selected_fixture
        st.markdown("**Selected:**")
        st.markdown(f"**{safe_get(sf,'teams','home','name','') }** vs **{safe_get(sf,'teams','away','name','') }**")
        if st.button("Clear selection"):
            st.session_state.selected_fixture = None

st.divider()

# --------------------
# Main view
# --------------------
selected = st.session_state.get("selected_fixture")

if not selected:
    st.info("Select a fixture from the left (sidebar) to analyze. Or paste team IDs manually below.")
    # allow manual fallback
    c1, c2 = st.columns(2)
    with c1:
        teamA_id_manual = st.text_input("Manual Team A ID (optional)", value="")
    with c2:
        teamB_id_manual = st.text_input("Manual Team B ID (optional)", value="")

    analyze_manual = st.button("Analyze Manual Teams")
    if analyze_manual and teamA_id_manual and teamB_id_manual:
        # build a fake selected fixture structure using manual ids
        selected = {
            "fixture": {"id": -1, "date": datetime.utcnow().isoformat()},
            "teams": {"home": {"id": int(teamA_id_manual), "name": f"Team {teamA_id_manual}"},
                      "away": {"id": int(teamB_id_manual), "name": f"Team {teamB_id_manual}"}}
        }
        st.session_state.selected_fixture = selected
        st.experimental_rerun()
else:
    # we have a selected fixture — extract team ids and names
    home_team = safe_get(selected, "teams", "home", default={})
    away_team = safe_get(selected, "teams", "away", default={})
    teamA_id = safe_get(home_team, "id")
    teamB_id = safe_get(away_team, "id")
    teamA_name = safe_get(home_team, "name", default=str(teamA_id))
    teamB_name = safe_get(away_team, "name", default=str(teamB_id))
    match_date = safe_get(selected, "fixture", "date", default="")

    st.header(f"{teamA_name}  vs  {teamB_name}")
    st.subheader(f"Match date: {match_date}")

    # --------------------
    # Fetch stats (cached)
    # --------------------
    statA = get_team_statistics(league_id, teamA_id, season=int(season))
    statB = get_team_statistics(league_id, teamB_id, season=int(season))
    injA = get_injuries(teamA_id, season=int(season))
    injB = get_injuries(teamB_id, season=int(season))

    if not statA or not statB:
        st.error("Could not fetch team statistics. Check league/team IDs or API limits.")
    else:
        # --------------------
        # Compute each metric (normalized 0..1)
        # --------------------
        # 1) Location: 1 if home for teamA else 0
        location_A = 1.0  # by selection home=teamA
        location_B = 0.0

        # 2) Recent Form - prefer stat['form'] if present
        formA_raw = safe_get(statA, "form", default=None)
        formB_raw = safe_get(statB, "form", default=None)
        formA = normalize_form(formA_raw)
        formB = normalize_form(formB_raw)

        # 3) Goals for per match (total goals for / matches played)
        goalsA_total = safe_get(statA, "goals", "for", "total", "total", default=None)
        goalsB_total = safe_get(statB, "goals", "for", "total", "total", default=None)
        matchesA_played = safe_get(statA, "fixtures", "played", "total", default=None)
        matchesB_played = safe_get(statB, "fixtures", "played", "total", default=None)

        goalsA_per_match = None
        goalsB_per_match = None
        if goalsA_total is not None and matchesA_played:
            goalsA_per_match = goalsA_total / matchesA_played
        if goalsB_total is not None and matchesB_played:
            goalsB_per_match = goalsB_total / matchesB_played

        gfA = normalize_goal_rate(goalsA_per_match)
        gfB = normalize_goal_rate(goalsB_per_match)

        # 4) Goals conceded per match (lower is better -> invert)
        gaA_total = safe_get(statA, "goals", "against", "total", "total", default=None)
        gaB_total = safe_get(statB, "goals", "against", "total", "total", default=None)
        gaA_per_match = None
        gaB_per_match = None
        if gaA_total is not None and matchesA_played:
            gaA_per_match = gaA_total / matchesA_played
        if gaB_total is not None and matchesB_played:
            gaB_per_match = gaB_total / matchesB_played

        gcA = invert_normalize_goal_conceded(gaA_per_match)
        gcB = invert_normalize_goal_conceded(gaB_per_match)

        # 5) Key player availability (approx from injuries)
        num_injA = len(injA) if injA else 0
        num_injB = len(injB) if injB else 0
        paA = normalize_player_availability(num_injA)
        paB = normalize_player_availability(num_injB)

        # 6) Manager win rate (approx from fixtures wins/played as a season proxy)
        winsA = safe_get(statA, "fixtures", "wins", "total", default=0)
        winsB = safe_get(statB, "fixtures", "wins", "total", default=0)
        playedA = safe_get(statA, "fixtures", "played", "total", default=0)
        playedB = safe_get(statB, "fixtures", "played", "total", default=0)
        mrA = normalize_manager_rate(winsA, playedA)
        mrB = normalize_manager_rate(winsB, playedB)

        # --------------------
        # Weights & final score
        # --------------------
        weights = {
            "location": 0.15,
            "form": 0.25,
            "gf": 0.20,
            "gc": 0.15,
            "pa": 0.15,
            "mr": 0.10
        }

        scoreA = (weights["location"] * location_A +
                  weights["form"] * formA +
                  weights["gf"] * gfA +
                  weights["gc"] * gcA +
                  weights["pa"] * paA +
                  weights["mr"] * mrA)

        scoreB = (weights["location"] * location_B +
                  weights["form"] * formB +
                  weights["gf"] * gfB +
                  weights["gc"] * gcB +
                  weights["pa"] * paB +
                  weights["mr"] * mrB)

        # Convert to probabilities
        if (scoreA + scoreB) > 0:
            probA = scoreA / (scoreA + scoreB)
            probB = scoreB / (scoreA + scoreB)
        else:
            probA = probB = 0.5

        # Draw rule: if close within threshold
        draw_threshold = 0.10
        is_draw = abs(scoreA - scoreB) < draw_threshold

        # --------------------
        # Display metrics & charts
        # --------------------
        st.subheader("🔎 Metrics (normalized 0–1)")
        metrics_df = pd.DataFrame({
            "Metric": ["Location (home)", "Recent Form", "Goals For", "Goals (defense)", "Player Avail.", "Manager Rate"],
            teamA_name: [location_A, formA, gfA, gcA, paA, mrA],
            teamB_name: [location_B, formB, gfB, gcB, paB, mrB]
        })
        st.dataframe(metrics_df.style.format("{:.2f}"))

        # Radar chart (polar)
        categories = ["Location", "Form", "Goals For", "Goals Def", "Player Avail", "Manager"]
        valsA = [location_A, formA, gfA, gcA, paA, mrA]
        valsB = [location_B, formB, gfB, gcB, paB, mrB]

        radar_fig = go.Figure()
        radar_fig.add_trace(go.Scatterpolar(r=valsA, theta=categories, fill='toself', name=teamA_name))
        radar_fig.add_trace(go.Scatterpolar(r=valsB, theta=categories, fill='toself', name=teamB_name))
        radar_fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=True,
                                title="Team Profile (Normalized Metrics)")
        st.plotly_chart(radar_fig, use_container_width=True)

        # Bar chart: Goals Scored vs Conceded
        st.subheader("⚽ Goals (Season totals & per-match average)")
        g_df = pd.DataFrame({
            "Metric": ["Goals For (total)", "Goals Against (total)", "Goals For (per match)", "Goals Against (per match)"],
            teamA_name: [goalsA_total or 0, gaA_total or 0, round(goalsA_per_match or 0, 2), round(gaA_per_match or 0, 2)],
            teamB_name: [goalsB_total or 0, gaB_total or 0, round(goalsB_per_match or 0, 2), round(gaB_per_match or 0, 2)]
        })
        # melt for plotting
        g_melt = g_df.melt(id_vars=["Metric"], var_name="Team", value_name="Value")
        g_fig = px.bar(g_melt, x="Metric", y="Value", color="Team", barmode="group", title="Goals Comparison")
        st.plotly_chart(g_fig, use_container_width=True)

        # Injuries lists
        st.subheader("🚑 Injuries / Unavailable Players (approx)")
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**{teamA_name} injuries ({len(injA)})**")
            if injA:
                for it in injA:
                    pname = safe_get(it, "player", "name", default="Unknown")
                    reason = safe_get(it, "player", "reason", default="N/A")
                    st.write(f"- {pname} — {reason}")
            else:
                st.write("No reported injuries.")

        with c2:
            st.write(f"**{teamB_name} injuries ({len(injB)})**")
            if injB:
                for it in injB:
                    pname = safe_get(it, "player", "name", default="Unknown")
                    reason = safe_get(it, "player", "reason", default="N/A")
                    st.write(f"- {pname} — {reason}")
            else:
                st.write("No reported injuries.")

        # Prediction summary box
        st.subheader("📈 Prediction Summary")
        if is_draw:
            st.info(f"Prediction: Likely Draw (teams are very close). Probabilities — {teamA_name}: {probA*100:.1f}% | {teamB_name}: {probB*100:.1f}%")
        else:
            winner = teamA_name if probA > probB else teamB_name
            st.success(f"Predicted likely winner: **{winner}**")
            st.metric(label=f"{teamA_name} Win Probability", value=f"{probA*100:.1f}%")
            st.metric(label=f"{teamB_name} Win Probability", value=f"{probB*100:.1f}%")

        # small debug / raw response toggle
        if st.checkbox("Show raw API responses (for debugging)"):
            st.subheader("Raw teamA statistics")
            st.json(statA)
            st.subheader("Raw teamB statistics")
            st.json(statB)
            st.subheader("Raw injuries A")
            st.json(injA)
            st.subheader("Raw injuries B")
            st.json(injB)
