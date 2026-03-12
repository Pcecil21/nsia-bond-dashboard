"""
NSIA Alert Digest — Automated Report Generator

Runs the Alert Monitor agent against current dashboard data and optionally
emails the digest to board members.

Usage:
    # Generate digest to stdout
    python scripts/alert_digest.py

    # Generate and save to file
    python scripts/alert_digest.py --output reports/digest_2026-03-12.md

    # Generate and email (requires SMTP config in .env or secrets)
    python scripts/alert_digest.py --email

    # Dry run (show what would be sent without sending)
    python scripts/alert_digest.py --email --dry-run

Schedule with Windows Task Scheduler or cron:
    # Weekly Monday 7am
    schtasks /create /tn "NSIA Alert Digest" /tr "python C:\\path\\to\\scripts\\alert_digest.py --email" /sc weekly /d MON /st 07:00

    # Or cron (WSL/Linux):
    0 7 * * 1 cd /path/to/nsia-bond-dashboard && python scripts/alert_digest.py --email
"""

import argparse
import os
import sys
import smtplib
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Patch st.cache_data so data_loader works outside Streamlit
import streamlit as st
st.cache_data = lambda *a, **kw: (lambda f: f) if not a else a[0]


def load_config():
    """Load email config from environment or .env file."""
    env_path = PROJECT_ROOT / ".env"
    config = {}

    # Try .env file
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip().strip('"').strip("'")

    # Environment variables override .env
    for key in ["ANTHROPIC_API_KEY", "SMTP_HOST", "SMTP_PORT", "SMTP_USER",
                "SMTP_PASSWORD", "DIGEST_FROM", "DIGEST_TO", "DIGEST_CC"]:
        env_val = os.environ.get(key)
        if env_val:
            config[key] = env_val

    return config


def build_digest_data():
    """Collect all dashboard data for the alert digest."""
    from utils.data_loader import (
        compute_kpis,
        compute_variance_alerts,
        compute_cscg_scorecard,
        load_hidden_cash_flows,
        load_cash_forecast,
        load_cscg_relationship,
    )

    kpis = compute_kpis()
    alerts = compute_variance_alerts()
    scorecard = compute_cscg_scorecard()
    hidden = load_hidden_cash_flows()
    cash = load_cash_forecast()
    cscg = load_cscg_relationship()

    red_alerts = alerts[alerts["Severity"] == "RED"]
    yellow_alerts = alerts[alerts["Severity"] == "YELLOW"]
    non_green = alerts[alerts["Severity"] != "GREEN"]

    data = []
    data.append(f"NSIA AUTOMATED ALERT DIGEST — {date.today().strftime('%B %d, %Y')}")
    data.append(f"FY2026 | Data through January 2026\n")

    # Key metrics
    data.append("=== KEY METRICS ===")
    data.append(f"DSCR: {kpis['dscr']:.2f}x")
    data.append(f"Net Cash Flow (est.): ${kpis['net_cash_flow']:,.0f}")
    data.append(f"Hidden Outflows: ${kpis['hidden_cash_outflows']:,.0f}/yr")
    data.append(f"Board-Approved Expenses: {kpis['pct_board_approved']*100:.1f}%")
    data.append("")

    # Variance alerts
    data.append("=== VARIANCE ALERTS ===")
    data.append(f"RED: {len(red_alerts)} | YELLOW: {len(yellow_alerts)}")
    if not red_alerts.empty:
        data.append("\nRED ALERTS:")
        data.append(red_alerts[["Category", "Line Item", "Variance $",
                                 "Variance %", "Assessment"]].to_csv(index=False))
    if not yellow_alerts.empty:
        data.append("\nYELLOW ALERTS:")
        data.append(yellow_alerts[["Category", "Line Item", "Variance $",
                                    "Variance %"]].to_csv(index=False))
    if not non_green.empty:
        data.append(f"\nNet Budget Impact: ${non_green['Variance $'].sum():+,.0f}")
    data.append("")

    # CSCG compliance
    data.append("=== CSCG COMPLIANCE ===")
    data.append(scorecard[["Contract Term", "Status"]].to_csv(index=False))
    non_compliant = len(scorecard[scorecard["Status"] == "NON-COMPLIANT"])
    data.append(f"Non-Compliant Items: {non_compliant}")
    data.append("")

    # Cash position
    data.append("=== CASH FORECAST ===")
    end_cash = cash["Cumulative Cash"].iloc[-1]
    min_cash = cash["Cumulative Cash"].min()
    min_month = cash.loc[cash["Cumulative Cash"].idxmin(), "Month"]
    data.append(f"Projected Ending Cash: ${end_cash:,.0f}")
    data.append(f"Lowest Point: ${min_cash:,.0f} ({min_month})")
    data.append("")

    return "\n".join(data)


