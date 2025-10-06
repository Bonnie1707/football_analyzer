import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Football Team Comparison", layout="wide")

st.title("⚽ Football Head-to-Head Analyzer")
st.write("Compare two competing teams across performance, form, goals, and injuries — powered by API-Football data.")

# --- API SETUP ---
API_KEY = st.secrets["API_KEY"]
BASE_URL = "https://v3.football.api-sports.io"
headers = {"x-apisports-key": API_KEY}

# --- SIDEBAR INPUTS ---
st.sidebar.header("Team Selection")
league_id = st.sidebar.text_input("Enter League ID (e.g., 39 for Premier League)", "39")
team1_id = st.sidebar.text_input("Enter Team 1 ID (e.g., 33 for Manchester United)", "33")
team2_id = st.sidebar.text_input("Enter Team 2 ID (e.g., 50 for Manchester City)", "50")

# --- FETCH FUNCTIONS ---
def get_team_stats(league_id, team_id):
    url = f"{BASE_URL}/teams/statistics?league={league_id}&season=2023&team={team_id}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    if "response" not in data or not data["response"]:
        return None
    return data["response"]

def get_team_injuries(team_id):
    url = f"{BASE_URL}/injuries?season=2023&team={team_id}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("response", [])

# --- COMPARISON ---
if st.sidebar.button("Compare Teams"):
    team1_data = get_team_stats(league_id, team1_id)
    team2_data = get_team_stats(league_id, team2_id)

    if not team1_data or not team2_data:
        st.error("Failed to fetch team data. Check IDs and API key.")
    else:
        # --- Team Info ---
        team1_name = team1_data["team"]["name"]
        team2_name = team2_data["team"]["name"]

        st.subheader(f"🏆 {team1_name} vs {team2_name}")

        col1, col2 = st.columns(2)

        # --- Team 1 Overview ---
        with col1:
            fixtures = team1_data["fixtures"]
            goals = team1_data["goals"]
            form = team1_data.get("form", "No data")

            st.write(f"### {team1_name}")
            st.write(f"Form: {form}")
            wins, draws, losses = fixtures["wins"]["total"], fixtures["draws"]["total"], fixtures["loses"]["total"]

            df1 = pd.DataFrame({
                "Result": ["Wins", "Draws", "Losses"],
                "Count": [wins, draws, losses]
            })
            fig1 = px.pie(df1, names="Result", values="Count", title=f"{team1_name} Results")
            st.plotly_chart(fig1, use_container_width=True)

            st.metric(label="Goals Scored", value=goals["for"]["total"]["total"])
            st.metric(label="Goals Conceded", value=goals["against"]["total"]["total"])

        # --- Team 2 Overview ---
        with col2:
            fixtures = team2_data["fixtures"]
            goals = team2_data["goals"]
            form = team2_data.get("form", "No data")

            st.write(f"### {team2_name}")
            st.write(f"Form: {form}")
            wins, draws, losses = fixtures["wins"]["total"], fixtures["draws"]["total"], fixtures["loses"]["total"]

            df2 = pd.DataFrame({
                "Result": ["Wins", "Draws", "Losses"],
                "Count": [wins, draws, losses]
            })
            fig2 = px.pie(df2, names="Result", values="Count", title=f"{team2_name} Results")
            st.plotly_chart(fig2, use_container_width=True)

            st.metric(label="Goals Scored", value=goals["for"]["total"]["total"])
            st.metric(label="Goals Conceded", value=goals["against"]["total"]["total"])

        # --- Combined Comparison Chart ---
        st.subheader("📊 Head-to-Head Comparison")
        comp_df = pd.DataFrame({
            "Metric": ["Wins", "Draws", "Losses", "Goals Scored", "Goals Conceded"],
            team1_name: [
                team1_data["fixtures"]["wins"]["total"],
                team1_data["fixtures"]["draws"]["total"],
                team1_data["fixtures"]["loses"]["total"],
                team1_data["goals"]["for"]["total"]["total"],
                team1_data["goals"]["against"]["total"]["total"]
            ],
            team2_name: [
                team2_data["fixtures"]["wins"]["total"],
                team2_data["fixtures"]["draws"]["total"],
                team2_data["fixtures"]["loses"]["total"],
                team2_data["goals"]["for"]["total"]["total"],
                team2_data["goals"]["against"]["total"]["total"]
            ]
        })

        fig = go.Figure()
        fig.add_trace(go.Bar(x=comp_df["Metric"], y=comp_df[team1_name], name=team1_name))
        fig.add_trace(go.Bar(x=comp_df["Metric"], y=comp_df[team2_name], name=team2_name))
        fig.update_layout(barmode="group", title="Team Comparison Overview", xaxis_title="Metric", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

        # --- Injury Comparison ---
        st.subheader("🚑 Injury Report")
        inj1 = get_team_injuries(team1_id)
        inj2 = get_team_injuries(team2_id)

        c1, c2 = st.columns(2)
        with c1:
            st.write(f"### {team1_name} Injuries")
            if inj1:
                for p in inj1:
                    st.write(f"- {p['player']['name']} ({p['player']['type']}) - {p['player']['reason']}")
            else:
                st.write("✅ No reported injuries")

        with c2:
            st.write(f"### {team2_name} Injuries")
            if inj2:
                for p in inj2:
                    st.write(f"- {p['player']['name']} ({p['player']['type']}) - {p['player']['reason']}")
            else:
                st.write("✅ No reported injuries")

        # --- Simple Prediction ---
        st.subheader("📈 Match Prediction (Simplified)")
        team1_strength = (
            team1_data["fixtures"]["wins"]["total"] +
            team1_data["goals"]["for"]["total"]["total"] -
            team1_data["goals"]["against"]["total"]["total"]
        )
        team2_strength = (
            team2_data["fixtures"]["wins"]["total"] +
            team2_data["goals"]["for"]["total"]["total"] -
            team2_data["goals"]["against"]["total"]["total"]
        )

        total_strength = team1_strength + team2_strength
        if total_strength > 0:
            team1_chance = (team1_strength / total_strength) * 100
            team2_chance = (team2_strength / total_strength) * 100
            st.metric(label=f"{team1_name} Win Probability", value=f"{team1_chance:.1f}%")
            st.metric(label=f"{team2_name} Win Probability", value=f"{team2_chance:.1f}%")
        else:
            st.warning("Insufficient data for prediction.")
