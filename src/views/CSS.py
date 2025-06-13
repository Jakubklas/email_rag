import streamlit as st

# Inject custom CSS for margins
site_margins ="""
    <style>
    /* only bump the MAIN content area, not the sidebar */
    [data-testid="stAppViewContainer"] > [data-testid="stMain"] {
        max-width: 90% !important;   /* 80% of the browser width */
        margin: 0 auto;              /* centre it */
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """