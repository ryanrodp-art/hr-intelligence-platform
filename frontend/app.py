import streamlit as st
import httpx
import uuid
from datetime import datetime

BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="ARIA — HR Intelligence Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# ── Sidebar ────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ ARIA Configuration")
st.sidebar.divider()

try:
    response = httpx.get(f"{BACKEND_URL}/health", timeout=3)
    response.raise_for_status()
    st.sidebar.success("✅ Backend Connected")
    st.sidebar.caption(f"Version: {response.json()['version']}")
except Exception:
    st.sidebar.error("❌ Backend Offline")
    st.sidebar.caption("Start: uv run uvicorn backend.main:app --reload --port 8000")

st.sidebar.divider()
st.sidebar.markdown("**Session ID**")
st.sidebar.caption(st.session_state.session_id)
st.sidebar.divider()

if st.sidebar.button("🗑️ Clear Conversation"):
    st.session_state.messages = []
    st.session_state.session_id = str(uuid.uuid4())
    st.rerun()

# ── Main area ──────────────────────────────────────────────────────────────
st.title("🤖 ARIA")
st.caption("HR Intelligence Assistant — Powered by GenAI")
st.divider()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Welcome message shown only when conversation is empty
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write("Hello! I'm ARIA, your HR Intelligence Assistant. I'm here to help you with:")
        st.markdown(
            "- 📋 HR policies and procedures\n"
            "- 🏖️ Leave requests and balances\n"
            "- 👥 Employee information\n"
            "- 📚 Company guidelines\n"
            "- 🎯 Onboarding assistance"
        )
        st.write("What can I help you with today?")

# ── Chat input ─────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask ARIA anything about HR...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("ARIA is thinking..."):
                response = httpx.post(
                    f"{BACKEND_URL}/chat",
                    json={"message": prompt, "session_id": st.session_state.session_id},
                    timeout=30,
                )
                response.raise_for_status()

            response_text = response.json()["response"]
            st.write(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})

        except Exception as e:
            st.error(f"❌ Could not reach ARIA backend: {str(e)}")
            st.info("Make sure the backend is running on port 8000")
