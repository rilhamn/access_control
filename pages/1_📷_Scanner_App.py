# --- Page title: 📷 Scanner ---
# --- Description: Scan QR codes for entry logging ---

import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import pandas as pd
from datetime import datetime
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
# 📷 UI
# ===============================

st.title("📷 Scanner App")

status_box = st.empty()

qr_detector = cv2.QRCodeDetector()


# ===============================
# 🎯 CAMERA SESSION KEY
# ===============================

if "cam_key" not in st.session_state:
    st.session_state.cam_key = 0


# ===============================
# 🎥 VIDEO PROCESSOR
# ===============================

class CodeStable(VideoTransformerBase):

    def __init__(self):
        self.saved = False

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")

        data, bbox, _ = qr_detector.detectAndDecode(img)

        # save only once per camera session
        if data and not self.saved:
            try:
                ts = datetime.utcnow().isoformat()

                supabase.table(TABLE_NAME).insert(
                    {
                        "code_value": data,
                        "code_type": "QRCODE",
                        "timestamp": ts,
                    }
                ).execute()

                status_box.success(f"✅ SAVED : {data}")

            except Exception as e:
                status_box.error(f"DB error: {e}")

            # freeze saving (video keeps running, user presses reset)
            self.saved = True

        if bbox is not None:
            pts = bbox.astype(int).reshape(-1, 2)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)
            cv2.putText(
                img,
                "QRCODE",
                (pts[0][0], pts[0][1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        return img


# ===============================
# 📹 CAMERA
# ===============================

ctx = webrtc_streamer(
    key=f"qr-scanner-{st.session_state.cam_key}",
    video_transformer_factory=CodeStable,
    media_stream_constraints={"video": True, "audio": False},
    async_processing=True,
    desired_playing_state=True
)


# ===============================
# 🔄 CONTROLS
# ===============================

if st.button("🔄 Reset / Resume"):
    st.session_state.cam_key += 1
    status_box.empty()
    st.rerun()


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
