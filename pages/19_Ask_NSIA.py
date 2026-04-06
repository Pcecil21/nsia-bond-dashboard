"""
Page 17: Ask NSIA — AI-powered Q&A for board members.

Conversational chat interface where board members can ask questions about
NSIA finances, operations, and governance in plain English.
Accepts redirects from per-page "Ask about this" widgets via session_state.
"""

import logging
import streamlit as st
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

MAX_QUESTIONS_PER_SESSION = 50

# Ensure utils is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from utils.agent_router import get_api_key
from utils.theme import inject_css
from utils.auth import require_auth
from utils.fiscal_period import get_current_month

# Optional imports — data_context may not exist yet
try:
    from utils.data_context import (
        build_data_summary, get_tool_definitions, query_data,
        search_documents, read_document,
    )

    DATA_CONTEXT_AVAILABLE = True
except ImportError:
    DATA_CONTEXT_AVAILABLE = False

    def build_data_summary() -> str:
        return "(Financial data context module not yet available.)"

    def get_tool_definitions() -> list:
        return []

    def query_data(query_type: str = "", filters: dict = None) -> str:
        return "(Data query module not yet available.)"

    def search_documents(search_query: str = "") -> str:
        return "(Document search not available.)"

    def read_document(file_id: str = "", file_name: str = "") -> str:
        return "(Document reading not available.)"


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Ask NSIA | Board Intelligence",
    layout="wide",
    page_icon=":ice_hockey:",
)

inject_css()
require_auth()

# ---------------------------------------------------------------------------
# NSIA Context
# ---------------------------------------------------------------------------

NSIA_CONTEXT = """
North Shore Ice Arena LLC (NSIA) is a 501(c)(3) nonprofit, EIN 20-8396527.
Fiscal year: July 1 - June 30.
Members: Wilmette Hockey Association (WHA) and Winnetka Hockey Club (WKC).
Governance: Six-member rotating board (3 from each member org).
Manager: Club Sports Consulting Group (CSCG), managed by Don Lapato.
Ground lease: With Divine Word (Techny property).
Bond: $8.49M Illinois Finance Authority Sports Facility Revenue Bonds (2008).
Key risks: Revenue concentration, thin cash margins, escalating lease costs, bond sinking fund through 2038, tax-exemption compliance.
"""


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def _build_system_prompt(page_context: str = "") -> str:
    """Assemble the system prompt with live financial data context.

    Args:
        page_context: Optional context from a per-page redirect (e.g. "User was
            viewing the Financial Overview page").
    """
    try:
        data_summary = build_data_summary()
    except Exception:
        data_summary = "(Unable to load financial data summary.)"

    try:
        period = get_current_month()
    except Exception:
        period = {
            "fiscal_year": "Unknown",
            "name": "Unknown",
            "calendar_year": "",
            "fiscal_month": "?",
        }

    page_section = f"\n## Page Context\nThe user was viewing: {page_context}\nPrioritize answering with data relevant to that page.\n" if page_context else ""

    return f"""You are the NSIA Board Intelligence Assistant — a conversational AI that answers questions about North Shore Ice Arena's finances, operations, and governance using actual data.

{NSIA_CONTEXT}

## Current Financial Snapshot
{data_summary}
{page_section}
## Rules
- Always cite specific dollar amounts and percentages from the data
- If you don't have data to answer a question, say so clearly — never guess
- Flag concerning findings: use "RED FLAG:" for urgent items, "CAUTION:" for moderate concerns
- Keep answers concise — board members are busy professionals
- When comparing periods, always show both numbers
- If a question requires more detailed data, use the query_financial_data tool
- If a question is about contracts, agreements, leases, insurance, audits, board meeting materials, or any governance document, use search_documents to find it, then read_document to retrieve its contents
- When referencing a document, include the Google Drive link so the board member can view the original
- Present financial data in clean tables when appropriate
- Never provide legal, tax, or accounting advice — recommend consulting a CPA or attorney for those questions
- You are an oversight tool, not a decision-maker — present options with trade-offs, don't recommend specific actions

## Current Period
{period['fiscal_year']}, data through {period['name']} {period['calendar_year']} (Month {period['fiscal_month']} of 12)
"""


# ---------------------------------------------------------------------------
# Chat UI
# ---------------------------------------------------------------------------

