import streamlit as st
import streamlit_authenticator as stauth
from supabase import create_client


# ---------------------------
# Auth (same as your other page)
# ---------------------------

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

# Only admin (change username if needed)
if st.session_state.get("username") != "admin":
    st.error("🚫 Admin only")
    st.stop()


# ---------------------------
# Supabase
# ---------------------------

supabase = create_client(
    st.secrets["supabase"]["url"],
    st.secrets["supabase"]["key"]
)

TABLE = "employee_master"


# ---------------------------
# UI
# ---------------------------

st.title("👤 Employee Master Data")

with st.form("add_employee"):

    code_value = st.text_input("QR Code / Code Value")
    employee_name = st.text_input("Employee Name")
    department = st.text_input("Department")
    company = st.text_input("Company")

    submit = st.form_submit_button("Save")

    if submit:

        if not code_value:
            st.error("Code value is required")
        else:
            try:
                supabase.table(TABLE).insert({
                    "code_value": code_value,
                    "employee_name": employee_name,
                    "department": department,
                    "company": company
                }).execute()

                st.success("Employee saved")

            except Exception as e:
                st.error(e)


# ---------------------------
# View data
# ---------------------------

st.subheader("Employee list")

data = supabase.table(TABLE).select("*").order("employee_name").execute()
st.dataframe(data.data, use_container_width=True)


authenticator.logout("Logout", "main")
