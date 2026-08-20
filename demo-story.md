# ProductPilot — demo story (the emulated use case)

This is the complete backstory for the demo: who the company is, what the product
is, what problem the PM walks in with, and what the `data/` folder says about it.
Read this once before the demo — it turns the pipeline demo into a product story.

---

## 1. The company — Metrica

**Metrica** is a mid-market B2B SaaS analytics platform. Teams of 5–400 seats use
it to build dashboards, run reports, and share insights across their company.

- **Product:** hosted analytics — dashboards, report builder, CSV export,
  scheduled digests, per-seat billing, API v2.
- **Market:** crowded "activation tooling" space in 2026 (see section 3).
- **Customers:** Acme Retail (Head of Ops), Northwind (PM), Globex (Data lead),
  TinyCo (Founder) — plus ~1,200 trial signups per quarter.
- **Business model:** per-seat subscriptions; expansion depends on trial → active
  conversion and keeping mid-market accounts past month 2.
- **Context:** the PM team (e.g. Priya, owner of the Q1 onboarding PRD) uses
  **ProductPilot** as their agentic product consultant — it ingests the org's raw
  feedback, researches, scores options, drafts and self-critiques PRDs, and
  commits decisions to org memory.

> Note on names: "Acme Retail" is a Metrica **customer**; "ACME Analytics" in the
> competitor scan is an unrelated **competitor** — a coincidence of the corpus,
> useful to mention only if someone asks.

**Timeline (this is why the demo works):**

| Quarter | What happened |
|---|---|
| Q1 2026 | Onboarding crisis: 12% trial activation. Metrica ships PRD "Onboarding Redesign": wizard simplified to 5 fields, activation email fixed (RICE 14.2 / 11.8, critic 8.1). NPS deep-dive: 31. |
| Q2 2026 | Onboarding fix in market; Q2 growth push begins. Competitor scan frozen. |
| Q3 2026 | **The demo moment:** "Churn is high in month 2." The PM re-opens the case with ProductPilot — this time Q1 knowledge is already in org memory. |

---

## 2. The product (what Metrica's analytics tool does)

- Analytics dashboards (the "first screen" users find overwhelming)
- Report builder + CSV export (legacy CSV export broken since API v2 migration)
- Scheduled email digests (landing in spam for ~20% of users)
- Alerts — **none**: no Slack, no push notifications (ops teams live in Slack)
- Billing — per-seat, but seat management is opaque and upgrade path is
  sales-contact-first
- Enterprise features missing: SSO, documented API rate limits, GDPR data
  retention policy, team invites during onboarding

The voice-of-customer corpus (section 4) is all the evidence the PM has.

---

## 3. The problem the PM walks in with

**Request:** *"Churn is high in month 2."*

The signals behind it:

1. **Trial activation is 12%** — only 1 in 8 trials ever reaches an active
   workspace (T-1008, Q1 PRD). Onboarding is the funnel's first leak.
2. **Month-2 value cliff** — value is clear in month 1, "disappears" in month 2:
   61 detractors cite it (NPS deep-dive); tickets T-1003, reviews G-07, NPS N-02
   all say the same. No guided value cadence after the trial month.
3. **First-run confusion** — the 9-field wizard and unguided first screen chase
   users away (T-1001, T-1004, G-02, G-11, N-04, N-08).
4. **Broken trust / hygiene issues** — activation email delayed or in spam
   (T-1002, T-1010), legacy CSV export broken for finance workflows (T-1017,
   G-14, N-13), GDPR retention unanswerable (T-1015).
5. **Alerting gap** — Slack + push requests repeat across every channel
   (T-1009, T-1012, G-04, G-05, G-08, N-05, N-11).
6. **Enterprise blockers** — SSO setup takes days, deals stall (T-1016, G-13).
7. **Market pressure** — competitors ship onboarding copilots (ACME), playbooks
   (BETA), AI setup wizards (GAMMA). Differentiation must be depth of analysis +
   traceability, not feature checklists.

**And the contradiction that makes it interesting:** TinyCo says onboarding is
*too simple* — they want deeper configuration in the first run — while everyone
else says it's too complex. A good answer segments first-run UX by user size.

---

## 4. What `data/` contains (the evidence map)

### `data/sources/` — raw feedback, fed to ProductPilot in the demo

