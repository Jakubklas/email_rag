import os
import base64
import html
import time

import streamlit as st

from config import *
from src.services.querying import answer_query, Memory, create_llm_client, create_os_client


# ---- Session state for messages ----
if "messages" not in st.session_state:
    st.session_state.messages = []
if "llm_client" not in st.session_state:
    st.session_state.llm_client = create_llm_client()
if "os_client" not in st.session_state:
    st.session_state.os_client = create_os_client()
if "memory" not in st.session_state:
  st.session_state.memory = Memory(
      llm_client= st.session_state.llm_client,
      os_client= st.session_state.os_client,
      short_term_tokens=1000,
      mid_term_turns=3,
      memory_model=MEMORY_MODEL,
      embeddings_model=EMBEDDINGS_MODEL
  )

# ---- Page config ----
st.set_page_config(page_title="Chatbot", layout="wide")

# ---- Asset paths & avatar loader ----
BASE_DIR   = os.path.dirname(os.path.realpath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

def load_avatar_as_data_uri(path: str) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except Exception as e:
        st.error(f"Could not load avatar image at {path}: {e}")
        return ""

USER_AVATAR_SRC      = load_avatar_as_data_uri(os.path.join(os.getcwd(), "src", "views", "assets", "user_avatar.png"))
ASSISTANT_AVATAR_SRC = load_avatar_as_data_uri(os.path.join(os.getcwd(), "src", "views", "assets", "bot_avatar.png"))
LOGO_SRC = os.path.join(os.getcwd(), "src", "views", "assets", "logo.png")

# ---- Logo ----
st.image(LOGO_SRC, width=250)

# ---- Custom CSS ----
st.markdown(
    """
<style>
  /* Container padding */
  .block-container {
    padding-left: 20% !important;
    padding-right: 20% !important;
  }

  /* Chat window */
  .scrollable-chat {
    background-color: #f5f5f5;
    border-radius: 10px;
    padding: 1.5rem;
    height: 60vh;
    overflow-y: auto;
  }
  .scrollable-chat::after {
    content: "";
    display: table;
    clear: both;
  }

  /* Scale up checkboxes & radios */
  div[data-testid="stCheckbox"],
  div[data-testid="stRadio"] {
    transform: scale(1.4);
    transform-origin: top left;
    margin-bottom: 0.5rem;
  }

  /* Chat row: vertical stack of label + body */
  .chat-row {
    display: flex;
    flex-direction: column;
    margin: 0.5rem 0;
  }
  .chat-row.user {
    align-items: flex-end;
  }
  .chat-row.assistant {
    align-items: flex-start;
  }

  /* Message label above bubble, aligned to outer edge */
  .chat-label {
    font-weight: bold;
    max-width: 75%;
    margin-bottom: 0.25rem;
  }
  .chat-label.user {
    text-align: right;
    margin-left: auto;
  }
  .chat-label.assistant {
    text-align: left;
    margin-right: auto;
  }

  /* Wrapper for avatar + bubble */
  .chat-body {
    display: flex;
    align-items: center;
    max-width: 75%;
  }
  .chat-row.user .chat-body {
    justify-content: flex-end;
  }
  .chat-row.assistant .chat-body {
    justify-content: flex-start;
  }

  /* Message bubbles */
  .msg-user,
  .msg-assistant {
    padding: 1rem;
    border-radius: 12px;
    word-wrap: break-word;
    margin: 0 0.5rem;
  }
  .msg-user {
    background-color: #bababa;
    text-align: right;
  }
  .msg-assistant {
    background-color: #e0e0e0;
    text-align: left;
  }

  /* Avatar images */
  .avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    object-fit: cover;
    margin: 0 8px;
  }

  /* Force toggle label flush with title line */
  .stToggle > label {
    display: block;
    margin-bottom: 0;
  }

  /* Prompt bar: same width as chat container (60vw), centered */
  [data-testid="stChatInput"] {
    max-width: 60vw;
    margin: 0 auto 1rem;
    box-sizing: border-box;
  }
</style>
    """,
    unsafe_allow_html=True,
)


st.title("Email Retrieval Assistant")

# ---- User input ----
user_input = st.chat_input("Say something…", key="chat_input")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.spinner("Looking for answers...", show_time=True):
        time.sleep(5)
        try:
            retrieved_ids = []
            prompt, response, mem_ctx, retrieved_ids, query_embeddings = answer_query(user_input, retrieved_ids=retrieved_ids, memory=st.session_state.memory)

        except Exception as e:
            raise e
            # response = f"❌ Error: {e}"
        st.session_state.messages.append({"role": "assistant", "content": response})

# ---- Render chat ----
chat_html = ['<div class="scrollable-chat" id="chat-container">']
for msg in st.session_state.messages:
    text    = html.escape(msg["content"]).replace("\n", "<br>")
    role    = msg["role"]
    row_cls = f"chat-row {role}"
    label   = "You:" if role == "user" else "Bot:"
    avatar  = USER_AVATAR_SRC if role == "user" else ASSISTANT_AVATAR_SRC
    bubble  = "msg-user" if role == "user" else "msg-assistant"

    chat_html.append(f'<div class="{row_cls}">')
    chat_html.append(f'  <div class="chat-label {role}">{label}</div>')
    chat_html.append('  <div class="chat-body">')
    if role == "assistant":
        chat_html.append(f'    <img src="{avatar}" class="avatar" />')
        chat_html.append(f'    <div class="{bubble}">{text}</div>')
    else:
        chat_html.append(f'    <div class="{bubble}">{text}</div>')
        chat_html.append(f'    <img src="{avatar}" class="avatar" />')
    chat_html.append('  </div>')
    chat_html.append('</div>')

# ---- Auto-scroll to bottom ----
# chat_html.append("""
# <script>
#   const chat = document.getElementById("chat-container");
#   if (chat) {
#     chat.scrollTo({ 
#       top: chat.scrollHeight,   // bottom of the scroll
#       behavior: 'smooth' 
#     });
#   }
# </script>
# """)
# chat_html.append('</div>')

st.markdown("".join(chat_html), unsafe_allow_html=True)


# python -m streamlit run src/views/UI.py
# streamlit run chat_page.py --server.port 8501 --server.enableCORS false --server.address 0.0.0.0