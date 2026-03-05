# NSIA Bond Dashboard

Board financial transparency dashboard for the North Shore Ice Arena (NSIA). Built with Streamlit, Plotly, and Pandas.

**Fiscal Year 2026** | July 2025 - June 2026 | Data through January 2026

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Pages

### Home — KPI Summary
Top-level metrics: revenue, expenses, net cash flow, hidden outflows, DSCR gauge, and expense approval breakdown.

![Home](screenshots/00_Home.png)

---

### 1. Financial Overview — Budget Variances
Revenue and expense budget vs. CSCG variance analysis, unauthorized budget modifications, and expense approval breakdown.

![Financial Overview](screenshots/01_Financial_Overview.png)

---

### 2. Bond & Debt — Obligations & Hidden Flows
Hidden cash flows (\$916K/yr), annual debt service waterfall, fixed obligations, and scoreboard economics NPV comparison.

![Bond & Debt](screenshots/02_Bond_and_Debt.png)

---

### 3. Revenue & Ads — Advertising Pipeline
Current advertisers, done deals vs. prospects pipeline, historical ad revenue (2014-2024), and scoreboard sponsorship revenue model.

![Revenue & Ads](screenshots/03_Revenue_and_Ads.png)

---

### 4. Operations — Ice Revenue & CSCG
CSCG management relationship breakdown, payment components, expense approval overview, and disclosure summary.

![Operations](screenshots/04_Operations.png)

---

### 5. Variance Alerts — Stoplight Flags
RED/YELLOW/GREEN stoplight system for all budget line items. RED alerts require board attention, YELLOW items need monitoring.

![Variance Alerts](screenshots/05_Variance_Alerts.png)

---

### 6. CSCG Scorecard — Contract Compliance
Contract compliance checklist, disclosed vs. undisclosed CSCG payments, budget modifications without board approval, and governance recommendations.

![CSCG Scorecard](screenshots/06_CSCG_Scorecard.png)

---

### 7. Monthly Financials — P&L, Cash, Receivables
Budget vs. actuals by month, 12-month cash forecast, and contract receivables with collection progress.

![Monthly Financials](screenshots/07_Monthly_Financials.png)

---

### 8. Multi-Year Trends — 3yr Revenue & Payroll
3-year revenue and expense trends, Form 990 highlights, and payroll benchmarking vs. peer park districts.

![Multi-Year Trends](screenshots/08_Multi_Year_Trends.png)

---

### 9. Ice Utilization — Allocation & Gaps
Weekday and weekend ice allocation by club (current vs. proposed), and Winnetka usage gap analysis.

![Ice Utilization](screenshots/09_Ice_Utilization.png)

---

### 10. Reconciliation — Budget vs Financials 4-Way Match
4-way reconciliation across Budget, Financials, GL, and Invoices. Line-item discrepancy analysis, GL adjusting entries impact, and approval traceability.

![Reconciliation](screenshots/10_Reconciliation.png)

## Data Sources

| Source | File | Description |
|--------|------|-------------|
| Budget Reconciliation | `data/budget_reconciliation.xlsx` | Revenue/expense budget vs CSCG comparison |
| Expense Flow | `data/expense_flow.xlsx` | Expense approval methods and CSCG relationship |
| Scoreboard Economics | `data/scoreboard_economics.xlsx` | 10-year scoreboard NPV projections |
| Current Ads | `data/current_ads.xlsx` | Active advertisers and contracts |
| Done Deals / Prospects | `data/done_deals_prospects.xlsx` | Sales pipeline |
| Hockey Schedule | `data/hockey_schedule.csv` | Game schedule and results |
| Monthly P&L | `data/monthly_pnl.csv` | Monthly budget vs actuals |
| Cash Forecast | `data/cash_forecast.csv` | 12-month cash projection |
| Contract Receivables | `data/contract_receivables.csv` | Outstanding receivables |
| Multi-Year Revenue | `data/multiyear_revenue.csv` | 3-year revenue/expense by category |
| Payroll Benchmarks | `data/payroll_benchmarks.csv` | Peer district comparisons |
| Ice Weekday Breakdown | `data/ice_weekday_breakdown.xlsx` | Weekday ice allocation by club |
| Ice Weekend Breakdown | `data/ice_weekend_breakdown.xlsx` | Weekend ice allocation by club |
| Winnetka Usage Gaps | `data/winnetka_usage_gaps.xlsx` | Weekend usage gap analysis |
| General Ledger | `data/general_ledger.xlsx` | 588 GL transactions Jul-Jan |
| Bills Summary | `data/bills_summary.xlsx` | 111 board-approved invoices |
| Proposed Entries | `data/proposed_entries.xlsx` | 19 year-end adjusting journal entries |

## Tech Stack

- **Streamlit** — Web framework
- **Plotly** — Interactive charts
- **Pandas** — Data processing
- **openpyxl** — Excel file reading

## Two-Computer Workflow

> Do NOT develop directly inside OneDrive. Keep repos at `C:\Users\<you>\<repo>` or `C:\dev\<repo>`.

### Stopping work (Computer A)
```powershell
.\scripts\handoff.ps1
```
This stages all changes, commits (with your message or "wip: progress"), and pushes.

### Starting work (Computer B)
```powershell
.\scripts\resume.ps1
```
This pulls latest, installs dependencies, and checks for missing env files.

### Troubleshooting
- **Node version mismatch**: Install the version in `.nvmrc` (`nvm install` / `nvm use`)
- **Missing env vars**: Copy `.env.example` to `.env.local` and fill in values
- **Wrong branch**: `git branch` to check, `git checkout <branch>` to switch
- **Uncommitted changes on other machine**: Run `handoff.ps1` there first, then `resume.ps1` here
- **Merge conflicts after pull**: Resolve conflicts, then `git add . && git rebase --continue`

