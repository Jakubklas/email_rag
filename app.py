import streamlit as st

# Page config
st.set_page_config(page_title="Email Assistant", layout="wide", page_icon="🤖")

def main():

    # Initiate session state & route elsewhere if user is authenticated
    if "current_page" not in st.session_state:
        st.session_state.current_page = "login"

    auth_status = st.session_state.get("authentication_status")
    
    if auth_status is True:
        # Show chat page
        exec(open("src/ui/pages/chat_page.py").read())
    elif st.session_state.current_page == "register":
        # Show registration page
        exec(open("src/ui/pages/register_page.py").read())
    else:
        # Show login Page
        exec(open("src/ui/pages/login_page.py").read())


if __name__ == "__main__":
    main()

# Command
# python -m streamlit run app.py