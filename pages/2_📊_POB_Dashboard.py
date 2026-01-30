import streamlit as st

# Safety gate
import streamlit_authenticator as stauth
import copy

# 🔑 Convert secrets to mutable dict
config = copy.deepcopy(st.secrets)

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