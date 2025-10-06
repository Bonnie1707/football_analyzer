import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Football Trends Analyzer", layout="wide")

st.title("⚽ Football Trends Analyzer")
st.write("Track team performance trends, visualize charts, and generate predictions using API-Football data.")

# --- API SETUP ---
API_KEY = st.secrets["API_KEY"]
BASE_URL = "https://v3.football.api-sports.io"

headers = {"x-apisports-key": API_KEY}

# --- SIDEBAR ---
st.sidebar.header("Select Team & League")
league_id = st.sidebar.text_input("Enter League ID (e.g., 39 for Premier League)", "39")
team_id = st.sidebar.text_input("Enter Team ID (e.g., 33 for Manchester United)", "33")

# --- FETCH DATA ---
def get_team_stats(league_id, team_id):
    url = f"{BASE_URL}/teams/statistics?league={league_id}&season=2023&team={team_id}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error("Failed to fetch data. Check your API key or team/league ID.")
        return None
    return r.json()

if st.sidebar.button("Analyze"):
    data = get_team_stats(league_id, team_id)
    if data:
        st.subheader("📊 Team Performance Overview")
        team_name = data["response"]["team"]["name"]
        fixtures = data["response"]["fixtures"]
        form = data["response"]["form"]

        st.write(f"**Team:** {team_name}")
        st.write(f"**Form (Last 5 Matches):** {form}")

        wins = fixtures["wins"]["total"]
        draws = fixtures["draws"]["total"]
        losses = fixtures["loses"]["total"]

        df = pd.DataFrame({
            "Result": ["Wins", "Draws", "Losses"],
            "Count": [wins, draws, losses]
        })

        fig = px.pie(df, names="Result", values="Count", title="Overall Team Results")
        st.plotly_chart(fig, use_container_width=True)

        # Prediction logic (simple trend)
        win_rate = (wins / (wins + draws + losses)) * 100
        st.metric(label="Estimated Win Probability (Next Match)", value=f"{win_rate:.1f}%")
