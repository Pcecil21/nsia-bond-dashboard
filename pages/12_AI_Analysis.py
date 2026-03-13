"""
NSIA Bond Dashboard — AI Governance Analysis
Page 12: Upload any document and route it to the appropriate AI agent.
"""

import streamlit as st
from pathlib import Path
import sys

# Ensure utils is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.agent_router import (
    AGENT_REGISTRY,
    analyze_document,
    analyze_document_with_pdf,
    detect_agent,
    get_agent_choices,
    get_api_key,
    ANTHROPIC_AVAILABLE,
)
from utils.theme import style_chart, inject_css
from utils.auth import require_auth

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AI Analysis | NSIA", page_icon=":ice_hockey:", layout="wide")

# ── Dark theme CSS (matches dashboard) ────────────────────────────────────
inject_css()
require_auth()

st.markdown("""
<style>
    .agent-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .agent-card h4 { color: #ccd6f6; margin: 0 0 4px 0; }
    .agent-card p { color: #a8b2d1; margin: 0; font-size: 0.9rem; }
    .analysis-result {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 20px 24px;
        margin: 12px 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("AI Governance Analysis")
st.caption(
    "Upload any NSIA document — invoices, bank statements, budgets, contracts, "
    "schedules, or reports — and the system will route it to the appropriate "
    "analysis agent automatically."
)

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

if not ANTHROPIC_AVAILABLE:
    st.error(
        "⚠️ The `anthropic` Python package is not installed. "
        "Run `pip install anthropic` in your terminal, then restart the app."
    )
    st.stop()

if not get_api_key():
    st.error(
        "⚠️ No API key found. Add your key to `.streamlit/secrets.toml`:\n\n"
        '```\nANTHROPIC_API_KEY = "sk-ant-your-key-here"\n```'
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar: Agent selector & info
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Agent Selection")

    mode = st.radio(
        "Routing mode",
        ["🔀 Auto-detect from document", "🎯 Choose agent manually"],
        index=0,
    )

    if mode.startswith("🎯"):
        agent_choices = get_agent_choices()
        selected_label = st.selectbox(
            "Select agent",
            options=[f"{a['icon']} {a['name']}" for a in agent_choices],
            index=0,
        )
        # Map back to agent_id
        selected_idx = [f"{a['icon']} {a['name']}" for a in agent_choices].index(
            selected_label
        )
        manual_agent_id = agent_choices[selected_idx]["id"]
        st.caption(agent_choices[selected_idx]["description"])
    else:
        manual_agent_id = None

    st.divider()
    st.header("Available Agents")
    for agent_id, config in AGENT_REGISTRY.items():
        st.markdown(
            f'<div class="agent-card"><h4>{config["icon"]} {config["name"]}</h4>'
            f'<p>{config["description"]}</p></div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Main: File upload (single document)
# ---------------------------------------------------------------------------

col_upload, col_context = st.columns([2, 1])

with col_upload:
    uploaded_file = st.file_uploader(
        "Upload a document for analysis",
        type=["pdf", "csv", "xlsx", "xls", "txt", "docx", "png", "jpg", "jpeg"],
        help="Supported: PDF, CSV, Excel, text, Word, images",
    )

with col_context:
    additional_context = st.text_area(
        "Additional context (optional)",
        placeholder="e.g., 'This is the January 2026 bank statement' or 'Compare against the CSCG contract rates'",
        height=120,
    )

# ---------------------------------------------------------------------------
# Process uploaded file
# ---------------------------------------------------------------------------

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    filename = uploaded_file.name
    file_ext = Path(filename).suffix.lower().lstrip(".")

    # Determine which agent to use
    if manual_agent_id:
        agent_id = manual_agent_id
    else:
        # For auto-detection, try to get a text preview
        preview = ""
        if file_ext in ("csv", "txt"):
            try:
                preview = file_bytes.decode("utf-8", errors="replace")[:2000]
            except Exception:
                pass
        agent_id = detect_agent(filename, preview)

    agent_config = AGENT_REGISTRY[agent_id]

    # Show what agent was selected
    st.info(
        f"**Agent selected:** {agent_config['icon']} {agent_config['name']}  \n"
        f"{agent_config['description']}"
    )

    # Run analysis button
    if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
        with st.spinner(f"Running {agent_config['name']} analysis on {filename}..."):

            result = None

            if file_ext == "pdf":
                # Send PDF natively to Claude
                result = analyze_document_with_pdf(
                    agent_id=agent_id,
                    pdf_bytes=file_bytes,
                    filename=filename,
                    additional_context=additional_context,
                )
            elif file_ext in ("csv", "txt"):
                # Send as text
                try:
                    text_content = file_bytes.decode("utf-8", errors="replace")
                except Exception:
                    text_content = str(file_bytes)
                result = analyze_document(
                    agent_id=agent_id,
                    document_content=text_content,
                    filename=filename,
                    additional_context=additional_context,
                )
            elif file_ext in ("xlsx", "xls"):
                # Convert Excel to CSV text for the API
                try:
                    import pandas as pd
                    import io
                    
                    xls = pd.ExcelFile(io.BytesIO(file_bytes))
                    all_sheets = []
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
                        all_sheets.append(
                            f"=== Sheet: {sheet_name} ===\n{df.to_csv(index=False)}"
                        )
                    text_content = "\n\n".join(all_sheets)
                    result = analyze_document(
                        agent_id=agent_id,
                        document_content=text_content,
                        filename=filename,
                        additional_context=additional_context,
                    )
                except ImportError:
                    st.error("Install `openpyxl` to process Excel files: `pip install openpyxl`")
                except Exception as e:
                    st.error(f"Error reading Excel file: {e}")
            elif file_ext in ("png", "jpg", "jpeg"):
                # Send image as base64 to Claude
                import base64
                img_b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
                media_type = f"image/{file_ext}" if file_ext != "jpg" else "image/jpeg"

                try:
                    import anthropic
                    system_prompt = open(
                        Path(__file__).parent.parent / "agents" / agent_config["file"],
                        encoding="utf-8",
                    ).read()

                    client = anthropic.Anthropic(api_key=get_api_key())
                    response = client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=8192,
                        system=system_prompt,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": img_b64,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": f"Analyze this document image: {filename}"
                                        + (f"\n\nContext: {additional_context}" if additional_context else ""),
                                    },
                                ],
                            }
                        ],
                    )
                    result = response.content[0].text
                except Exception as e:
                    st.error(f"Error processing image: {e}")
            else:
                st.warning(f"File type `.{file_ext}` is not yet supported for direct analysis.")

            # Display results
            if result:
                st.divider()
                st.header(f"{agent_config['icon']} Analysis Results")

                # Check for escalation items and show a warning banner
                red_flags = result.count("🔴")
                yellow_flags = result.count("🟡")
                if red_flags > 0:
                    st.error(f"⚠️ **{red_flags} critical item(s)** require board attention")
                if yellow_flags > 0:
                    st.warning(f"**{yellow_flags} caution item(s)** flagged for review")

                # Render the full analysis
                st.markdown(result)

                # Download button for the analysis
                st.divider()
                st.download_button(
                    label="📥 Download Analysis as Markdown",
                    data=result,
                    file_name=f"nsia_analysis_{filename.rsplit('.', 1)[0]}.md",
                    mime="text/markdown",
                )

                # Store in session state for potential cross-agent use
                if "analysis_history" not in st.session_state:
                    st.session_state.analysis_history = []
                st.session_state.analysis_history.append(
                    {
                        "agent": agent_config["name"],
                        "filename": filename,
                        "result": result,
                    }
                )

# ---------------------------------------------------------------------------
# Analysis history (from current session)
# ---------------------------------------------------------------------------

if "analysis_history" in st.session_state and st.session_state.analysis_history:
    st.divider()
    with st.expander(
        f"Session History ({len(st.session_state.analysis_history)} analyses this session)",
        expanded=False,
    ):
        for i, entry in enumerate(reversed(st.session_state.analysis_history)):
            st.markdown(
                f"**{i + 1}.** {entry['agent']} → `{entry['filename']}`"
            )

        if st.button("Clear Session History"):
            st.session_state.analysis_history = []
            st.rerun()

# ---------------------------------------------------------------------------
# Multi-document cross-analysis
# ---------------------------------------------------------------------------

st.divider()
st.header("Multi-Document Cross-Analysis")
st.caption(
    "Upload multiple documents at once. Each is analyzed by its matched agent, "
    "then all results are synthesized into a single cross-document report."
)

multi_files = st.file_uploader(
    "Upload multiple documents",
    type=["pdf", "csv", "xlsx", "xls", "txt"],
    accept_multiple_files=True,
    key="multi_upload",
    help="Upload 2+ documents (bank statement + budget + invoices, etc.)",
)

multi_context = st.text_area(
    "Cross-analysis instructions (optional)",
    placeholder="e.g., 'Compare the bank statement against the budget and flag discrepancies'",
    height=80,
    key="multi_context",
)

if multi_files and len(multi_files) >= 2:
    if st.button("Run Cross-Analysis", type="primary", use_container_width=True, key="btn_multi"):
        individual_results = []

        # Step 1: Analyze each document individually
        for i, mf in enumerate(multi_files):
            file_bytes = mf.read()
            fname = mf.name
            ext = Path(fname).suffix.lower().lstrip(".")

            # Detect agent
            preview = ""
            if ext in ("csv", "txt"):
                try:
                    preview = file_bytes.decode("utf-8", errors="replace")[:2000]
                except Exception:
                    pass
            agent_id = detect_agent(fname, preview)
            agent_config_item = AGENT_REGISTRY[agent_id]

            with st.spinner(f"[{i+1}/{len(multi_files)}] Analyzing {fname} with {agent_config_item['name']}..."):
                if ext in ("csv", "txt"):
                    try:
                        text_content = file_bytes.decode("utf-8", errors="replace")
                    except Exception:
                        text_content = str(file_bytes)
                    result = analyze_document(
                        agent_id=agent_id,
                        document_content=text_content,
                        filename=fname,
                    )
                elif ext in ("xlsx", "xls"):
                    try:
                        import pandas as pd
                        import io
                        xls = pd.ExcelFile(io.BytesIO(file_bytes))
                        all_sheets = []
                        for sheet_name in xls.sheet_names:
                            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
                            all_sheets.append(f"=== Sheet: {sheet_name} ===\n{df.to_csv(index=False)}")
                        text_content = "\n\n".join(all_sheets)
                        result = analyze_document(
                            agent_id=agent_id,
                            document_content=text_content,
                            filename=fname,
                        )
                    except Exception as e:
                        st.error(f"Error reading {fname}: {e}")
                        result = None
                elif ext == "pdf":
                    result = analyze_document_with_pdf(
                        agent_id=agent_id,
                        pdf_bytes=file_bytes,
                        filename=fname,
                    )
                else:
                    result = None

                if result:
                    individual_results.append({
                        "filename": fname,
                        "agent": agent_config_item["name"],
                        "result": result,
                    })

        # Step 2: Synthesize with Report Generator
        if len(individual_results) >= 2:
            synthesis_input = "MULTI-DOCUMENT CROSS-ANALYSIS\n\n"
            synthesis_input += f"Documents analyzed: {len(individual_results)}\n\n"
            for ir in individual_results:
                synthesis_input += f"{'='*60}\n"
                synthesis_input += f"DOCUMENT: {ir['filename']}\n"
                synthesis_input += f"AGENT: {ir['agent']}\n"
                synthesis_input += f"{'='*60}\n"
                synthesis_input += ir["result"]
                synthesis_input += "\n\n"

            with st.spinner("Synthesizing cross-document analysis..."):
                synthesis = analyze_document(
                    agent_id="report_generator",
                    document_content=synthesis_input,
                    filename="cross_analysis.txt",
                    additional_context=(
                        "Synthesize these individual document analyses into a single "
                        "cross-document report. Identify connections, discrepancies, "
                        "and patterns across the documents. Flag any items where one "
                        "document contradicts another."
                        + (f"\n\nUser instructions: {multi_context}" if multi_context else "")
                    ),
                )

            if synthesis:
                st.divider()
                st.subheader("Cross-Analysis Results")

                # Show individual results in expanders
                for ir in individual_results:
                    with st.expander(f"{ir['agent']} → {ir['filename']}"):
                        st.markdown(ir["result"])

                # Show synthesis
                st.subheader("Synthesized Report")
                red_flags = synthesis.count("\U0001f534")
                yellow_flags = synthesis.count("\U0001f7e1")
                if red_flags > 0:
                    st.error(f"**{red_flags} critical item(s)** found across documents")
                if yellow_flags > 0:
                    st.warning(f"**{yellow_flags} caution item(s)** found across documents")
                st.markdown(synthesis)
                st.download_button(
                    label="Download Cross-Analysis Report",
                    data=synthesis,
                    file_name="nsia_cross_analysis.md",
                    mime="text/markdown",
                    key="dl_cross",
                )
        elif individual_results:
            st.warning("Only one document was successfully analyzed. Upload 2+ for cross-analysis.")
elif multi_files and len(multi_files) == 1:
    st.info("Upload at least 2 documents for cross-analysis.")

# ---------------------------------------------------------------------------
# Persistent analysis history (SQLite)
# ---------------------------------------------------------------------------

st.divider()
st.header("Analysis Archive")
st.caption("All AI analyses are automatically saved for audit trail and comparison.")

try:
    from utils.analysis_history import get_recent_analyses, get_analysis_stats, get_analysis_by_id

    stats = get_analysis_stats()

    if stats["total_analyses"] > 0:
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("Total Analyses", stats["total_analyses"])
        with col_s2:
            st.metric("Red Flags (all time)", stats["total_red_flags"])
        with col_s3:
            st.metric("Yellow Flags (all time)", stats["total_yellow_flags"])
        with col_s4:
            if stats["latest_timestamp"]:
                st.metric("Latest", stats["latest_timestamp"][:10])

        # Agent breakdown
        if stats["by_agent"]:
            with st.expander("Analyses by Agent"):
                for entry in stats["by_agent"]:
                    st.markdown(f"- **{entry['agent_name']}**: {entry['count']} analyses")

        # Recent analyses with expand-to-view
        recent = get_recent_analyses(limit=10)
        if recent:
            st.subheader("Recent Analyses")
            for analysis in recent:
                ts = analysis["timestamp"][:16].replace("T", " ")
                label = f"{ts} | {analysis['agent_name']} | {analysis['filename']}"
                flags = ""
                if analysis["red_flags"]:
                    flags += f" | {analysis['red_flags']} red"
                if analysis["yellow_flags"]:
                    flags += f" | {analysis['yellow_flags']} yellow"
                with st.expander(label + flags):
                    st.markdown(analysis["result"])
                    st.download_button(
                        "Download",
                        data=analysis["result"],
                        file_name=f"analysis_{analysis['id']}_{analysis['filename']}.md",
                        mime="text/markdown",
                        key=f"dl_hist_{analysis['id']}",
                    )
    else:
        st.info("No analyses saved yet. Run an analysis above to start building your archive.")

except ImportError:
    st.info("Analysis history module not available.")
