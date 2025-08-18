import streamlit as st
import yaml
import os
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from streamlit_authenticator import Hasher


st.set_page_config(page_title="registration_page")

# Center column layout
_, middle, _ = st.columns([1, 3, 1])

# Load the YAML config
with open("auth.yaml") as file:
    auth = yaml.load(file, Loader=SafeLoader)

# Init the authenticator
authenticator = stauth.Authenticate(
    credentials=auth["credentials"],
    cookie_name=auth["cookie"]["name"],
    key=auth["cookie"]["key"],
    cookie_expiry_days=auth["cookie"]["expiry_days"],
    preauthorized_emails=auth.get("pre_authorized", {}).get("emails", []),
)

with middle:
    # Logo
    _, col, _ = st.columns([1, 3, 1])
    with col:
        st.image(
            os.path.join(os.getcwd(), "src", "views", "assets", "logo.png"),
            use_container_width=True
        )
        st.write("\n\n")

    # Make the Login button full-width
    st.markdown("""
    <style>
      #login_form button { width: 100% !important; }
    </style>
    """, unsafe_allow_html=True)

    try:
        registered = authenticator.register_user(key="register_form", merge_username_email=True)
        if registered is not None:
            email, username, name = registered
        else:
            email = username = name = None

        if st.button(label="Log In", use_container_width=True):
            st.session_state.auth_page = "login"
            st.rerun()

        if registered:
            st.success("User registered successfully! ✅")
            with open("auth.yaml", "w") as file:
                yaml.dump(auth, file, default_flow_style=False, allow_unicode=True)
            
            st.Page("src/views/register_page.py", title="Registration Page")

    except Exception as e:
        st.error(f"Registration error: {e}")


# python -m streamlit run src/views/register_page.py