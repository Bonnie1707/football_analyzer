import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Football Trends Analyzer", layout="wide")
st.title("⚽ Football Trends Analyzer")
st.write("Compare competing teams, visualize performance trends, and generate predictions using API-Football data.")

# --- API SETUP ---
API_KEY = st.secrets["API_KEY"]
BASE_URL = "https://v3.football.api-sports.io"
headers = {"x-apisports-key": API_KEY}

# --- HELPER FUNCTIONS ---
def get_fixtures(league_id):
    url = f"{BASE_URL}/fixtures?league={league_id}&season=2024&next=10"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error("Failed to fetch fixtures.")
        return []
    data = r.json()
    return data.get("response", [])

def get_team_stats(league_id, team_id):
    url = f"{BASE_URL}/teams/statistics?league={league_id}&season=2024&team={team_id}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    return r.json().get("response", {})

def normalize(value, max_val):
    return min(value / max_val, 1.0) if max_val else 0

def compute_score(stats, location_score, player_avail, manager_rate):
    form = stats.get("form", "")
    form_score = sum([3 if c == "W" else 1 if c == "D" else 0 for c in form]) / (5 * 3)

    goals_for = stats["goals"]["for"]["total"]["total"] / max(stats["fixtures"]["played"]["total"], 1)
    goals_against = stats["goals"]["against"]["total"]["total"] / max(stats["fixtures"]["played"]["total"], 1)

    goals_for_n = normalize(goals_for, 3)
    goals_against_n = 1 - normalize(goals_against, 3)

    score = (
        0.15 * location_score
        + 0.25 * form_score
        + 0.20 * goals_for_n
        + 0.15 * goals_against_n
        + 0.15 * player_avail
        + 0.10 * manager_rate
    )
    return score, {"Form": form_score, "Goals For": goals_for_n,
                   "Goals Against": goals_against_n,
                   "Player Availability": player_avail,
                   "Manager Rate": manager_rate,
                   "Location": location_score}

def get_injury_ratio(team_id):
    # Placeholder until we integrate detailed player data
    return 1.0

def get_manager_win_rate(stats):
    wins = stats["fixtures"]["wins"]["total"]
    played = stats["fixtures"]["played"]["total"]
    return normalize(wins / played if played else 0, 1)

# --- SIDEBAR ---
st.sidebar.header("⚙️ Select League & Fixture")
league_id = st.sidebar.text_input("Enter League ID (e.g. 39 for Premier League)", "39")

fixtures = get_fixtures(league_id)
fixture_names = [
    f"{f['teams']['home']['name']} vs {f['teams']['away']['name']} ({f['fixture']['date'][:10]})"
    for f in fixtures
]
selected_fixture = st.sidebar.selectbox("Choose Fixture to Analyze", fixture_names if fixture_names else [])

if selected_fixture:
    selected = fixtures[fixture_names.index(selected_fixture)]
else:
    selected = None

st.sidebar.write("---")
st.sidebar.write("🔍 Or analyze manually:")
teamA_id_manual = st.sidebar.text_input("Team A ID")
teamB_id_manual = st.sidebar.text_input("Team B ID")
analyze_manual = st.sidebar.button("Analyze Manual Teams")

# --- SAFE MANUAL ANALYSIS ---
if analyze_manual:
    try:
        teamA_id_int = int(teamA_id_manual.strip())
        teamB_id_int = int(teamB_id_manual.strip())
        selected = {
            "fixture": {"id": -1, "date": datetime.utcnow().isoformat()},
            "teams": {
                "home": {"id": teamA_id_int, "name": f"Team {teamA_id_int}"},
                "away": {"id": teamB_id_int, "name": f"Team {teamB_id_int}"}
            }
        }
        st.session_state.selected_fixture = selected
        st.experimental_rerun()
    except ValueError:
        st.error("⚠️ Please enter numeric team IDs before analyzing.")

# --- MAIN ANALYSIS ---
if selected:
    home = selected["teams"]["home"]
    away = selected["teams"]["away"]

    st.subheader(f"📊 {home['name']} vs {away['name']} — {selected['fixture']['date'][:10]}")

    stats_home = get_team_stats(league_id, home["id"])
    stats_away = get_team_stats(league_id, away["id"])

    if not stats_home or not stats_away:
        st.error("Unable to fetch team statistics. Check IDs or API quota.")
    else:
        home_score, home_metrics = compute_score(
            stats_home, location_score=1, player_avail=get_injury_ratio(home["id"]),
            manager_rate=get_manager_win_rate(stats_home)
        )
        away_score, away_metrics = compute_score(
            stats_away, location_score=0, player_avail=get_injury_ratio(away["id"]),
            manager_rate=get_manager_win_rate(stats_away)
        )

        total = home_score + away_score
        prob_home = (home_score / total) * 100
        prob_away = (away_score / total) * 100
        diff = abs(prob_home - prob_away)

        # --- RESULTS ---
        col1, col2, col3 = st.columns([1.5, 1.5, 1])
        with col1:
            st.metric(label=f"{home['name']} Win Chance", value=f"{prob_home:.1f}%")
        with col2:
            st.metric(label=f"{away['name']} Win Chance", value=f"{prob_away:.1f}%")
        with col3:
            if diff < 10:
                st.metric(label="Prediction", value="Draw", delta=f"Low confidence")
            elif prob_home > prob_away:
                st.metric(label="Prediction", value=home["name"], delta=f"{diff:.1f}% advantage")
            else:
                st.metric(label="Prediction", value=away["name"], delta=f"{diff:.1f}% advantage")

        # --- CHARTS ---
        st.markdown("### 📈 Radar Comparison")
        categories = list(home_metrics.keys())
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=list(home_metrics.values()), theta=categories,
                                      fill='toself', name=home["name"]))
        fig.add_trace(go.Scatterpolar(r=list(away_metrics.values()), theta=categories,
                                      fill='toself', name=away["name"]))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### ⚽ Goals Scored vs Conceded")
        df_goals = pd.DataFrame({
            "Team": [home["name"], away["name"]],
            "Goals Scored": [
                stats_home["goals"]["for"]["total"]["total"],
                stats_away["goals"]["for"]["total"]["total"]
            ],
            "Goals Conceded": [
                stats_home["goals"]["against"]["total"]["total"],
                stats_away["goals"]["against"]["total"]["total"]
            ]
        })
        fig2 = px.bar(df_goals, x="Team", y=["Goals Scored", "Goals Conceded"],
                      barmode="group", title="Goals Comparison")
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Select a fixture or enter team IDs to start analysis.")
