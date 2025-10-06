import streamlit as st

st.title("Secrets Test")

# Try to fetch your API key from Streamlit secrets
try:
    api_key = st.secrets["API_KEY"]
    st.success(f"✅ Secret key loaded successfully! Your key starts with: {api_key[:5]}...")
except KeyError:
    st.error("❌ API_KEY not found! Please add it under Secrets in Streamlit Cloud.")
except Exception as e:
    st.error(f"⚠️ Something else went wrong: {e}")
