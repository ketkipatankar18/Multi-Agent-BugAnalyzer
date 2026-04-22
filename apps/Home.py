# Import libraries
import streamlit as st
from streamlit_oauth import OAuth2Component

st.title("BugFinder: JIRA Issue Resolution RAG")

# Load OAuth credentials from secrets
client_id     = st.secrets["GOOGLE_CLIENT_ID"]
client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]

token = None

# Initialize OAuth2Component for Google login
oauth2 = OAuth2Component(
    client_id=client_id,
    client_secret=client_secret,
    authorize_endpoint="https://accounts.google.com/o/oauth2/auth",
    token_endpoint="https://oauth2.googleapis.com/token"
)

# Handle login flow
if 'token' not in st.session_state:
    result = oauth2.authorize_button(
        "Log in using Google",
        "http://localhost:8501",
        "openid email profile"
    )
    if result and 'token' in result:
        st.session_state.token = result.get('token')
        st.rerun()
else:
    token = st.session_state['token']

# ── Issue Input ────────────────────────────────────────────────────────────────
st.markdown("### Describe Your Issue")
issue_description = st.text_area(
    "What is the bug or issue you are facing?",
    placeholder="e.g. NullPointerException when sending HTTP POST request with empty body on Linux",
    height=150
)

# ── Priority ───────────────────────────────────────────────────────────────────
st.markdown("### Priority")
priority = st.selectbox(
    "What is the priority of this issue?",
    ["Blocker", "Critical", "Major", "Minor", "Trivial"]
)

# ── Submit ─────────────────────────────────────────────────────────────────────
if token and st.button("Find Similar Issues & Solutions"):
    if not issue_description.strip():
        st.warning("Please describe your issue before searching.")
    else:
        st.session_state["issue_description"] = issue_description
        st.session_state["priority"]           = priority
        st.switch_page("pages/GenerateSolution.py")