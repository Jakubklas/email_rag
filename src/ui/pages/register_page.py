import streamlit as st
import yaml
import os
import time
import base64
import streamlit_authenticator as stauth

# Session state
if "page" not in st.session_state:
    st.session_state.page = "register"

# Load auth config
config_path = os.path.join(os.getcwd(), "auth.yaml")
with open(config_path, "r", encoding="utf-8-sig") as f:
    auth_cfg = yaml.safe_load(f)

# Logo
LOGO_SRC = os.path.join(os.getcwd(), "src", "ui", "assets", "logo.png")
st.markdown(
    f"""
    <div style="text-align: center;">
        <img src="data:image/png;base64,{base64.b64encode(open(LOGO_SRC, "rb").read()).decode()}" width="250">
        <br>
        <br>
        <br>
    </div>
    """,
    unsafe_allow_html=True
)

# Registration form
_, mid, _ = st.columns([1, 1, 1])

# Start registration state
if "registration_complete" not in st.session_state:
    st.session_state.registration_complete = False

with mid:
    # Show reg form inly if not completed
    if not st.session_state.registration_complete:
        with st.form("register_form", clear_on_submit=False):
            st.subheader("Create Account")
            email = st.text_input("Email", placeholder="your.email@example.com")
            password = st.text_input("Password", type="password", placeholder="Enter a secure password")
            
            submitted = st.form_submit_button("Create Account", use_container_width=True)
            
            if submitted:
                if email and password and "@" in email:
                    # Hash the password
                    hasher = stauth.Hasher()
                    hashed_password = hasher.hash(password)
                    
                    # Save credentials to yaml
                    auth_cfg["credentials"]["usernames"][email] = {
                        "email": email,
                        "name": email.split("@")[0].title(),
                        "password": hashed_password
                    }
                    with open(config_path, "w") as f:
                        yaml.dump(auth_cfg, f, default_flow_style=False, allow_unicode=True)
                    
                    st.session_state.registration_complete = True
                    st.rerun()
                else:
                    st.error("Email or password are invalid.")
    else:
        st.success("Registration completed!")
        with st.spinner("Taking you back to login..."):
            st.session_state.current_page = "login"
            time.sleep(3)
            st.rerun()

    # Back to login
    if st.button("Back to Login", key="back_to_login", use_container_width=True):
        st.session_state.current_page = "login"
        st.session_state.registration_complete = False
        