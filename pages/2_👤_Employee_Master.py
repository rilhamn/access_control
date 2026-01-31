import streamlit as st
import streamlit_authenticator as stauth
from supabase import create_client
import pandas as pd


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

# Only admin can manage employee
if st.session_state.get("username") != "admin":
    st.error("🚫 Admin only")
    st.stop()


# ===============================
# 🌐 SUPABASE
# ===============================

supabase = create_client(
    st.secrets["supabase"]["url"],
    st.secrets["supabase"]["key"]
)

TABLE = "employee_master"


# ===============================
# ➕ ADD EMPLOYEE
# ===============================

st.title("👤 Employee Master")

with st.form("add_employee"):

    st.subheader("➕ Add employee")

    code_value = st.text_input("QR Code / Code Value")
    employee_name = st.text_input("Employee name")
    department = st.text_input("Department")
    company = st.text_input("Company")

    submitted = st.form_submit_button("Save")

    if submitted:
        if not code_value:
            st.error("Code value is required")
        else:
            try:
                supabase.table(TABLE).insert({
                    "code_value": code_value.strip(),
                    "employee_name": employee_name,
                    "department": department,
                    "company": company
                }).execute()

                st.success("Employee added")
                st.rerun()

            except Exception as e:
                st.error(e)


# ===============================
# 📋 VIEW EMPLOYEES
# ===============================

st.divider()
st.subheader("📋 Employee list")

try:
    res = supabase.table(TABLE).select("*").order("employee_name").execute()
    df = pd.DataFrame(res.data)

    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(e)
    df = pd.DataFrame()


# ===============================
# 🗑 DELETE EMPLOYEE
# ===============================

st.divider()
st.subheader("🗑 Delete employee")

if not df.empty:

    selected_code = st.selectbox(
        "Select employee (by code_value)",
        df["code_value"].tolist()
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        delete_btn = st.button("Delete")

    if delete_btn:
        try:
            supabase.table(TABLE)\
                .delete()\
                .eq("code_value", selected_code)\
                .execute()

            st.success(f"Deleted {selected_code}")
            st.rerun()

        except Exception as e:
            st.error(e)

else:
    st.info("No employee data yet.")


# ===============================
# 🚪 LOGOUT
# ===============================

authenticator.logout("Logout", "main")
