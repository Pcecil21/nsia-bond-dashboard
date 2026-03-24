"""
Page 19: New Board Member Guide
Orientation guide for incoming NSIA board members — what NSIA is, how the
finances work, key metrics to watch, glossary of terms, and page directory.
"""
import streamlit as st
from utils.theme import inject_css, FONT_COLOR, TITLE_COLOR, VALUE_COLOR
from utils.auth import require_auth

st.set_page_config(page_title="Board Guide | NSIA", layout="wide", page_icon=":ice_hockey:")

inject_css()
require_auth()

# ── Welcome Header ────────────────────────────────────────────────────────

st.title("New Board Member Guide")
st.markdown(
    f"""
    <p style="color:{FONT_COLOR}; font-size:1.1rem; margin-bottom:2rem;">
    Welcome to the NSIA Board Dashboard — your window into the financial health
    and operations of North Shore Ice Arena.
    </p>
    """,
    unsafe_allow_html=True,
)

# ── What Is NSIA? ─────────────────────────────────────────────────────────

st.header("What Is NSIA?")
st.markdown(
    f"""
<ul style="color:{FONT_COLOR}; line-height:1.8;">
<li><b style="color:{VALUE_COLOR};">North Shore Ice Arena LLC</b> is a 501(c)(3) nonprofit in Northbrook, IL.</li>
<li>Built in 2008, funded by <b style="color:{VALUE_COLOR};">$8.49M</b> in Illinois Finance Authority Revenue Bonds.</li>
<li>Owned jointly by <b style="color:{VALUE_COLOR};">Wilmette Hockey Association (WHA)</b> and
    <b style="color:{VALUE_COLOR};">Winnetka Hockey Club (WKC)</b>.</li>
<li>Governed by a <b style="color:{VALUE_COLOR};">six-member rotating board</b> (3 from each member org).</li>
<li>Day-to-day operations managed by <b style="color:{VALUE_COLOR};">Club Sports Consulting Group (CSCG)</b>,
    led by Don Lapato.</li>
<li>Ground lease on Techny property (Divine Word), runs through <b style="color:{VALUE_COLOR};">2088</b>.</li>
</ul>
""",
    unsafe_allow_html=True,
)

# ── How the Finances Work ─────────────────────────────────────────────────

st.header("How the Finances Work")
st.markdown(
    f"""
<ul style="color:{FONT_COLOR}; line-height:1.8;">
<li><b style="color:{VALUE_COLOR};">Fiscal year:</b> July 1 through June 30.</li>
<li>Revenue comes primarily from ice rental contracts with member clubs, plus advertising and events.</li>
<li>CSCG submits a proposed annual budget; the board approves it.</li>
<li>CSCG manages daily operations and spending within the approved budget.</li>
<li>The board's job is <b style="color:{VALUE_COLOR};">oversight</b>: making sure CSCG stays within budget
    and the rink stays financially healthy.</li>
<li>Bond debt service (<b style="color:{VALUE_COLOR};">~$376K/year</b>) is paid from a separate restricted
    trust account at UMB Bank.</li>
<li>The Debt Service Reserve Fund (DSRF) holds <b style="color:{VALUE_COLOR};">~$650K</b> in CDs as a safety
    cushion required by the bond agreement.</li>
</ul>
""",
    unsafe_allow_html=True,
)

# ── Your 5 Key Metrics ────────────────────────────────────────────────────

st.header("Your 5 Key Metrics (Monthly Check)")

metrics = [
    ("Net Income", "Are we making or losing money this month?", "Home page"),
    ("Cash on Hand", "Can we pay our bills? Below $50K is a warning.", "Home page"),
    ("YTD vs Plan", "Are we on track against the approved budget?", "Home page"),
    ("DSCR", "Debt Service Coverage Ratio. Can we cover our bond payments? Above 1.25x is healthy.", "Home page"),
    ("Collection Rate", "Are clubs paying their ice contracts on time?", "Home page"),
]

cols = st.columns(5)
for col, (name, description, location) in zip(cols, metrics):
    with col:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #1a1a2e, #16213e);
                border: 1px solid #0f3460;
                border-radius: 10px;
                padding: 1.2rem;
                height: 100%;
            ">
                <p style="color:{TITLE_COLOR}; font-weight:700; font-size:1rem; margin-bottom:0.5rem;">
                    {name}
                </p>
                <p style="color:{FONT_COLOR}; font-size:0.85rem; margin-bottom:0.75rem;">
                    {description}
                </p>
                <p style="color:{VALUE_COLOR}; font-size:0.8rem; opacity:0.7; margin:0;">
                    Find it on: {location}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── Glossary — Key Terms ──────────────────────────────────────────────────

