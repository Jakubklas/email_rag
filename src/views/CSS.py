import streamlit as st

# Inject custom CSS for margins
site_margins ="""
    <style>
    /* only bump the MAIN content area, not the sidebar */
    [data-testid="stAppViewContainer"] > [data-testid="stMain"] {
        max-width: 90% !important;   /* 90% of the browser width */
        margin: 0 auto;              /* center it */
        padding-left: 2rem;
        padding-right: 2rem;
        padding-top: 0.1rem !important;         /* decreased top padding */
        margin-top: 0rem;            /* optional: zero top margin */
    }
    </style>
    """

chat_container = """
        <style>
        .scrollable-chat {
            height: 500px;
            overflow-y: auto;
            padding-right: 10px;
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            padding: 1rem;
            background-color: #f9f9f9;
        }
        </style>
    """