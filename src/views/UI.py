import streamlit as st
import openai
import os
from config import *
from src.tools.reconstruct_thread import create_llm_client
from src.views.CSS import *

# Set your OpenAI API key (replace with your key or use environment variable)
llm_client = create_llm_client()

st.set_page_config(page_title="Chatbot", layout="wide")
st.markdown(site_margins, unsafe_allow_html=True)

# Store chat history in session
if "messages" not in st.session_state:
    st.session_state.messages = []

# Define the column layout
column_1, column_2, column_3 = st.columns([3, 0.2, 2])

with column_1:
    st.title("RAG")
    st.divider()
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    prompt = st.chat_input("Say something...", accept_file=True)
    if prompt:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call OpenAI API
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    chat_response = llm_client.chat.completions.create(
                        model=QUERY_MODEL,
                        messages=[
                            {"role":"system",
                            "content":"Follow the instructions provided in the query text and briefly state your sources."},
                            {"role":"user", "content": prompt}
                        ],
                        temperature=0.2,
                    )
                
                    reply = chat_response.choices[0].message.content

                except Exception as e:
                    reply = f"Error: {e}"
                st.markdown(reply)

        # Save assistant reply
        st.session_state.messages.append({"role": "assistant", "content": reply})

with column_3:
    st.title("Content")
    st.divider()
    with st.container(border=False, height=500):
        with st.expander(label="Relevant_emails", expanded=True):
            st.write("This is where relevant context might be displayed.")

# python -m streamlit run src/views/UI.py
