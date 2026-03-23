# NSIA Dashboard Upgrade Plan
**Goal:** Transform the NSIA Board Dashboard from a manually-updated reporting tool into a self-updating centralized brain that board members can ask questions to on demand.

**Created:** 2026-03-18

---

## Phase 0: Documentation Discovery (Complete)

### Key Findings
1. **47 data loader functions** in `utils/data_loader.py` — well-structured, cached, with fallbacks
2. **60+ hardcoded values** across `app.py` and 16 page files — month names, dollar amounts, date ranges, fiscal year references
3. **AI infrastructure already exists:**
   - 16 specialized Claude agents in `agents/` with system prompts
   - Agent router (`utils/agent_router.py`) with keyword-based document detection
   - SQLite analysis history (`utils/analysis_history.py`)
   - Anthropic API key configured in `.streamlit/secrets.toml`
   - Model: `claude-sonnet-4-20250514` with 8192 max tokens
4. **What's missing:** No chat interface. Current AI page is upload → one-shot analysis → download. No conversational Q&A, no multi-turn dialogue, no data-grounded answers.

### Allowed APIs
- **Streamlit:** `st.chat_message`, `st.chat_input`, `st.session_state` (for conversation history)
- **Anthropic:** `anthropic.Anthropic().messages.create()` with system prompts, tool use
- **Data:** All 47 existing loader functions return pandas DataFrames
- **Existing:** `utils/agent_router.py` for Claude API calls, `utils/analysis_history.py` for persistence

### Anti-Patterns to Avoid
- Do NOT use LangChain or vector databases — the data is small enough to pass directly to Claude
- Do NOT extract text from PDFs when Claude handles native PDF — already implemented
- Do NOT create a separate backend/API — Streamlit handles everything
- Do NOT break the existing page structure — add capabilities, don't rebuild

---

## Phase 1: Fiscal Period Config Module
**Purpose:** Eliminate all hardcoded month/year/dollar references. Make the dashboard auto-update when new data syncs from Google Drive.

### Tasks

#### 1.1 Create `utils/fiscal_period.py`
A single source of truth for the current reporting period. All pages import from here.

```python
# Core functions to implement:
def get_current_month() -> dict:
    """Auto-detect latest month from monthly_pnl.csv data.
    Returns: {"name": "January", "abbrev": "Jan", "number": 7,
              "fiscal_month": 7, "total_months": 12,
              "fiscal_year": "FY2026", "fy_start": "July 2025",
              "fy_end": "June 2026", "as_of_date": "January 31, 2026"}"""

def get_month_label() -> str:
    """Returns 'January 2026 — Month 7 of 12'"""

def get_sidebar_caption() -> str:
    """Returns 'FY2026 | Data through January 2026 (Month 7 of 12)'"""

def get_fiscal_date_range() -> str:
    """Returns 'Jul 2025 – Jan 2026'"""

def get_ytd_label() -> str:
    """Returns 'July–January 2025-26 (7 months)'"""
```

**Detection logic:** Read `monthly_pnl.csv`, find the last month with non-null Actual data. Derive everything else from that.

**Doc reference:** `utils/data_loader.py` — `load_monthly_pnl()` returns DataFrame with `Month` column containing abbreviated month names.

#### 1.2 Create `utils/variance_engine.py`
Replace all hardcoded flags with computed variance alerts.

```python
def compute_monthly_flags(month: str) -> list[dict]:
    """Compute red/yellow/green flags from actual data.
    Returns: [{"color": "red", "title": "...", "detail": "..."}]

    Logic:
    - Load monthly_pnl for the target month
    - Compare each line item's Actual vs Budget
    - RED: >150% of budget OR >$5K over budget
    - YELLOW: >120% of budget OR >$2K over budget
    - GREEN: notable positive variances (>150% favorable)
    - Include both monthly and YTD figures in detail text
    """

def compute_discussion_items() -> list[str]:
    """Generate discussion items from:
    - Any RED flags from variance engine
    - Outstanding board demands (from compute_board_demands)
    - Cash forecast negative months
    - Collection shortfalls
    """
```

