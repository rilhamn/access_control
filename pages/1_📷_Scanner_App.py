# --- Page title: 📷 Scanner ---
# --- Description: Scan QR codes for entry logging ---

import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import time
from datetime import datetime
import pandas as pd
import streamlit_authenticator as stauth
from supabase import create_client


# ===============================
# 🔐 AUTH
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

if "camera_on" not in st.session_state:
    st.session_state.camera_on = False

if "pending_code" not in st.session_state:
    st.session_state.pending_code = None

if "last_seen_time" not in st.session_state:
    st.session_state.last_seen_time = 0.0


# ===============================
# UI
# ===============================

st.title("📷 Scanner App")

status_box = st.empty()

qr_detector = cv2.QRCodeDetector()


# ===============================
# ▶️ START BUTTON
# ===============================

if not st.session_state.camera_on:
    if st.button("▶️ Start camera"):
        st.session_state.camera_on = True
        st.rerun()


# ===============================
# 🎥 VIDEO PROCESSOR
# ===============================

class QRProcessor(VideoTransformerBase):

    def transform(self, frame):

        img = frame.to_ndarray(format="bgr24")

        # if waiting for user decision, do not detect new QR
        if st.session_state.pending_code is not None:
            return img

        data, bbox, _ = qr_detector.detectAndDecode(img)

        now = time.time()

        # simple debounce (avoid detecting same frame 100x)
        if data and (now - st.session_state.last_seen_time) > 1.5:
            st.session_state.pending_code = data
            st.session_state.last_seen_time = now

        if bbox is not None:
            pts = bbox.astype(int).reshape(-1, 2)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)

        return img


# ===============================
# 📹 CAMERA
# ===============================

if st.session_state.camera_on:

    webrtc_streamer(
        key="qr-scanner-confirm",
        video_transformer_factory=QRProcessor,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
        desired_playing_state=True,
    )


# ===============================
# ✅ CONFIRM PANEL
# ===============================

if st.session_state.pending_code:

    st.markdown("---")
    st.subheader("QR detected")

    st.write("Code:")
    st.code(st.session_state.pending_code)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Record", use_container_width=True):
            try:
                supabase.table(TABLE_NAME).insert({
                    "code_value": st.session_state.pending_code,
                    "code_type": "QRCODE",
                    "timestamp": datetime.utcnow().isoformat()
                }).execute()

                status_box.success(
                    f"Saved : {st.session_state.pending_code}"
                )

            except Exception as e:
                status_box.error(e)

            # continue scanning
            st.session_state.pending_code = None
            st.rerun()

    with col2:
        if st.button("❌ Ignore", use_container_width=True):
            status_box.info("Ignored")

            st.session_state.pending_code = None
            st.rerun()


# ===============================
# 📊 TABLE VIEW
# ===============================

st.markdown("---")
st.subheader("📄 Recorded Access Logs (latest 20)")

try:
    records = (
        supabase
        .table(TABLE_NAME)
        .select("*")
        .order("timestamp", desc=True)
        .limit(20)
        .execute()
    )

    df = pd.DataFrame(records.data)
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(e)


# ===============================
# 🚪 LOGOUT
# ===============================

authenticator.logout("Logout", "main")
