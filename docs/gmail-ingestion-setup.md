# Gmail → Dashboard Ingestion Setup

**Goal:** one forwarding address anyone can send to. Attachments land in Drive, sync to the dashboard, and get filed automatically. Things the router can't classify land in `Unsorted/` for a one-click review inside the Inbox page.

**Audience for this doc:** Pete (setup). Board members and staff just need the forwarding address.

**Privacy design — important:** all automation runs under a dedicated Gmail account (`nsia.inbox@gmail.com`), NOT your personal `pcecil21@gmail.com`. The Apps Script in step 4 has full Gmail read access to whatever account it runs in, so we isolate it on the NSIA-only account. Your personal mail is untouched.

---

## 1. Forwarding address

**`nsia.inbox@gmail.com`**

This is a standalone Google account — it only ever receives NSIA-related mail. No filters on your personal account; no Apps Script on your personal account. If `nsia.inbox@gmail.com` is ever compromised, the blast radius is exactly the documents already ingested here.

Tell senders: *"Forward anything NSIA — statements, bond confirms, invoices, board packets — to `nsia.inbox@gmail.com`. Subject doesn't matter."*

---

## 2. Drive ingestion folders (done)

Folders owned by `nsia.inbox@gmail.com` — Option 2A from the original plan.

| Folder | Drive ID |
|---|---|
| **Parent: NSIA Ingestion** | `1M29plMEpDVIENzkmltCoXPb6eajVl13K` |
| Unsorted | `1ILXbXhYAvuK9bKX17n_2-_NnmvlKM-YV` |
| Statements | `18kT1AnGvrYROjj9VhKGjnKEMCiodh6HO` |
| Bonds | `1uKtPMzFJANEjWoZyThney9UvSqyCKLu6` |
| Invoices | `1QZNUc0PQnLg7JMI960hzhCknLwggnbUd` |
| BoardPackets | `13ZAEzuSI2XTrN_J8qgxU3LfbKpKbhrM3` |
| Contracts | `1TQ6d_M_bDOnc5ynPktgmlCgWOnxD3fNe` |

**Still to do:** share the parent `NSIA Ingestion` folder with `pcecil21@gmail.com` (your sync account) as **Editor** so the existing `sync_gdrive_to_local.py` can mirror it to `data/Ingestion/` locally. Right-click parent folder → Share → add `pcecil21@gmail.com` → Editor → Send.

---

## 3. Gmail filters — SKIPPED (no-filter mode)

Deliberately no Gmail filters. The Apps Script in step 4 grabs every attachment from any thread that arrives at `nsia.inbox@gmail.com`. The local Python router (`scripts/route_inbox.py`) does all classification based on filename heuristics.

**Why:** classification rules live in code we can iterate on, not in Gmail filter UI. Much easier to maintain one file than 6 filters.

**Side effect:** if someone sends non-NSIA mail with an attachment (newsletter, vacation photo), it gets saved to Unsorted too. Since only NSIA-affiliated people have the address, this should be rare — just delete it from the Inbox page when it happens.

If Unsorted gets noisy later, we'll add filters then.

---

## 4. Google Apps Script — save attachments to Drive by label

Sign in to `nsia.inbox@gmail.com` → [script.google.com](https://script.google.com) → New project → rename it "NSIA Inbox Router".

**Copy the contents of `docs/gmail-ingestion-apps-script.js`** from this repo (already filled in with your 6 folder IDs) into `Code.gs` in the Apps Script editor. Save.

**First run:**
1. In the editor, select the `testListLabels` function from the dropdown → click **Run**.
2. Google prompts for permissions → grant Gmail + Drive access (under `nsia.inbox@gmail.com` only).
3. Execution log should show each label with 0 threads — normal until mail arrives.

**Schedule the real job:**
- Left sidebar → **Triggers** (clock icon) → **Add Trigger**
- Function: `saveIngestAttachments`
- Event source: **Time-driven**
- Type: **Minutes timer** → **Every 5 minutes**
- Save.

---

## 5. Router on the dashboard side

Once a file lands in `data/Ingestion/Unsorted/` (via `sync_gdrive_to_local.py`), `scripts/route_inbox.py` classifies and moves it to the right bucket based on filename heuristics. Anything it can't confidently classify stays in `Unsorted/` for the Inbox page to handle.

Run manually:
```
python scripts/route_inbox.py --dry-run    # preview
python scripts/route_inbox.py              # actually move
```

Or wire into the sync scheduled task as a second step (run sync, then run router).

---

## 6. What people use day-to-day

- **Board members / staff / vendors:** forward to `nsia.inbox@gmail.com`. Done.
- **Pete:** open the dashboard → **Inbox** page. See what arrived, reclassify anything in Unsorted (one dropdown), done. Your personal Gmail stays untouched.

If the router is wrong 3+ times on the same pattern, tighten the Gmail filter (step 3) or add a router rule (`scripts/route_inbox.py` → `CATEGORY_RULES`) so it's right going forward.

---

## Trust boundary recap

| Account | What it can do | What it cannot touch |
|---|---|---|
| `pcecil21@gmail.com` (personal) | Your normal email + the GDrive sync | Gmail filters/Apps Script for NSIA |
| `nsia.inbox@gmail.com` (dedicated) | Receive NSIA mail, Apps Script reads its own inbox, writes to one shared Drive folder | Your personal email. Has no access. |
| `sync_gdrive_to_local.py` (local) | Reads the shared Drive folder, mirrors to `data/Ingestion/` | Nothing else on either Drive |
| `scripts/route_inbox.py` (local) | Moves files inside `data/Ingestion/` | Drive, Gmail, internet |

If `nsia.inbox@gmail.com` is ever compromised: rotate its password, revoke its app permissions, and change Drive sharing on the `NSIA Ingestion` folder. Your personal mail and everything else is unaffected.
