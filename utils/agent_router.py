"""
NSIA Agent Router - AI-powered document analysis for the bond dashboard.

Loads agent prompts from /agents folder, detects document type,
and routes to the appropriate agent via Claude API.
"""

import os
import json
import re
from pathlib import Path
from typing import Optional
import streamlit as st

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ---------------------------------------------------------------------------
# Agent registry – maps agent IDs to their prompt files
# ---------------------------------------------------------------------------

AGENT_REGISTRY = {
    # Financial Oversight
    "bank_statement": {
        "name": "Bank Statement Analyst",
        "file": "financial-oversight/01-bank-statement-analyst.claude.md",
        "icon": "🏦",
        "description": "Parse transactions, flag anomalies, track cash flow",
        "accepts": ["pdf"],
        "keywords": ["bank", "statement", "checking", "savings", "deposit", "withdrawal"],
    },
    "budget_reconciler": {
        "name": "Budget & GL Reconciler",
        "file": "financial-oversight/02-budget-gl-reconciler.claude.md",
        "icon": "📊",
        "description": "Budget-to-actual comparison, variance analysis",
        "accepts": ["csv", "xlsx", "xls", "pdf"],
        "keywords": ["budget", "general ledger", "gl", "variance", "actual", "quickbooks"],
    },
    "invoice_auditor": {
        "name": "Invoice Auditor",
        "file": "financial-oversight/03-invoice-auditor.claude.md",
        "icon": "🧾",
        "description": "Invoice accuracy, duplicates, contract rate compliance",
        "accepts": ["pdf", "png", "jpg", "jpeg"],
        "keywords": ["invoice", "bill", "payment", "vendor", "due"],
    },
    "revenue_tracker": {
        "name": "Revenue & Utilization Tracker",
        "file": "financial-oversight/04-revenue-utilization-tracker.claude.md",
        "icon": "💰",
        "description": "Revenue monitoring, utilization rates, projections",
        "accepts": ["csv", "xlsx", "xls", "pdf"],
        "keywords": ["revenue", "income", "rental", "program fees", "concession"],
    },
    "financial_health": {
        "name": "Financial Health Monitor",
        "file": "financial-oversight/05-financial-health-monitor.claude.md",
        "icon": "❤️‍🩹",
        "description": "Financial ratios, reserves, burn rate, fiscal health",
        "accepts": ["csv", "xlsx", "xls", "pdf"],
        "keywords": ["balance sheet", "financial summary", "assets", "liabilities", "ratio"],
    },
    # Contract & Compliance
    "contract_analyst": {
        "name": "Contract Analyst",
        "file": "contract-compliance/06-contract-analyst.claude.md",
        "icon": "📜",
        "description": "Contract terms, obligations, deadlines, risk exposure",
        "accepts": ["pdf", "docx"],
        "keywords": ["contract", "agreement", "amendment", "lease", "terms"],
    },
    "compliance_monitor": {
        "name": "Compliance & Insurance Monitor",
        "file": "contract-compliance/07-compliance-insurance-monitor.claude.md",
        "icon": "🛡️",
        "description": "Regulatory tracking, insurance coverage, filings",
        "accepts": ["pdf"],
        "keywords": ["insurance", "policy", "certificate", "compliance", "990", "filing"],
    },
    # Operations
    "scheduling_optimizer": {
        "name": "Ice Time & Scheduling Optimizer",
        "file": "operations/08-ice-time-scheduling-optimizer.claude.md",
        "icon": "🧊",
        "description": "Utilization analysis, scheduling optimization",
        "accepts": ["csv", "xlsx", "xls"],
        "keywords": ["schedule", "ice time", "booking", "rink", "utilization", "allocation"],
    },
    "facility_analyst": {
        "name": "Facility & Maintenance Analyst",
        "file": "operations/09-facility-maintenance-analyst.claude.md",
        "icon": "🔧",
        "description": "Maintenance costs, energy, equipment lifecycle",
        "accepts": ["csv", "xlsx", "xls", "pdf"],
        "keywords": ["maintenance", "repair", "utility", "energy", "equipment", "zamboni"],
    },
    "mgmt_scorer": {
        "name": "Management Company Performance Scorer",
        "file": "operations/10-management-company-scorer.claude.md",
        "icon": "📋",
        "description": "KPI scorecards, contractual performance evaluation",
        "accepts": ["pdf", "csv", "xlsx", "xls"],
        "keywords": ["management", "cscg", "performance", "scorecard", "kpi"],
    },
    # Marketing & Growth
    "marketing_strategist": {
        "name": "Marketing Strategist",
        "file": "marketing-growth/11-marketing-strategist.claude.md",
        "icon": "📣",
        "description": "Program marketing, community engagement, growth",
        "accepts": ["csv", "xlsx", "xls", "pdf"],
        "keywords": ["marketing", "program", "enrollment", "community", "event"],
    },
    "pricing_analyst": {
        "name": "Pricing & Competitive Analyst",
        "file": "marketing-growth/12-pricing-competitive-analyst.claude.md",
        "icon": "💲",
        "description": "Rate benchmarking, competitive intelligence",
        "accepts": ["csv", "xlsx", "xls", "pdf"],
        "keywords": ["pricing", "rate", "competitor", "benchmark", "fee schedule"],
    },
    # Infrastructure
    "data_ingestion": {
        "name": "Data Ingestion Agent",
        "file": "infrastructure/13-data-ingestion-agent.claude.md",
        "icon": "📥",
        "description": "Parse, validate, normalize input data",
        "accepts": ["csv", "xlsx", "xls", "pdf", "txt"],
        "keywords": [],  # Fallback agent for unrecognized data
    },
    "metrics_calculator": {
        "name": "Metrics Calculator",
        "file": "infrastructure/14-metrics-calculator.claude.md",
        "icon": "🔢",
        "description": "Compute financial and operational metrics on demand",
        "accepts": ["csv", "xlsx", "xls"],
        "keywords": ["calculate", "metric", "ratio", "variance", "formula"],
    },
    "report_generator": {
        "name": "Report Generator",
        "file": "infrastructure/15-report-generator.claude.md",
        "icon": "📑",
        "description": "Synthesize analyses into board reports",
        "accepts": [],
        "keywords": ["board report", "synthesize", "summary report", "board meeting"],
    },
    "alert_monitor": {
        "name": "Alert Monitor",
        "file": "infrastructure/16-alert-monitor.claude.md",
        "icon": "🚨",
        "description": "Threshold-based alerting and deadline tracking",
        "accepts": ["csv", "xlsx", "xls", "pdf"],
        "keywords": ["alert", "threshold", "deadline", "overdue", "warning"],
    },
}


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

