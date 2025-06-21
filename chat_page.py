import os
import base64
import time
import streamlit as st
from config import *
from src.services.querying import answer_query, Memory, create_llm_client, create_os_client


# --- Session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "llm_client" not in st.session_state:
    st.session_state.llm_client = create_llm_client()
if "os_client" not in st.session_state:
    st.session_state.os_client = create_os_client()
if "memory" not in st.session_state:
    st.session_state.memory = Memory(
        llm_client=st.session_state.llm_client,
        os_client=st.session_state.os_client,
        short_term_tokens=1000,
        mid_term_turns=3,
        memory_model=MEMORY_MODEL,
        embeddings_model=EMBEDDINGS_MODEL
    )

# --- Load images ---
def load_image_as_base64(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    return f"data:image/png;base64,{base64.b64encode(data).decode()}"

USER_AVATAR      = load_image_as_base64("src/views/assets/user_avatar.png")
ASSISTANT_AVATAR = load_image_as_base64("src/views/assets/bot_avatar.png")
LOGO_PATH        = "src/views/assets/logo.png"

# --- Layout config ---
st.set_page_config(page_title="Chatbot", layout="centered", page_icon=ASSISTANT_AVATAR)

# --- Logo ---
_, mid, _ = st.columns([1, 1.5, 1])
with mid:

    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.write(" ")
    st.image(LOGO_PATH, width=250, use_container_width=True)
    st.write(" ")
    st.markdown(
    """
    <p style='text-align: center; color: grey; font-size: 0.95rem;'>
        Ask me anything—I’ll do my best to find the answer in your email history, if it exists.
    </p>
    """,
    unsafe_allow_html=True
    )
    st.write(" ")
    st.write(" ")
    st.write(" ")

# --- Chat rendering ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR):
        st.markdown(msg["content"])

# --- Chat input ---
prompt = st.chat_input("Ask something...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    with st.spinner("Looking for answers...", show_time=True):
        try:
            retrieved_ids = []
            _, response, _, _, _ = answer_query(prompt, retrieved_ids=retrieved_ids, memory=st.session_state.memory)
        except Exception as e:
            response = f"❌ Error: {e}"

    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        st.markdown(response)