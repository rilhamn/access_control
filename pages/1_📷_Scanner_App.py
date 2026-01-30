# --- Page title: 📷 Scanner ---
# --- Page icon: camera ---
# --- Page description: Scan QR codes for entry logging --

import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import pandas as pd
from datetime import datetime
import os
from pyzbar.pyzbar import decode

# Safety gate
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

config = st.secrets

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"]
)

if st.session_state.get("username") != "scanner":
    st.stop()

st.title("📷 Scanner App")

CSV_FILE = "access_records.csv"

class CodeStable(VideoTransformerBase):
    def __init__(self):
        self.paused = False
        self.saved = False

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")

        if self.paused:
            return img

        decoded_objects = decode(img)

        for obj in decoded_objects:
            data = obj.data.decode("utf-8")
            code_type = obj.type  # QRCODE, CODE128, EAN13, etc.

            if not self.saved:
                df = pd.read_csv(CSV_FILE)

                if data in df["code_value"].values:
                    status_box.error(f"❌ ALREADY RECORDED: {data}")
                else:
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.loc[len(df)] = [data, code_type, ts]
                    df.to_csv(CSV_FILE, index=False)
                    status_box.success(f"✅ SAVED ({code_type}): {data} @ {ts}")

                self.saved = True
                self.paused = True

            # draw bounding box
            x, y, w, h = obj.rect
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                img,
                f"{code_type}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

            break  # only process ONE code per frame

        return img


ctx = webrtc_streamer(
    key="code-stable",
    video_transformer_factory=CodeStable,
    media_stream_constraints={"video": True, "audio": False},
    )

if st.button("🔄 Reset / Resume"):
    if ctx.video_transformer:
        ctx.video_transformer.paused = False
        ctx.video_transformer.saved = False

st.subheader("Recorded Access Codes")
st.dataframe(pd.read_csv(CSV_FILE))

# ✅ Logout only AFTER login
authenticator.logout("Logout", "main")