def generate_ai_digest(data_payload: str, api_key: str) -> str:
    """Send data to the Alert Monitor agent and get the digest."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    # Load the alert monitor agent prompt
    agent_path = PROJECT_ROOT / "agents" / "infrastructure" / "16-alert-monitor.claude.md"
    if not agent_path.exists():
        print(f"ERROR: Agent prompt not found at {agent_path}")
        sys.exit(1)

    system_prompt = agent_path.read_text(encoding="utf-8")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": (
                f"Generate a concise alert digest for the NSIA board. "
                f"Prioritize items that require immediate action. "
                f"Format for email readability.\n\n{data_payload}"
            ),
        }],
    )
    return response.content[0].text


def send_email(subject: str, body: str, config: dict, dry_run: bool = False):
    """Send the digest via SMTP."""
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                "DIGEST_FROM", "DIGEST_TO"]
    missing = [k for k in required if k not in config]
    if missing:
        print(f"ERROR: Missing email config: {', '.join(missing)}")
        print("Add these to .env or set as environment variables:")
        print("  SMTP_HOST=smtp.gmail.com")
        print("  SMTP_PORT=587")
        print("  SMTP_USER=your@email.com")
        print("  SMTP_PASSWORD=app-password")
        print("  DIGEST_FROM=nsia-dashboard@example.com")
        print("  DIGEST_TO=board-president@example.com")
        print("  DIGEST_CC=board-member@example.com (optional)")
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["DIGEST_FROM"]
    msg["To"] = config["DIGEST_TO"]
    if config.get("DIGEST_CC"):
        msg["Cc"] = config["DIGEST_CC"]

    # Plain text version
    msg.attach(MIMEText(body, "plain"))

    # Simple HTML version (wrap markdown in pre for readability)
    html_body = f"""<html><body>
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 800px; margin: 0 auto; padding: 20px;">
<h2 style="color: #1a1a2e;">NSIA Alert Digest — {date.today().strftime('%B %d, %Y')}</h2>
<pre style="font-size: 14px; line-height: 1.6; white-space: pre-wrap;">{body}</pre>
<hr>
<p style="color: #666; font-size: 12px;">
Generated by NSIA Bond Dashboard | AI-powered governance monitoring
</p>
</div></body></html>"""
    msg.attach(MIMEText(html_body, "html"))

    recipients = [config["DIGEST_TO"]]
    if config.get("DIGEST_CC"):
        recipients.extend(config["DIGEST_CC"].split(","))

    if dry_run:
        print(f"\n--- DRY RUN ---")
        print(f"From: {config['DIGEST_FROM']}")
        print(f"To: {config['DIGEST_TO']}")
        if config.get("DIGEST_CC"):
            print(f"Cc: {config['DIGEST_CC']}")
        print(f"Subject: {subject}")
        print(f"Body length: {len(body)} chars")
        print(f"--- Would send to {len(recipients)} recipient(s) ---\n")
        return

    with smtplib.SMTP(config["SMTP_HOST"], int(config["SMTP_PORT"])) as server:
        server.starttls()
        server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
        server.sendmail(config["DIGEST_FROM"], recipients, msg.as_string())

    print(f"Email sent to {', '.join(recipients)}")


def main():
    parser = argparse.ArgumentParser(description="NSIA Alert Digest Generator")
    parser.add_argument("--output", "-o", help="Save digest to file")
    parser.add_argument("--email", action="store_true", help="Send digest via email")
    parser.add_argument("--dry-run", action="store_true", help="Show email without sending")
    parser.add_argument("--raw", action="store_true", help="Output raw data without AI analysis")
    args = parser.parse_args()

    config = load_config()

    print("Collecting dashboard data...")
    data_payload = build_digest_data()

    if args.raw:
        digest = data_payload
    else:
        api_key = config.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not found in .env or environment")
            sys.exit(1)
        print("Generating AI digest...")
        digest = generate_ai_digest(data_payload, api_key)

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(digest, encoding="utf-8")
        print(f"Digest saved to {output_path}")

    if args.email or args.dry_run:
        subject = f"NSIA Alert Digest — {date.today().strftime('%B %d, %Y')}"
        send_email(subject, digest, config, dry_run=args.dry_run)

    if not args.output and not args.email and not args.dry_run:
        print("\n" + digest)


if __name__ == "__main__":
    main()