st.title("Ask NSIA")
st.caption("AI-powered Q&A for board members — ask about finances, operations, and governance in plain English.")
st.markdown("---")

if not ANTHROPIC_AVAILABLE:
    st.error(
        "The `anthropic` Python package is not installed. "
        "Run `pip install anthropic` and restart the app."
    )
    st.stop()

# Initialize conversation history and session counter
if "messages" not in st.session_state:
    st.session_state.messages = []
if "question_count" not in st.session_state:
    st.session_state.question_count = 0

# Read page context from redirect (set by per-page "Ask about this" widgets)
_page_context = st.session_state.pop("page_context", "")

# Suggested questions — shown only when the conversation is empty
if len(st.session_state.messages) == 0:
    st.markdown(
        '<div style="color:#a8b2d1;font-size:0.95rem;margin-bottom:12px;">'
        '<b style="color:#ccd6f6;">Try asking:</b></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    suggestions = [
        "How did we do this month?",
        "Are we going to run out of cash?",
        "Which budget lines are most over?",
        "Is everyone paying their ice contracts?",
        "What should we discuss at the next board meeting?",
        "How does CSCG's spending compare to the approved budget?",
        "What's our debt service coverage ratio?",
        "Show me the top 5 vendors by spend",
    ]
    for i, q in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(q, key=f"suggest_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()
    st.markdown("---")

# Display existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ---------------------------------------------------------------------------
# Message handling with tool use
# ---------------------------------------------------------------------------

prompt = st.chat_input("Ask about NSIA finances, operations, or governance...")

# Check for pending question from suggestion buttons
if "pending_question" in st.session_state:
    prompt = st.session_state.pending_question
    del st.session_state.pending_question

if prompt:
    # Session counter check
    if st.session_state.question_count >= MAX_QUESTIONS_PER_SESSION:
        st.warning(
            f"You've asked {MAX_QUESTIONS_PER_SESSION} questions this session. "
            "Please refresh the page to continue, or review past answers above."
        )
        st.stop()

    st.session_state.question_count += 1

    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get API key
    api_key = get_api_key()
    if not api_key:
        st.error(
            "Anthropic API key not configured. "
            "Add ANTHROPIC_API_KEY to .streamlit/secrets.toml or set the environment variable."
        )
        st.stop()

    # Build conversation for API (include page context from redirect if present)
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _build_system_prompt(page_context=_page_context)

    # Convert session messages to API format
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]

    # Fetch tool definitions (may be empty if data_context is unavailable)
    tools = get_tool_definitions()

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            # Build create kwargs — only include tools if we have them
            create_kwargs = dict(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=api_messages,
            )
            if tools:
                create_kwargs["tools"] = tools

            response = client.messages.create(**create_kwargs)

            # Handle tool use loop (Claude may call tools multiple times)
            while response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        # Execute the appropriate tool
                        try:
                            if block.name == "search_documents":
                                result = search_documents(
                                    search_query=block.input.get("search_query", ""),
                                )
                            elif block.name == "read_document":
                                result = read_document(
                                    file_id=block.input.get("file_id", ""),
                                    file_name=block.input.get("file_name", ""),
                                )
                            else:
                                result = query_data(
                                    query_type=block.input.get("query_type", ""),
                                    filters=block.input.get("filters", {}),
                                )
                        except Exception as e:
                            result = f"Error executing query: {e}"

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result),
                            }
                        )

                # Continue conversation with tool results
                api_messages.append(
                    {"role": "assistant", "content": assistant_content}
                )
                api_messages.append({"role": "user", "content": tool_results})

                response = client.messages.create(**create_kwargs | {"messages": api_messages})

            # Extract final text response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            st.markdown(final_text)

    # Save to conversation history
    st.session_state.messages.append({"role": "assistant", "content": final_text})

    # Save to analysis history for audit trail
    try:
        from utils.analysis_history import save_analysis

        save_analysis(
            agent_id="ask_nsia",
            agent_name="Ask NSIA (Q&A)",
            result=final_text,
            filename="chat_question",
            input_summary=prompt[:500],
            source_page="Ask NSIA",
        )
    except Exception as e:
        logger.warning("Failed to save analysis history: %s", e)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption(
        "Powered by Claude AI. Answers are based on NSIA financial data "
        "and should be verified. Not legal, tax, or accounting advice."
    )
