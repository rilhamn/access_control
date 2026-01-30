import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

config = st.secrets

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"]
)

if st.session_state.get("username") != "viewer":
    st.stop()

st.write("📊 POB Dashboard")

# ✅ Logout only AFTER login
authenticator.logout("Logout", "main")