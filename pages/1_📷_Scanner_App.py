# --- Page title: 📷 Scanner ---
# --- Description: Scan QR codes for entry logging ---

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
# UI
# ===============================

st.title("📷 Scanner App")

status_box = st.empty()

qr_detector = cv2.QRCodeDetector()


# ===============================
# 🎥 VIDEO PROCESSOR
# ===============================

class CodeStable(VideoTransformerBase):

    def __init__(self):
        self.last_code = None
        self.last_time = 0.0
        self.cooldown = 2.0

        # message for UI
        self.last_message = None
        self.last_message_ok = True

    def transform(self, frame):

        img = frame.to_ndarray(format="bgr24")

        data, bbox, _ = qr_detector.detectAndDecode(img)
        now = time.time()

        if data:
            if data != self.last_code or (now - self.last_time) > self.cooldown:

                try:
                    supabase.table(TABLE_NAME).insert(
                        {
                            "code_value": data,
                            "code_type": "QRCODE",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ).execute()

                    # store message in the transformer instance
                    self.last_message = f"Saved : {data}"
                    self.last_message_ok = True

                    self.last_code = data
                    self.last_time = now

                except Exception as e:
                    self.last_message = str(e)
                    self.last_message_ok = False

        if bbox is not None:
            pts = bbox.astype(int).reshape(-1, 2)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)

        return img


# ===============================
# 📹 CAMERA
# ===============================

ctx = webrtc_streamer(
    key="qr-scanner-continuous",
    video_transformer_factory=CodeStable,
    media_stream_constraints={"video": True, "audio": False},
    async_processing=True,
    desired_playing_state=True
)


# ===============================
# 🔔 SHOW NOTIFICATION (SAFE)
# ===============================

if ctx and ctx.video_transformer:

    msg = ctx.video_transformer.last_message

    if msg:
        if ctx.video_transformer.last_message_ok:
            status_box.success("✅ " + msg)
        else:
            status_box.error("❌ " + msg)


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
