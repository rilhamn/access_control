# --- Page title: 📷 Scanner ---
# --- Description: Continuous QR scanner (no freeze, background insert)

import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import pandas as pd
from datetime import datetime
import time
import threading
import queue
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
# 🌐 WEBRTC (STUN)
# ===============================

RTC_CONFIGURATION = {
    "iceServers": [
        {"urls": ["stun:stun.l.google.com:19302"]},
    ]
}


# ===============================
# 🔁 GLOBAL QUEUE (IMPORTANT)
# ===============================

log_queue = queue.Queue()


# ===============================
# 🔁 BACKGROUND WORKER
# ===============================

def supabase_worker():
    while True:
        item = log_queue.get()
        if item is None:
            break
        try:
            supabase.table(TABLE_NAME).insert(item).execute()
        except Exception as e:
            print("Supabase insert error:", e)
        finally:
            log_queue.task_done()


if "worker_started" not in st.session_state:
    t = threading.Thread(target=supabase_worker, daemon=True)
    t.start()
    st.session_state.worker_started = True


# ===============================
# SESSION
# ===============================

if "webrtc_key" not in st.session_state:
    st.session_state.webrtc_key = "qr"


# ===============================
# UI
# ===============================

st.title("📷 Scanner App")

status_box = st.empty()

qr_detector = cv2.QRCodeDetector()


# ===============================
# 🎛 CAMERA PICKER
# ===============================

st.subheader("🎛 Camera")

if st.button("🔄 Change camera (browser picker)"):
    st.session_state.webrtc_key = str(time.time())
    st.rerun()


# ===============================
# 🎥 VIDEO PROCESSOR
# ===============================

class QRProcessor(VideoTransformerBase):

    def __init__(self):
        self.last_code = None
        self.last_time = 0.0
        self.cooldown = 2.0

        self.last_message = None
        self.last_ok = True

    def transform(self, frame):

        img = frame.to_ndarray(format="bgr24")

        data, bbox, _ = qr_detector.detectAndDecode(img)
        now = time.time()

        if data:
            if data != self.last_code or (now - self.last_time) > self.cooldown:

                try:
                    log_queue.put(
                        {
                            "code_value": data,
                            "code_type": "QRCODE",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                    self.last_message = f"Queued : {data}"
                    self.last_ok = True

                    self.last_code = data
                    self.last_time = now

                except Exception as e:
                    self.last_message = str(e)
                    self.last_ok = False

        if bbox is not None:
            pts = bbox.astype(int).reshape(-1, 2)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)

        return img


# ===============================
# 📹 CAMERA
# ===============================

ctx = webrtc_streamer(
    key=st.session_state.webrtc_key,
    video_transformer_factory=QRProcessor,
    rtc_configuration=RTC_CONFIGURATION,
    media_stream_constraints={
        "video": True,
        "audio": False
    },
    async_processing=True,
    desired_playing_state=True
)


# ===============================
# 🔔 STATUS
# ===============================

if ctx and ctx.video_transformer:

    msg = ctx.video_transformer.last_message

    if msg:
        if ctx.video_transformer.last_ok:
            status_box.success(msg)
        else:
            status_box.error(msg)


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
