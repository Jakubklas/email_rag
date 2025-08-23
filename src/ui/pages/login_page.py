import streamlit as st
import yaml
import os
import base64
import bcrypt


if "page" not in st.session_state:
    st.session_state.page = "login"
if "current_page" not in st.session_state:
    st.session_state.current_page = "login"

# Load auth.yaml file
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

# Login form
_, mid, _ = st.columns([1, 1, 1])
with mid:
    with st.form("login_form", clear_on_submit=False):
        st.subheader("Sign In")
        username = st.text_input("Username or Email", placeholder="admin or your.email@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        submitted = st.form_submit_button("Sign In", use_container_width=True)
        
        # Check the inputted credentials
        if submitted:
            if username and password:
                user_data = auth_cfg["credentials"]["usernames"].get(username)
                if user_data:
                    try:
                        stored_password = user_data["password"]
                        is_valid = bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))
                    except:
                        is_valid = False
                    
                    # Set auth state
                    if is_valid:
                        st.session_state.authentication_status = True
                        st.session_state.username = username
                        st.session_state.name = user_data["name"]
                        st.success(f"Welcome, {user_data['name']}!")
                        st.rerun()
                    else:
                        st.error("Incorrect email or password")
                else:
                    st.error("Incorrect email or password")
            else:
                st.error("Please enter both username and password")
    
    # Register button
    if st.button("Register", key="register_button", use_container_width=True):
        st.session_state.current_page = "register"
        st.rerun()

