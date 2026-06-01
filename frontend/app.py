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

if "last_sql_used" not in st.session_state:
    st.session_state.last_sql_used = ""

if "last_row_count" not in st.session_state:
    st.session_state.last_row_count = 0

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

try:
    httpx.post(
        f"{BACKEND_URL}/agent/query",
        json={"question": "ping"},
        timeout=5,
    )
    st.sidebar.success("🤖 Agent: Online")
except Exception:
    st.sidebar.error("🤖 Agent: Offline")

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
        if message.get("answer_type") == "db":
            row_count = message.get("row_count", 0)
            sql = message.get("sql_used", "")
            if row_count > 0:
                st.caption(f"🗄️ Employee database · {row_count} record(s)")
            if sql:
                with st.expander("View database query"):
                    st.code(sql, language="sql")
        elif message.get("answer_type"):
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

# ── Agent helper ───────────────────────────────────────────────────────────
def get_agent_response(question: str) -> dict:
    """Call /agent/query and return the full response dict."""
    response = httpx.post(
        f"{BACKEND_URL}/agent/query",
        json={"question": question},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


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


def stream_db(question: str, session_id: str):
    """Generator that streams tokens from the database RAG endpoint."""
    with httpx.stream(
        "POST",
        f"{BACKEND_URL}/rag/db/stream",
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
                elif token == "NOT_DB_QUERY":
                    st.session_state.last_answer_type = "rag_fallback"
                    break
                elif "sql_used" in data:
                    st.session_state.last_sql_used = data.get("sql_used", "")
                    st.session_state.last_row_count = data.get("row_count", 0)
                elif token:
                    yield token


# ── Chat input ─────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask ARIA anything about HR..."):
    st.session_state.last_sources = []
    st.session_state.last_sql_used = ""
    st.session_state.last_row_count = 0
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

    # Phase 4 override — route compound questions to agent
    agent_keywords = ["and how many", "and what is", "and who is", "tell me about"]
    if any(kw in prompt.lower() for kw in agent_keywords):
        classification = "agent"

    st.session_state.last_answer_type = classification

    # Route to the correct chain
    if classification == "agent":
        try:
            result = get_agent_response(prompt)
        except Exception as e:
            with st.chat_message("assistant"):
                st.error(f"❌ Could not reach ARIA agent: {str(e)}")
            result = None

        if result:
            with st.chat_message("assistant"):
                st.markdown("🤖 **Agent**")
                st.markdown(result["answer"])

                if result.get("tools_used"):
                    cols = st.columns(len(result["tools_used"]))
                    tool_icons = {
                        "search_policies": "📄",
                        "lookup_employee": "👤",
                        "search_knowledge_base": "🔍",
                    }
                    for i, tool in enumerate(result["tools_used"]):
                        icon = tool_icons.get(tool, "🔧")
                        cols[i].markdown(
                            f"<span style='background:#1a1a2e;padding:4px 10px;"
                            f"border-radius:12px;font-size:0.8em;color:#00C8FF'>"
                            f"{icon} {tool}</span>",
                            unsafe_allow_html=True,
                        )

                if result.get("steps"):
                    with st.expander(
                        f"🧠 Agent Reasoning ({len(result['steps'])} steps)"
                    ):
                        for i, step in enumerate(result["steps"], 1):
                            st.markdown(f"**Step {i} — {step['tool']}**")
                            st.markdown(f"*Tool input:* `{step['tool_input']}`")
                            st.markdown("*Observation:*")
                            st.text(step["observation"][:400])
                            if i < len(result["steps"]):
                                st.divider()

            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
            })

    else:
        response_text = None
        with st.chat_message("assistant"):
            if classification == "rag":
                try:
                    response_text = st.write_stream(
                        stream_rag(prompt, st.session_state.session_id)
                    )
                except Exception as e:
                    st.error(f"❌ Could not reach ARIA backend: {str(e)}")

                if st.session_state.last_sources:
                    st.caption(
                        "📄 **Sources:** " +
                        " · ".join(st.session_state.last_sources)
                    )
                st.caption("🔍 Answered from company documents")

            elif classification == "db":
                try:
                    response_text = st.write_stream(
                        stream_db(prompt, st.session_state.session_id)
                    )
                except Exception as e:
                    st.error(f"❌ Could not reach ARIA backend: {str(e)}")

                if st.session_state.last_row_count > 0:
                    st.caption(
                        f"🗄️ Answered from employee database · "
                        f"{st.session_state.last_row_count} record(s) found"
                    )
                if st.session_state.last_sql_used:
                    with st.expander("View database query"):
                        st.code(st.session_state.last_sql_used, language="sql")

            else:
                try:
                    response_text = st.write_stream(
                        stream_response(prompt, st.session_state.session_id)
                    )
                except Exception as e:
                    st.error(f"❌ Could not reach ARIA backend: {str(e)}")
                    st.info("Make sure the backend is running on port 8000")

                st.caption("💬 General HR knowledge")

        if response_text:
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_text,
                "sources": st.session_state.last_sources,
                "sql_used": st.session_state.last_sql_used,
                "row_count": st.session_state.last_row_count,
                "answer_type": classification,
            })
