import streamlit as st
import yaml
import os
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities.exceptions import LoginError

st.set_page_config(page_title="Login / Register", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "login"

# --- Load auth config ---

config_path = os.path.join(os.getcwd(), "auth.yaml")
with open(config_path, "r", encoding="utf-8-sig") as f:
    auth_cfg = yaml.safe_load(f)


# --- Init the authenticator ---
authenticator = stauth.Authenticate(
    credentials=auth_cfg["credentials"],
    cookie_name=auth_cfg["cookie"]["name"],
    key=auth_cfg["cookie"]["key"],
    cookie_expiry_days=auth_cfg["cookie"]["expiry_days"],
    preauthorized_emails=auth_cfg.get("pre_authorized", {}).get("emails", []),
)

# --- Center column for layout ---
_, mid, _ = st.columns([2, 1.5, 2])


# ------- LOGIN FORM ---------------------------


with mid:
    _, col, _ = st.columns([1, 1., 1])
    with col:
        logo_path = os.path.join("src", "views", "assets", "logo.png")
        if os.path.exists(logo_path):
            pass
            # st.image(logo_path, use_container_width=True)
        st.write(" ")   




if st.session_state.page == "login":
    with mid:
        # --- 1) Clear any stale/bad cookie on first render ---
        try:
            login_result = authenticator.login(location="main", key="login_form")
            if login_result:
                name, auth_status, username = login_result
            else:
                name = auth_status = username = None

        except LoginError:
            # Cookie pointed to a deleted user; clear session & rerun
            for k in ["authentication_status", "username", "name"]:
                st.session_state.pop(k, None)
            st.rerun()

        if auth_status is None:
            if st.button("Register", use_container_width=True):
                st.session_state.page = "register"
                st.rerun()
            if st.button("Log Out", use_container_width=True):
                try:
                    authenticator.logout(location="unrendered", key="login_form")
                    st.rerun()
                except Exception:
                    pass

        if auth_status is True:
            st.success(f"👋 Welcome, **{name}**!")
            authenticator.logout(
                button_name="Log Out",
                location="main", 
                key="login_form", 
                use_container_width=True)
            st.rerun()

        elif auth_status is False:
            st.error("❌ Username or password is incorrect")

        


# ------- REGISTRATION FORM ---------------------------

if "just_registered" not in st.session_state:
    st.session_state.just_registered = False

# 2) Only run registration logic when we’re on the register page
if st.session_state.get("page") == "register":
    with mid:
        try:
            # this will display the registration form and return credentials tuple on success
            registered = authenticator.register_user(
                location="main",
                merge_username_email=True,
                key="register_form",
                captcha=False,
            )

            # always give a way to bail out to login
            if st.button("Log In", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()

            # 3) Only on a _new_ successful registration …
            if registered and not st.session_state.just_registered:
                email, new_username, new_name = registered
                st.success(f"✅ Registered {new_name} ({email})!")

                # —> **Make sure to copy the in-memory credentials into your config dict**
                auth_cfg["credentials"] = authenticator.credentials

                # now persist
                with open("auth.yaml", "w") as f:
                    yaml.dump(auth_cfg, f, default_flow_style=False, allow_unicode=True)

                st.info("You can now log in with your new credentials.")

                # finally, flip the flag so we don’t do this twice
                st.session_state.just_registered = True

        except Exception as e:
            st.error(f"Registration error: {e}")
            # still let them jump to login if they want
            if st.button("Log In", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()
            st.error(e)


# python -m streamlit run src/views/pages/login_page.py