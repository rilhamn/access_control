# --- Page title: 📷 Scanner ---
# --- Description: Scan QR codes, freeze while assessing, then continue ---

import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import pandas as pd
from datetime import datetime
import time
import streamlit_authenticator as stauth
from supabase import create_client
import threading


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
        self.cooldown = 1.0

        self.processing = False     # <- freeze flag

        self.last_message = None
        self.last_message_ok = True


    def assess_and_store(self, data):
        """
        This runs in background thread.
        We freeze scanning while this runs.
        """

        try:
            # ---------------------------
            # 🔎 ASSESSMENT PLACE
            # ---------------------------
            # Example:
            # check if this QR already exists in last 5 minutes
            check = (
                supabase
                .table(TABLE_NAME)
                .select("id")
                .eq("code_value", data)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            allowed = True

            if check.data:
                last_time = pd.to_datetime(check.data[0]["timestamp"])
                if (pd.Timestamp.utcnow() - last_time).total_seconds() < 10:
                    allowed = False

            # ---------------------------
            # 📝 INSERT IF OK
            # ---------------------------
            if allowed:
                supabase.table(TABLE_NAME).insert(
                    {
                        "code_value": data,
                        "code_type": "QRCODE",
                        "timestamp": datetime.utcnow().isoformat(),
                        "result": "OK"
                    }
                ).execute()

                self.last_message = f"OK : {data}"
                self.last_message_ok = True
            else:
                self.last_message = f"DENIED : duplicate"
                self.last_message_ok = False

        except Exception as e:
            self.last_message = str(e)
            self.last_message_ok = False

        finally:
            # release freeze
            self.processing = False


    def transform(self, frame):

        img = frame.to_ndarray(format="bgr24")

        # ---------------------------
        # ⏸ freeze scan while assessing
        # ---------------------------
        if self.processing:
            return img

        data, bbox, _ = qr_detector.detectAndDecode(img)
        now = time.time()

        if data:
            if data != self.last_code or (now - self.last_time) > self.cooldown:

                # ---------------------------
                # freeze now
                # ---------------------------
                self.processing = True

                self.last_code = data
                self.last_time = now

                # run assessment in background
                t = threading.Thread(
                    target=self.assess_and_store,
                    args=(data,),
                    daemon=True
                )
                t.start()

        if bbox is not None:
            pts = bbox.astype(int).reshape(-1, 2)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)

        return img


# ===============================
# 📹 CAMERA
# ===============================

ctx = webrtc_streamer(
    key="qr-scanner-assess",
    video_transformer_factory=CodeStable,
    media_stream_constraints={"video": True, "audio": False},
    async_processing=True,
    desired_playing_state=True
)


# ===============================
# 🔔 STATUS
# =========================
