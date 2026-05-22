import streamlit as st
import httpx
import uuid
import json
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

# ── Streaming helper ───────────────────────────────────────────────────────
def stream_response(prompt: str, session_id: str):
    """Generator that streams tokens from the FastAPI streaming endpoint."""
    with httpx.stream(
        "POST",
        f"{BACKEND_URL}/chat/stream",
        json={"message": prompt, "session_id": session_id},
        timeout=60,
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                token = data.get("token", "")
                if token and token != "[DONE]" and token != "[ERROR]":
                    yield token


# ── Chat input ─────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask ARIA anything about HR...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            response_text = st.write_stream(
                stream_response(prompt, st.session_state.session_id)
            )
        except Exception as e:
            st.error(f"❌ Could not reach ARIA backend: {str(e)}")
            st.info("Make sure the backend is running on port 8000")
            response_text = None

    if response_text:
        st.session_state.messages.append({"role": "assistant", "content": response_text})