def get_agents_dir() -> Path:
    """Find the agents directory relative to the project root."""
    # Try common locations
    candidates = [
        Path(__file__).parent.parent / "agents",       # utils/agent_router.py -> ../agents
        Path.cwd() / "agents",                          # Current working directory
        Path("agents"),                                  # Relative
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not find agents/ directory. Ensure it exists in the project root."
    )


def load_agent_prompt(agent_id: str) -> str:
    """Load the full .claude.md prompt for a given agent."""
    if agent_id not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_id}")

    agents_dir = get_agents_dir()
    prompt_path = agents_dir / AGENT_REGISTRY[agent_id]["file"]

    if not prompt_path.exists():
        raise FileNotFoundError(f"Agent prompt not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")


def load_router_prompt() -> str:
    """Load the unified router prompt."""
    agents_dir = get_agents_dir()
    router_path = agents_dir / "ROUTER.claude.md"
    if router_path.exists():
        return router_path.read_text(encoding="utf-8")
    # Fallback: return a minimal router instruction
    return "You are the NSIA governance analysis system. Analyze the uploaded document."


# ---------------------------------------------------------------------------
# Document type detection
# ---------------------------------------------------------------------------

def detect_agent(filename: str, file_content_preview: str = "") -> str:
    """
    Detect which agent should handle a file based on filename and content preview.
    Returns agent_id from AGENT_REGISTRY.
    """
    filename_lower = filename.lower()
    preview_lower = file_content_preview.lower() if file_content_preview else ""
    combined = f"{filename_lower} {preview_lower}"

    # Score each agent based on keyword matches
    scores = {}
    for agent_id, config in AGENT_REGISTRY.items():
        score = 0
        for keyword in config.get("keywords", []):
            if keyword in combined:
                score += 1
        scores[agent_id] = score

    # Get the best match
    best_agent = max(scores, key=scores.get)

    # If no keywords matched at all, fall back to data_ingestion
    if scores[best_agent] == 0:
        return "data_ingestion"

    return best_agent