**Doc reference:** `utils/data_loader.py` — `compute_variance_alerts()` already does RED/YELLOW/GREEN at line-item level. Wrap it for home page consumption.

#### 1.3 Update `app.py` — Make Home Page Dynamic
- Import `fiscal_period` and `variance_engine`
- Replace all hardcoded month references with `fiscal_period.get_*()` calls
- Replace hardcoded `flags` list (lines 367-398) with `variance_engine.compute_monthly_flags()`
- Replace hardcoded `discussion_items` (lines 453-460) with `variance_engine.compute_discussion_items()`
- Make cash chart auto-detect actual vs forecast months (don't hardcode 7/5 split)
- Make receivables section use latest available month columns dynamically

#### 1.4 Update All Page Files
For each of the 16 pages, replace hardcoded values with `fiscal_period` imports:

| File | Changes Needed |
|------|---------------|
| `1_Financial_Overview.py` | Caption date range (line 18, 227) |
| `2_Bond_and_Debt.py` | "6 Months" header (line 87) |
| `3_Revenue_and_Ads.py` | Month columns (lines 194-255), chart titles |
| `4_Operations.py` | Date range caption (line 29, 96) |
| `5_Variance_Alerts.py` | Threshold descriptions (cosmetic only) |
| `6_CSCG_Scorecard.py` | Reporting period label (line 128) |
| `7_Monthly_Financials.py` | FY label (line 147), month names (lines 308-328) |
| `8_Multi_Year_Trends.py` | FY column references (lines 30-32) |
| `9_Ice_Utilization.py` | Season dates (lines 85, 271, 297, 513, 539) |
| `13_Board_Report.py` | Default reporting period (line 112) |

#### 1.5 Update `utils/data_loader.py` — Remove 7-Month Assumption
- `compute_kpis()` line 467: `annual_rev = total_rev_ytd * 12 / 7` — replace `7` with `fiscal_period.get_current_month()["fiscal_month"]`
- `compute_cscg_scorecard()`: Replace hardcoded 6-month actual values with computed values from data

### Verification Checklist — Phase 1
- [ ] `grep -r "January\|FY2026\|Month 7" pages/ app.py` returns zero hits (except comments)
- [ ] Dashboard renders correctly with current data
- [ ] Sidebar caption updates automatically
- [ ] Home page flags are computed, not hardcoded
- [ ] Cash chart correctly splits actual vs forecast months
- [ ] All 16 pages load without errors

---

## Phase 2: Board Q&A Chat Interface
**Purpose:** Add a conversational AI page where board members type questions in plain English and get answers grounded in NSIA's actual financial data.

### Tasks

#### 2.1 Create `utils/data_context.py` — Data Grounding Layer
The bridge between board member questions and the 47 data loaders.

```python
def build_data_summary() -> str:
    """Build a concise text summary of current NSIA financial state.
    Loads key data and formats as structured text that fits in a Claude prompt.

    Sections:
    - Monthly P&L (current month actual vs budget, YTD)
    - Cash position and forecast
    - Contract receivables by club
    - Top variance alerts (RED and YELLOW)
    - CSCG scorecard status
    - Board demands status
    - KPIs (DSCR, NOI, hidden cash flows)

    Target: ~2,000 tokens of structured context
    """

def get_available_data_sources() -> list[dict]:
    """Returns metadata about what data is available for answering questions.
    Used by Claude to decide what additional data to request."""

def query_data(query_type: str, params: dict) -> str:
    """Tool-callable function for Claude to request specific data.
    query_type options:
    - 'monthly_pnl': params={month, category}
    - 'cash_forecast': params={month_range}
    - 'receivables': params={customer}
    - 'variance_alerts': params={severity}
    - 'vendor_bills': params={vendor, category}
    - 'gl_transactions': params={account, date_range}
    - 'ice_utilization': params={club, period}
    - 'cscg_scorecard': no params
    - 'board_demands': no params
    """
```

#### 2.2 Create `pages/17_Ask_NSIA.py` — Chat Interface
The main Q&A page. Uses Streamlit's chat components.

```python
# Key components:
# 1. System prompt with NSIA context + data summary
# 2. st.chat_input for questions
# 3. st.chat_message for conversation display
# 4. Claude API with tool_use for data queries
# 5. Conversation history in st.session_state
# 6. Analysis auto-saved to analysis_history.db

# System prompt structure:
SYSTEM_PROMPT = """You are the NSIA Board Intelligence Assistant.
You answer questions about North Shore Ice Arena's finances,
operations, and governance using actual data — never guessing.

{NSIA context from ROUTER.claude.md}
{Current data summary from build_data_summary()}
{Fiscal period context from fiscal_period}

Rules:
- Always cite specific numbers from the data
- If you don't have data to answer, say so
- Flag any concerning findings with 🔴 or 🟡
- Keep answers concise — board members are busy
- When comparing periods, show both numbers
"""
```

**Claude tool_use integration:**
- Define tools matching `query_data()` function signatures
- Claude calls tools when it needs specific data beyond the summary
- Tool results are injected back into the conversation
- This gives Claude access to all 47 data loaders on demand

#### 2.3 Add Suggested Questions
Pre-populate the chat with clickable starter questions:
- "How did we do this month?"
- "Are we going to run out of cash?"
- "Which budget lines are most over?"
- "Is everyone paying their ice contracts?"
- "What should we discuss at the next board meeting?"
- "How does CSCG's spending compare to the approved budget?"
- "What's our debt service coverage ratio?"

#### 2.4 Add Source Citations
When Claude answers a question, include expandable source references:
```
> Cash on hand is $X as of January 31.

📊 Source: cash_forecast.csv → Cumulative Cash (Jan)
```

This builds trust with board members who want to verify.

#### 2.5 Save Chat History
- Each Q&A session saved to `analysis_history.db` with `source_page="Ask NSIA"`
- Board members can review past questions/answers
- Flag counts tracked for escalation

### Verification Checklist — Phase 2
- [ ] Chat page loads and accepts questions
- [ ] Answers include specific dollar amounts from actual data
- [ ] Tool use works (Claude can query specific data loaders)
- [ ] Conversation history persists within session
- [ ] Suggested questions work as clickable buttons
- [ ] Analysis saved to SQLite history
- [ ] Auth gate works (login required)
- [ ] Test with 10 representative board member questions

---

## Phase 3: Polish & Integrate
**Purpose:** Wire the Q&A into the rest of the dashboard and add quality-of-life features.

### Tasks

#### 3.1 Add "Ask about this" to Every Page
Each existing page gets a small chat widget at the bottom:
```python
with st.expander("💬 Ask a question about this data"):
    question = st.text_input("What would you like to know?")
    if question:
        # Route to Ask NSIA with page context pre-loaded
```

#### 3.2 Add "Last Updated" Indicator
- Show when data was last synced from Google Drive
- Show data freshness on every page header
- Warn if data is >7 days stale

#### 3.3 Email Digest (Optional)
- Weekly summary email to board members
- Top RED/YELLOW flags
- Cash position
- "Ask the dashboard" CTA link

#### 3.4 Mobile Optimization
- Test all pages on mobile viewport
- Ensure chat interface works on phone
- Board members often check on phones before meetings

### Verification Checklist — Phase 3
- [ ] "Ask about this" works from at least 3 pages
- [ ] Last updated indicator shows on home page
- [ ] Mobile layout is usable
- [ ] Full end-to-end test: sync data → dashboard updates → chat answers correctly

---

## Execution Order
1. **Phase 1 first** — foundational, makes everything else easier
2. **Phase 2 next** — the "centralized brain" feature
3. **Phase 3 last** — polish, can be incremental

## Estimated Scope
- Phase 1: ~2 sessions (config module + update all pages)
- Phase 2: ~2 sessions (data context + chat page + tool use)
- Phase 3: ~1 session (integration + polish)
