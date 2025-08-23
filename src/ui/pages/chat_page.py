import os
import base64
import streamlit as st

from config.config import *
from src.querying.query_service import QueryService


# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_service" not in st.session_state:
    st.session_state.query_service = QueryService()

# Asset paths
ASSETS_DIR = os.path.join(os.getcwd(), "src", "ui", "assets")
USER_AVATAR_SRC = os.path.join(ASSETS_DIR, "user_avatar.png")
ASSISTANT_AVATAR_SRC = os.path.join(ASSETS_DIR, "bot_avatar.png")
LOGO_SRC = os.path.join(ASSETS_DIR, "logo.png")

# Logout button in top right corner
with st.container():
    st.markdown(
        """
        <style>
        .logout-container {
            position: fixed;
            top: 10px;
            right: 20px;
            z-index: 999;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    _, _, top_right = st.columns([8, 1, 1])
    with top_right:
        if st.button("Logout", type="secondary", key="logout_chat"):
            for key in ["authentication_status", "username", "name"]:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.session_state.messages = []
            st.session_state.current_page = "login"
            st.rerun()

# Show logo & tagline
st.markdown(
    f"""
    <div style="text-align: center; margin-top: 20px;">
        <img src="data:image/png;base64,{base64.b64encode(open(LOGO_SRC, "rb").read()).decode()}" width="250">
        <br><br>
        <p>Ask me anything - I'll do my best to find the<br>answer in your email history.</p>
        <br>
    </div>
    """,
    unsafe_allow_html=True
)

# Show input bar & process user query
user_input = st.chat_input("Ask anything...", key="chat_input")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.spinner("Looking for answers...", show_time=True):
        try:
            retrieved_ids = []
            prompt, response, memory, retrieved_ids, query_embeddings = st.session_state.query_service.answer_query(user_input, retrieved_ids)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            st.error(f"Error processing query: {e}")
            st.session_state.messages.append({"role": "assistant", "content": "Error processing request."})

# Show chat messages
for msg in st.session_state.messages:
    role = msg["role"]
    avatar = USER_AVATAR_SRC if role == "user" else ASSISTANT_AVATAR_SRC
    
    with st.chat_message(role, avatar=avatar):
        st.write(msg["content"])