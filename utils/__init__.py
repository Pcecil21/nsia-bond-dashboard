"""NSIA Dashboard utilities."""
import streamlit as st


def ask_about_this(page_name: str):
    """Add an 'Ask about this' expander that redirects to Ask NSIA with page context.

    Usage (at the bottom of any page):
        from utils import ask_about_this
        ask_about_this("Financial Overview")
    """
    st.markdown("---")
    with st.expander("Ask a question about this data"):
        question = st.text_input(
            "What would you like to know?",
            key=f"ask_about_{page_name.replace(' ', '_').lower()}",
            placeholder=f"e.g., 'Explain the {page_name.lower()} numbers'",
        )
        if question:
            st.session_state["pending_question"] = question
            st.session_state["page_context"] = page_name
            st.switch_page("pages/19_Ask_NSIA.py")
