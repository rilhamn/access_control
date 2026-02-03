# --- Page title: 📷 Scanner ---
# --- Description: Scan QR, ask before insert, choose camera from browser ---

import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import pandas as pd
from datetime import datetime
import time
import streamlit_authenticator as stauth
from supabase import create_client


# ===============================
# 🔐 AUTHENTICATION
# ===============================

config = {
    "credentials": {
        "usernames": {
            user: dict(st.secrets["credentials"]["usernames"][user])
            for user in st.secrets["credentials"]["usernames"]
        }
    },
    "cookie": dict(st.secrets["cookie"]),
}

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

if st.session_state.get("username") != "scanner":
    st.error("🚫 Scanner only")
    st.stop()


# ===============================
# 🌐 SUPABASE
# ===============================

supabase = create_client(
    st.secrets["supabase"]["url"],
    st.secrets["supabase"]["key"]
)

TABLE_NAME = "access_logs"


# ===============================
# STATE
# ===============================

if "pending_qr" not in st.session_state:
    st.session_state.pending_qr = None

if "freeze_scan" not in st.session_state:
    st.session_state.freeze_scan = False


# ===============================
# UI
# ===============================

st.title("📷 Scanner App")

status_box = st.empty()

qr_detector = cv2.QRCodeDetector()


# ===============================
# 🎥 VIDEO PROCESSOR
# ===============================

class QRProcessor(VideoTransformerBase):

    def transform(self, frame):

        img = frame.to_ndarray(format="bgr24")

        # do not scan while waiting user decision
        if st.session_state.freeze_scan:
            return img

        data, bbox, _ = qr_detector.detectAndDecode(img)

        if data:
            # freeze and store QR in session
            st.session_state.pending_qr = data
            st.session_state.freeze_scan = True

        if bbox is not Non
