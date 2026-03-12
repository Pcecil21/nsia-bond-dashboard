# NSIA Agent Suite — Master Index

## Overview

16 specialized Claude sub-agents for North Shore Ice Arena LLC governance, financial oversight, operations management, and marketing strategy. Each `.claude.md` file is a fully self-contained system prompt ready to deploy as a Claude Project or standalone instance.

**Organization:** North Shore Ice Arena LLC (501(c) nonprofit)
**Ownership:** Joint — Wilmette Hockey Association & Winnetka Hockey Club
**Governance Model:** Volunteer board oversees a contracted management company
**Usage Model:** Ad hoc — agents activate when documents are uploaded for analysis

---

## Shared Escalation Thresholds (All Agents)

| Threshold | Trigger |
|-----------|---------|
| $1,000 single item | Any transaction, expense, or financial exposure ≥ $1,000 |
| 10–15% variance | Budget line item deviation from approved budget |
| Board vote required | Per LLC operating agreement |
| Management contract threshold | Per management company agreement |

---

## Agent Directory

### Financial Oversight (Agents 1–5)

| # | Agent | File | Purpose |
|---|-------|------|---------|
| 1 | Bank Statement Analyst | `financial-oversight/01-bank-statement-analyst.claude.md` | Parse transactions, flag anomalies, track cash flow |
| 2 | Budget & GL Reconciler | `financial-oversight/02-budget-gl-reconciler.claude.md` | Budget-to-actual comparison, variance analysis |
| 3 | Invoice Auditor | `financial-oversight/03-invoice-auditor.claude.md` | Invoice accuracy, duplicates, rate compliance |
| 4 | Revenue & Utilization Tracker | `financial-oversight/04-revenue-utilization-tracker.claude.md` | Revenue monitoring, utilization rates, projections |
| 5 | Financial Health Monitor | `financial-oversight/05-financial-health-monitor.claude.md` | Financial ratios, reserves, burn rate, fiscal health |

### Contract & Compliance (Agents 6–7)

| # | Agent | File | Purpose |
|---|-------|------|---------|
| 6 | Contract Analyst | `contract-compliance/06-contract-analyst.claude.md` | Contract terms, obligations, deadlines, risk |
| 7 | Compliance & Insurance Monitor | `contract-compliance/07-compliance-insurance-monitor.claude.md` | Regulatory tracking, insurance coverage, filings |

### Operations Efficiency (Agents 8–10)

| # | Agent | File | Purpose |
|---|-------|------|---------|
| 8 | Ice Time & Scheduling Optimizer | `operations/08-ice-time-scheduling-optimizer.claude.md` | Utilization analysis, scheduling recommendations |
| 9 | Facility & Maintenance Analyst | `operations/09-facility-maintenance-analyst.claude.md` | Maintenance costs, energy, equipment lifecycle |
| 10 | Management Company Performance Scorer | `operations/10-management-company-scorer.claude.md` | KPI scorecards, contractual performance evaluation |

### Marketing & Growth (Agents 11–12)

| # | Agent | File | Purpose |
|---|-------|------|---------|
| 11 | Marketing Strategist | `marketing-growth/11-marketing-strategist.claude.md` | Program marketing, community engagement, growth |
| 12 | Pricing & Competitive Analyst | `marketing-growth/12-pricing-competitive-analyst.claude.md` | Rate benchmarking, competitive intelligence, pricing |

### Infrastructure (Agents 13–16)

| # | Agent | File | Purpose |
|---|-------|------|---------|
| 13 | Data Ingestion Agent | `infrastructure/13-data-ingestion-agent.claude.md` | Parse, validate, normalize all input data |
| 14 | Metrics Calculator | `infrastructure/14-metrics-calculator.claude.md` | Compute financial and operational metrics |
| 15 | Report Generator | `infrastructure/15-report-generator.claude.md` | Synthesize multi-agent outputs into board reports |
| 16 | Alert Monitor | `infrastructure/16-alert-monitor.claude.md` | Threshold-based alerting and deadline tracking |

---

## Cross-Agent Routing Map

When an agent encounters analysis outside its scope, it flags for a specific peer agent. Common routing patterns:

```
Invoice uploaded
  → Data Ingestion Agent (parse/validate)
  → Invoice Auditor (audit)
  → Budget & GL Reconciler (budget alignment)
  → Contract Analyst (rate compliance, if contract terms referenced)

Bank statement uploaded
  → Data Ingestion Agent (parse/validate)
  → Bank Statement Analyst (categorize, flag anomalies)
  → Budget & GL Reconciler (GL reconciliation)
  → Financial Health Monitor (cash position update)

Management company monthly report
  → Data Ingestion Agent (parse/validate)
  → Management Company Performance Scorer (scorecard update)
  → Revenue & Utilization Tracker (revenue data)
  → Budget & GL Reconciler (budget comparison)

Board meeting prep
  → Report Generator (synthesize all available agent outputs)
  → Alert Monitor (generate alert digest)
```

---

## Deployment Notes

1. **Each file is independent.** Copy-paste any single `.claude.md` as a system prompt for a Claude Project or conversation.
2. **No inter-agent communication.** Agents reference each other by name for human routing, but do not directly call each other.
3. **Data flows through the board president.** Upload a document → get agent output → route to another agent if flagged.
4. **Report Generator requires multi-agent input.** Feed it outputs from 2+ agents to produce a board report.
5. **Alert Monitor is cumulative.** Feed it any data or agent output to get a threshold evaluation.

---

## Version

- **Created:** March 2026
- **Author:** Pete Cecil, Board President, NSIA
- **Framework:** Claude Project system prompts (Anthropic)
