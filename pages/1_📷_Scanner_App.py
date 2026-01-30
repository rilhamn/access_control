# --- Page title: 📷 Scanner ---
# --- Description: Scan QR codes for entry logging ---

import streamlit as st

# Scanner
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import pandas as pd
from datetime import datetime
import os

# Safety gate
import streamlit_authenticator as stauth

# Database
from supabase import create_client

# ===============================
# 🔐 AUTHENTICATION (Cloud-safe)
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

# 🔒 Page protection
if st.session_state.get("username") != "scanner":
    st.error("🚫 Access denied")
    st.stop()


# ===============================
# 🌐 SUPABASE SETUP
# ===============================

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase: "Client" = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE_NAME = "access_logs"

# ===============================
# 📷 SCANNER SETUP
# ===============================

st.title("📷 Scanner App")
status_box = st.empty()
qr_detector = cv2.QRCodeDetector()

# ===============================
# 🎥 VIDEO PROCESSOR
# ===============================

class CodeStable(VideoTransformerBase):
    def __init__(self):
        self.paused = False
        self.saved = False

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")

        if self.paused:
            return img

        data, bbox, _ = qr_detector.detectAndDecode(img)

        if data and not self.saved:
            df = pd.read_csv(CSV_FILE)

            if data in df["code_value"].values:
                status_box.error(f"❌ ALREADY RECORDED: {data}")
            else:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.loc[len(df)] = [data, "QRCODE", ts]
                df.to_csv(CSV_FILE, index=False)
                status_box.success(f"✅ SAVED (QRCODE): {data}")

            self.saved = True
            self.paused = True

        # Draw bounding box
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
    key="qr-scanner",
    video_transformer_factory=CodeStable,
    media_stream_constraints={"video": True, "audio": False},
)

# ===============================
# 🔄 CONTROLS
# ===============================

if st.button("🔄 Reset / Resume"):
    if ctx.video_transformer:
        ctx.video_transformer.paused = False
        ctx.video_transformer.saved = False
        status_box.empty()

# ===============================
# 📊 DATA VIEW
# ===============================

st.subheader("📄 Recorded Access Logs")

records = supabase.table(TABLE_NAME).select("*").order("timestamp", desc=True).execute()
df = pd.DataFrame(records.data)
st.dataframe(df, use_container_width=True)

# ===============================
# 🚪 LOGOUT
# ===============================

authenticator.logout("Logout", "main")