st.header("Glossary -- Key Terms")

glossary = [
    ("CSCG", "Club Sports Consulting Group. The management company hired to run daily operations."),
    ("DSCR", "Debt Service Coverage Ratio. Net operating income divided by annual debt payments. Above 1.25x means comfortable; below 1.0x means we can't cover debt from operations."),
    ("DSRF", "Debt Service Reserve Fund. A reserve of ~$650K in CDs held at UMB Bank, required by our bond agreement as a safety cushion."),
    ("Variance", 'The difference between what was budgeted and what was actually spent/earned. A "favorable" variance means we did better than planned.'),
    ("YTD", "Year to Date. Cumulative totals from July 1 (start of fiscal year) through the latest month."),
    ("Budget vs Actuals", "Comparing what CSCG proposed spending (budget) against what they actually spent (actuals)."),
    ("Par Amount", "The face value of a CD or bond. The amount you get back at maturity."),
    ("CUSIP", "A 9-character ID code for securities. Think of it as a serial number for a CD or bond."),
    ("Yield", "The annual interest rate earned on an investment (CD, Treasury, etc.)."),
    ("FDIC", "Federal Deposit Insurance Corporation. Insures bank deposits up to $250,000 per institution."),
    ("NPV", "Net Present Value. The current value of future cash flows, discounted for the time value of money."),
    ("Form 990", "The annual tax return nonprofits file with the IRS. Publicly available."),
    ("Auto-Pay", "Expenses CSCG pays without individual board approval (e.g., utilities, payroll)."),
    ("Trustee", "UMB Bank. Holds and manages the bond-related accounts on behalf of NSIA."),
]

with st.expander("Click to expand the full glossary", expanded=False):
    left_col, right_col = st.columns(2)
    midpoint = len(glossary) // 2 + len(glossary) % 2

    for i, (term, definition) in enumerate(glossary):
        target = left_col if i < midpoint else right_col
        with target:
            st.markdown(
                f"""
                <p style="color:{FONT_COLOR}; margin-bottom:0.75rem;">
                    <b style="color:{VALUE_COLOR};">{term}</b> — {definition}
                </p>
                """,
                unsafe_allow_html=True,
            )

# ── Page Guide — Where to Find What ───────────────────────────────────────

st.header("Page Guide -- Where to Find What")

page_guide = [
    ("How we're doing this month", "Home"),
    ("Detailed budget vs actual numbers", "Financial Overview"),
    ("Whether we can pay our bills", "Monthly Financials"),
    ("What's off-budget and needs attention", "Variance Alerts"),
    ("How CSCG is managing the rink", "CSCG Scorecard, Operations"),
    ("Our bond debt and reserve fund", "Bond & Debt, DSRF Tracker"),
    ("Ice time allocation by club", "Ice Utilization"),
    ("Board documents and contracts", "Document Library"),
    ("Ask a question in plain English", "Ask NSIA"),
]

header_row = f"""
<div style="display:flex; border-bottom:2px solid #0f3460; padding:0.5rem 0; margin-bottom:0.25rem;">
    <div style="flex:1; color:{TITLE_COLOR}; font-weight:700;">If you want to know...</div>
    <div style="flex:1; color:{TITLE_COLOR}; font-weight:700;">Go to...</div>
</div>
"""
rows = ""
for question, destination in page_guide:
    rows += f"""
    <div style="display:flex; border-bottom:1px solid #0f3460; padding:0.5rem 0;">
        <div style="flex:1; color:{FONT_COLOR};">{question}</div>
        <div style="flex:1; color:{VALUE_COLOR}; font-weight:600;">{destination}</div>
    </div>
    """

st.markdown(header_row + rows, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Questions? ─────────────────────────────────────────────────────────────

st.header("Questions?")
st.markdown(
    f"""
    <p style="color:{FONT_COLOR}; font-size:1.05rem;">
    Use <b style="color:{VALUE_COLOR};">Ask NSIA</b> (in the sidebar) to ask any question about
    NSIA finances in plain English. Or contact your board president.
    </p>
    """,
    unsafe_allow_html=True,
)
