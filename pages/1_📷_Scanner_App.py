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

        if bbox is not None:
            pts = bbox.astype(int).reshape(-1, 2)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)

        return img


# ===============================
# 🎛 CAMERA SELECT (browser picker)
# ===============================

st.subheader("🎛 Camera")

if st.button("🔄 Change camera (open browser picker)"):
    # changing key forces reconnection → browser shows camera chooser
    st.session_state.webrtc_key = str(time.time())

if "webrtc_key" not in st.session_state:
    st.session_state.webrtc_key = "qr"


# ===============================
# 📹 CAMERA
# ===============================

ctx = webrtc_streamer(
    key=st.session_state.webrtc_key,
    video_transformer_factory=QRProcessor,
    media_stream_constraints={
        "video": True,
        "audio": False
    },
    async_processing=True
)


# ===============================
# ✅ DECISION UI
# ===============================

if st.session_state.pending_qr:

    st.warning("QR detected:")
    st.code(st.session_state.pending_qr)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ YES – insert to Supabase"):

            try:
                supabase.table(TABLE_NAME).insert(
                    {
                        "code_value": st.session_state.pending_qr,
                        "code_type": "QRCODE",
                        "timestamp": datetime.utcnow().isoformat(),
                        "result": "OK"
                    }
                ).execute()

                st.success("Saved")

            except Exception as e:
                st.error(e)

            # release freeze
            st.session_state.pending_qr = None
            st.session_state.freeze_scan = False
            st.experimental_rerun()

    with col2:
        if st.button("❌ NO – cancel"):

            st.info("Canceled")

            st.session_state.pending_qr = None
            st.session_state.freeze_scan = False
            st.experimental_rerun()


# ===============================
# 📊 TABLE VIEW
# ===============================

st.subheader("📄 Recorded Access Logs")

try:
    records = (
        supabase
        .table(TABLE_NAME)
        .select("*")
        .order("timestamp", desc=True)
        .limit(30)
        .execute()
    )

    df = pd.DataFrame(records.data)
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Failed to load data: {e}")


# ===============================
# 🚪 LOGOUT
# ===============================

authenticator.logout("Logout", "main")