def get_agent_choices() -> list[dict]:
    """Return a list of all agents for UI selection."""
    return [
        {
            "id": agent_id,
            "name": config["name"],
            "icon": config["icon"],
            "description": config["description"],
        }
        for agent_id, config in AGENT_REGISTRY.items()
    ]


# ---------------------------------------------------------------------------
# Claude API integration
# ---------------------------------------------------------------------------

def get_api_key() -> Optional[str]:
    """Retrieve the Anthropic API key from Streamlit secrets or environment."""
    # Try Streamlit secrets first
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError, AttributeError):
        pass
    # Then environment variable
    return os.environ.get("ANTHROPIC_API_KEY")


def analyze_document(
    agent_id: str,
    document_content: str,
    filename: str = "uploaded_document",
    additional_context: str = "",
    model: str = "claude-sonnet-4-20250514",
) -> Optional[str]:
    """
    Send a document to the specified agent via Claude API and return the analysis.

    Args:
        agent_id: The agent to use (key from AGENT_REGISTRY)
        document_content: The text content of the document to analyze
        filename: Original filename for context
        additional_context: Any extra context from the user
        model: Claude model to use
    
    Returns:
        The agent's analysis as a string, or None if the API call fails.
    """
    if not ANTHROPIC_AVAILABLE:
        st.error(
            "The `anthropic` package is not installed. "
            "Run `pip install anthropic` to enable AI analysis."
        )
        return None

    api_key = get_api_key()
    if not api_key:
        st.error(
            "No API key found. Add ANTHROPIC_API_KEY to `.streamlit/secrets.toml` "
            "or set it as an environment variable."
        )
        return None

    # Load the agent's system prompt
    try:
        system_prompt = load_agent_prompt(agent_id)
    except (FileNotFoundError, ValueError) as e:
        st.error(f"Could not load agent prompt: {e}")
        return None

    # Build the user message
    user_message = f"**Document:** {filename}\n\n"
    if additional_context:
        user_message += f"**Context:** {additional_context}\n\n"
    user_message += f"**Document Content:**\n\n{document_content}"

    # Call Claude
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        result_text = response.content[0].text

        # Auto-save to history
        try:
            from utils.analysis_history import save_analysis
            save_analysis(
                agent_id=agent_id,
                agent_name=AGENT_REGISTRY[agent_id]["name"],
                result=result_text,
                filename=filename,
                input_summary=document_content[:500],
            )
        except Exception:
            pass  # Don't fail the analysis if history save fails

        return result_text
    except anthropic.APIError as e:
        st.error(f"Claude API error: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error calling Claude API: {e}")
        return None


def analyze_document_with_pdf(
    agent_id: str,
    pdf_bytes: bytes,
    filename: str = "uploaded_document.pdf",
    additional_context: str = "",
    model: str = "claude-sonnet-4-20250514",
) -> Optional[str]:
    """
    Send a PDF directly to Claude using the document input type.

    Args:
        agent_id: The agent to use
        pdf_bytes: Raw PDF file bytes
        filename: Original filename
        additional_context: Extra context
        model: Claude model to use
    
    Returns:
        The agent's analysis as a string, or None if the API call fails.
    """
    if not ANTHROPIC_AVAILABLE:
        st.error("The `anthropic` package is not installed.")
        return None

    api_key = get_api_key()
    if not api_key:
        st.error("No API key found.")
        return None

    try:
        system_prompt = load_agent_prompt(agent_id)
    except (FileNotFoundError, ValueError) as e:
        st.error(f"Could not load agent prompt: {e}")
        return None

    import base64
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    user_content = []

    # Add the PDF as a document
    user_content.append({
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": pdf_b64,
        },
    })

    # Add text instructions
    instructions = f"Analyze this document: **{filename}**"
    if additional_context:
        instructions += f"\n\n**Additional context:** {additional_context}"
    user_content.append({"type": "text", "text": instructions})

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        result_text = response.content[0].text

        # Auto-save to history
        try:
            from utils.analysis_history import save_analysis
            save_analysis(
                agent_id=agent_id,
                agent_name=AGENT_REGISTRY[agent_id]["name"],
                result=result_text,
                filename=filename,
                input_summary=f"PDF document: {filename}",
            )
        except Exception:
            pass

        return result_text
    except anthropic.APIError as e:
        st.error(f"Claude API error: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None
