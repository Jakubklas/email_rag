import streamlit as st
import streamlit.components.v1 as components
from config import *
from src.tools.reconstruct_thread import create_llm_client
from src.services.querying import answer_query
from src.views.CSS import *

# OpenAI client
llm_client = create_llm_client()

st.set_page_config(page_title="Chatbot", layout="wide")

# Inject custom CSS for margins, alignment, and spacing
st.markdown(
    """
    <style>
    /* 15% padding on left and right of entire page */
    .block-container {
        padding-left: 20% !important;
        padding-right: 20% !important;
    }

    /* Right-align user prompts, left-align bot replies */
    .msg-user {
        text-align: right;
        margin: 1rem 0;      /* vertical spacing */
    }
    .msg-assistant {
        text-align: left;
        margin: 1rem 0;      /* vertical spacing */
    }

    /* Ensure the chat-input area inherits the same side-padding */
    [data-testid="stChatInput"] {
        padding-left: 20%;
        padding-right: 20%;
        box-sizing: border-box;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("Redcoat Express")

# Capture input first; this triggers a rerun automatically
user_input = st.chat_input("Say something…", key="chat_input")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    try:
        assistant_reply = answer_query(user_input, llm_client)
    except Exception as e:
        assistant_reply = f"Error: {e}"
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

# render messages
st.markdown('<div class="scrollable-chat">', unsafe_allow_html=True)

for msg in st.session_state.messages:
    text = msg["content"].replace("\n", "<br>")
    cls = "msg-user" if msg["role"] == "user" else "msg-assistant"
    label = "You:" if msg["role"] == "user" else "Bot:"
    st.markdown(f'<div class="{cls}"><b>{label}</b> {text}</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# auto-scroll JS
components.html(
    """
    <script>
      const chat = window.parent.document.querySelector('.scrollable-chat');
      if (chat) {
        chat.scrollTop = chat.scrollHeight;
      }
    </script>
    """,
    height=0,
    width=0,
)