| File | Role | Key evidence |
|---|---|---|
| `zendesk_tickets.csv` | support tickets (200 rows) | activation 12% (T-1008), month-2 churn (T-1003), wizard complexity (T-1004), GDPR (T-1015), legacy export (T-1017), Slack (T-1012) |
| `g2_reviews.csv` | public reviews 1–5★ | "setup took a day" (G-11), "second month dip" (G-07), "Slack please" (G-05), "SSO would unblock us" (G-13), "digest in spam" (G-04) |
| `nps_survey.csv` | NPS comments | low scores cluster on first-run confusion, month-2 value, alerting (N-04, N-02, N-05, N-11) |
| `interview_transcripts.md` | 4 customer calls | depth + the TinyCo contradiction (too simple vs too complex) |
| `competitor_scan.md` | market notes | crowded activation space; differentiator = depth + traceability |

### `data/memory_seed/` — org memory, pre-seeded so recall can be demonstrated

| File | Content | Why it matters in the demo |
|---|---|---|
| `q1_onboarding_prd.md` | Approved Q1 PRD (critic 8.1, RICE 14.2/11.8) | the canonical onboarding reference the analyst should recall |
| `q1_nps_deepdive.md` | NPS 31; month-2 cliff = 61 detractors | independently corroborates the Q3 churn request |
| `q1_competitive_scan.md` | Frozen Q1 positioning | keeps the analyst from re-researching known facts |

### `data/db/` — generated at runtime (not hand-authored)

`productpilot.db` (committed PRDs), `chroma/` (vector index), `memory_blob.json`
(doc records). Rebuilt with `Remove-Item -Recurse -Force data\db; python
seed_memory.py`. This is where the demo run *writes*, not reads.

---

## 5. The emulated use case — full narrative

> **The PM (Priya) opens ProductPilot on a Q3 morning:** churn tickets and NPS
> comments keep mentioning the second month. She types the request and attaches
> the raw feedback files.

**Step 1 — Planner.** ProductPilot recognizes the request is under-specified
(which product area? which segment?) and **pauses for a human** instead of
guessing. Priya answers: *"The analytics product, new trial signups."*

**Step 2 — Research.** The Researcher ingests all five sources (parsing the real
CSVs, sampling 200 tickets, scanning for prompt injection — quarantining
anything malicious before it reaches a model) and runs a web scan of the
competitive landscape.

**Step 3 — Analyst.** Clusters the evidence into themes with frequency +
sentiment: onboarding friction, trial activation, **month-2 value cliff**,
legacy CSV export, alerting. Detects the TinyCo contradiction. Recalls the Q1
PRD and NPS deep-dive from org memory — *Q1 decisions inform Q3 work* — and
prices three options with sourced RICE and confidence labels.

**Step 4 — Synthesis gate.** Priya reviews themes + options, approves.

**Step 5 — Writer + Critic.** The PRD is drafted, then scored against a
7-dimension rubric (problem clarity, segment, metrics, opportunity size, risk,
dependencies, assumptions). If any dimension is below the 7.0 bar, the critic
demands revisions and the writer revises — capped at 2 loops. The final draft
lands above the bar.

**Step 6 — PRD gate.** Priya approves; the PRD is **committed to org memory** —
next quarter, this run is the knowledge that informs the next request. Every
decision is traceable: source row → theme → RICE → PRD line.

**The story's arc:** Q1 fixed onboarding (12% activation, shipped). Q3 re-opens
the case with new evidence and *memory of what was already decided* — so the new
PRD doesn't re-litigate the wizard, it attacks the month-2 cliff (check-in
cadence, alerts, value instrumentation) that Q1 data flagged but Q1 scope
deferred.

---

## 6. Numbers cheat sheet (quote these during the demo)

- Trial activation: **12%** → target 25% (Q1 PRD)
- Month-2 value cliff: **61 detractors** (Q1 NPS deep-dive)
- NPS: **31** (promoters 42% / passives 31% / detractors 27%)
- Q1 RICE: wizard simplification **14.2**, activation email **11.8** (high confidence)
- Critic: Q1 PRD scored **8.1/10**; mock demo runs land **≥ 7.0** (threshold)
- Sources: **200 tickets** + reviews + NPS + interviews + competitor scan
- Quarantined injections: shown on the synthesis screen if a poisoned file is added

## 7. One-liners

- *"Each agent is a LangGraph node; every checkpoint is a real human approval."*
- *"Nothing commits to memory without a human saying yes."*
- *"Q1's PRD is Q3's input — that's what org memory buys you."*
- *"The critic can fire the writer up to twice before the PM sees the draft."*
- *"Every PRD line traces back to a source row."*