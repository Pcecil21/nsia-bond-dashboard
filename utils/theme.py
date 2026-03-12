"""
NSIA Bond Dashboard — Shared Theme Configuration

Central source of truth for colors, chart styling, CSS, and formatters.
Import from here instead of duplicating in each page.
"""
import streamlit as st


# ── Color Palette ─────────────────────────────────────────────────────────
CHART_BG = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(168,178,209,0.15)"
FONT_COLOR = "#a8b2d1"
TITLE_COLOR = "#ccd6f6"
VALUE_COLOR = "#e6f1ff"
BG_DARK = "#0a192f"
BG_CARD = "#1a1a2e"
BG_CARD_END = "#16213e"
BORDER_COLOR = "#0f3460"

# Semantic colors
RED = "#eb144c"
YELLOW = "#fcb900"
GREEN = "#00d084"
BLUE = "#0984e3"
PURPLE = "#6c5ce7"
ORANGE = "#e17055"
TEAL = "#00b894"
CYAN = "#64ffda"

# Chart accent palette (10 colors for categorical data)
ACCENT_COLORS = [
    "#64ffda", "#f78da7", "#fcb900", "#7bdcb5", "#00d084",
    "#8ed1fc", "#0693e3", "#abb8c3", "#eb144c", "#ff6900",
]

# Status colors
STATUS_COLORS = {
    "Active": GREEN,
    "Expiring Soon": YELLOW,
    "Expired": RED,
    "COMPLIANT": GREEN,
    "NON-COMPLIANT": RED,
    "AUTO-PAY": YELLOW,
    "RED": RED,
    "YELLOW": YELLOW,
    "GREEN": GREEN,
}


# ── Chart Styling ─────────────────────────────────────────────────────────

def style_chart(fig, height=450):
    """Apply consistent dark theme to any Plotly figure."""
    fig.update_layout(
        height=height,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color=FONT_COLOR, size=12),
        title_font=dict(color=TITLE_COLOR, size=18),
        xaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=FONT_COLOR)),
        yaxis=dict(gridcolor=GRID_COLOR, tickfont=dict(color=FONT_COLOR)),
        legend=dict(font=dict(color=FONT_COLOR)),
        margin=dict(t=60, b=40),
    )
    return fig


# ── CSS Injection ─────────────────────────────────────────────────────────

METRIC_CSS = """
<style>
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    [data-testid="stMetric"] label { color: #a8b2d1 !important; }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { color: #e6f1ff !important; }
</style>
"""


def inject_css():
    """Inject the standard metric card CSS. Call once per page."""
    st.markdown(METRIC_CSS, unsafe_allow_html=True)


# ── Number Formatters ─────────────────────────────────────────────────────

def fmt_dollar(value, decimals=0):
    """Format a number as a dollar amount: $1,234 or $1,234.56"""
    if value is None:
        return "N/A"
    if decimals == 0:
        return f"${value:,.0f}"
    return f"${value:,.{decimals}f}"


def fmt_dollar_delta(value, decimals=0):
    """Format a number as a signed dollar amount: +$1,234 or -$1,234"""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    if decimals == 0:
        return f"{sign}${value:,.0f}"
    return f"{sign}${value:,.{decimals}f}"


def fmt_pct(value, decimals=1):
    """Format a decimal as a percentage: 0.255 → 25.5%"""
    if value is None:
        return "N/A"
    pct = value * 100 if abs(value) <= 1 else value
    return f"{pct:.{decimals}f}%"


def fmt_compact(value):
    """Format large numbers compactly: $1.2M, $456K, $1,234"""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 10_000:
        return f"{sign}${abs_val / 1_000:.0f}K"
    return f"{sign}${abs_val:,.0f}"


# ── Severity Helpers ──────────────────────────────────────────────────────

def severity_color(severity: str) -> str:
    """Return hex color for a severity/status string."""
    return STATUS_COLORS.get(severity.upper() if severity else "", FONT_COLOR)


def severity_icon(severity: str) -> str:
    """Return emoji for a severity level."""
    icons = {"RED": "\U0001f534", "YELLOW": "\U0001f7e1", "GREEN": "\U0001f7e2"}
    return icons.get(severity.upper() if severity else "", "\u26aa")
