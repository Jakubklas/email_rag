import streamlit as st

# Inject custom CSS for margins
site_margins ="""
    <style>
    /* only bump the MAIN content area, not the sidebar */
    [data-testid="stAppViewContainer"] > [data-testid="stMain"] {
        max-width: 80% !important;   /* 90% of the browser width */
        margin: 0 auto;              /* center it */
        padding-left: 0rem;
        padding-right: 0rem;
        padding-top: 0.1rem !important;         /* decreased top padding */
        margin-top: 0rem;            /* optional: zero top margin */
    }
    </style>
    """
