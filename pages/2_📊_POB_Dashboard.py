import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

if st.session_state.get("username") != "viewer":
    st.stop()

st.write("📊 POB Dashboard")

# ✅ Logout only AFTER login
authenticator.logout("Logout", "main")