# --- Page title: 📷 Scanner ---
# --- Description: Scan QR codes, freeze while assessing, then continue ---

import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import pandas as pd
from datetime import datetime
import time
import threading
import streamlit_authenticator as stauth
from supabase import create_client

# 🔁 force UI refresh (important for background thread status)
from streamlit_autorefresh import st_autorefresh


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
# 🔁 AUTO UI REFRESH
# ===============================
# every 500 ms
st_autorefresh(interval=500, key="scanner_refresh")


# ===============================
# 🎛 CAMERA CONFIG
# ===============================

st.subheader("🎛 Camera configuration")

if "facing_mode" not in st.session_state:
    st.session_state.facing_mode = "environment"

if st.button("🔁 Switch camera (front / back)"):
    st.session_state.facing_mode = (
        "user"
        if st.session_state.facing_mode == "environment"
        else "environment"
    )
    st.rerun()

st.caption(f"Current camera mode: {st.session_state.facing_mode}")


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
        self.cooldown = 1.5

        self.processing = False

        self.last_message = None
        self.last_message_ok = True


    def assess_and_store(self, data):

        try:
            # -------------------------
            # example assessment
            # -------------------------
            allowed = True

            # prevent same QR within 10 seconds
            check = (
                supabase
                .table(TABLE_NAME)
                .select("timestamp")
                .eq("code_value", data)
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if check.data:
                last_ts = pd.to_datetime(check.data[0]["timestamp"])
                if (pd.Timestamp.utcnow() - last_ts).total_seconds() < 10:
                    allowed = False

            # -------------------------
            # insert or reject
            # -------------------------
            if allowed:
                supabase.table(TABLE_NAME).insert(
                    {
                        "code_value": data,
                        "code_type": "QRCODE",
                        "timestamp": datetime.utcnow().isoformat(),
                        "result": "OK"
                    }
                ).execute()

                self.last_message = f"✅ OK : {data}"
                self.last_message_ok = True

            else:
                self.last_message = "❌ DENIED : duplicate scan"
                self.last_message_ok = False

        except Exception as e:
            self.last_message = str(e)
            self.last_message_ok = False

        finally:
            self.processing = False


    def transform(self, frame):

        img = frame.to_ndarray(format="bgr24")

        # ⏸ freeze scanning while assessing
        if self.processing:
            return img

        data, bbox, _ = qr_detector.detectAndDecode(img)
        now = time.time()

        if data:
            if data != self.last_code or (now - self.last_time) > self.cooldown:

                self.processing = True
                self.last_code = data
                self.last_time = now

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
    media_stream_constraints={
        "video": {
            "facingMode": st.session_state.facing_mode
        },
        "audio": False,
    },
    async_processing=True,
    desired_playing_state=True
)


# ===============================
# 🔔 STATUS
# ===============================

if ctx and ctx.video_transformer:

    vt = ctx.video_transformer

    if vt.processing:
        status_box.info("⏳ Assessing...")

    if vt.last_message:
        if vt.last_message_ok:
            status_box.success(vt.last_message)
        else:
            status_box.error(vt.last_message)


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

    if records.data:
        df = pd.DataFrame(records.data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No data yet.")

except Exception as e:
    st.error(f"Failed to load data: {e}")


# ===============================
# 🚪 LOGOUT
# ===============================

authenticator.logout("Logout", "main")
