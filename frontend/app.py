import streamlit as st
import httpx
import uuid
import json
import urllib.parse
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

if "last_sources" not in st.session_state:
    st.session_state.last_sources = []

if "last_answer_type" not in st.session_state:
    st.session_state.last_answer_type = "chat"

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

try:
    rag_status = httpx.get(f"{BACKEND_URL}/rag/status", timeout=3)
    rag_status.raise_for_status()
    count = rag_status.json().get("vectors", 0)
    st.sidebar.success(f"📄 {count} policy chunks indexed")
    st.sidebar.caption("Leave Policy · Code of Conduct · Benefits Guide · Employee Handbook")
except Exception:
    st.sidebar.warning("⚠️ Document search unavailable")

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
        if message.get("sources"):
            st.caption(
                "📄 **Sources:** " +
                " · ".join(message["sources"])
            )
        if message.get("answer_type"):
            icon = "🔍" if message["answer_type"] == "rag" else "💬"
            label = "Company documents" if message["answer_type"] == "rag" \
                    else "General HR knowledge"
            st.caption(f"{icon} {label}")

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

# ── Streaming helpers ──────────────────────────────────────────────────────
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


def stream_rag(question: str, session_id: str):
    """Generator that streams tokens from the RAG streaming endpoint."""
    with httpx.stream(
        "POST",
        f"{BACKEND_URL}/rag/stream",
        json={"question": question, "session_id": session_id},
        timeout=60,
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                token = data.get("token", "")
                if token == "[DONE]":
                    break
                elif token == "[ERROR]":
                    break
                elif "sources" in data:
                    st.session_state.last_sources = data.get("sources", [])
                    st.session_state.last_chunks_used = data.get("chunks_used", 0)
                elif token:
                    yield token


# ── Chat input ─────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask ARIA anything about HR..."):
    st.session_state.last_sources = []
    st.session_state.last_answer_type = "chat"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Classify the query
    try:
        encoded = urllib.parse.quote(prompt)
        classify_response = httpx.get(
            f"{BACKEND_URL}/rag/classify?query={encoded}",
            timeout=10,
        )
        classification = classify_response.json().get("classification", "chat")
    except Exception:
        classification = "chat"

    st.session_state.last_answer_type = classification

    # Stream from the right endpoint
    with st.chat_message("assistant"):
        if classification == "rag":
            try:
                response_text = st.write_stream(
                    stream_rag(prompt, st.session_state.session_id)
                )
            except Exception as e:
                st.error(f"❌ Could not reach ARIA backend: {str(e)}")
                response_text = None

            if st.session_state.last_sources:
                st.caption(
                    "📄 **Sources:** " +
                    " · ".join(st.session_state.last_sources)
                )
            st.caption("🔍 Answered from company documents")
        else:
            try:
                response_text = st.write_stream(
                    stream_response(prompt, st.session_state.session_id)
                )
            except Exception as e:
                st.error(f"❌ Could not reach ARIA backend: {str(e)}")
                st.info("Make sure the backend is running on port 8000")
                response_text = None

            st.caption("💬 General HR knowledge")

    if response_text:
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text,
            "sources": st.session_state.last_sources,
            "answer_type": classification,
        })
