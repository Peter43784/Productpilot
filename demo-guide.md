# ProductPilot — UI demo guide

## Scenario

> "Churn is high in month 2" — a PM walks in with a churn signal, ProductPilot
> researches the org's raw feedback, proposes RICE-sized options, writes and
> self-critiques a PRD, and commits it to org memory — with a human approving
> every checkpoint.

**Talking points baked in:** 5-agent LangGraph flow, human-in-the-loop
checkpoints, RICE scoring, self-critiquing writer (revision loop), org memory
recall, prompt-injection quarantine, 100% reasoning trace.

---

## 0. Environment (one-time)

PowerShell, from the project root:

```powershell
$env:PYTHONPATH="D:\Development\Productpilot"
pip install -r requirements.txt
```

**Keys required:** `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` in `.env`.

### Semantic memory (local, free, no API key)

Uses local sentence-transformers (`all-MiniLM-L6-v2`, 384-dim, free, offline):

```powershell
# No extra config needed — local embeddings work out of the box
# Verify:
python -c "from productpilot.memory.vector_store import embed; print(len(embed(['test'])[0]))"
```

Expect: `384`

---

## 1. Prepare artifacts (fresh, reproducible state)

```powershell
Remove-Item -Recurse -Force data\db            # wipe previous runs
python seed_memory.py                          # seed 3 Q1 memory docs
```

Expected: `Seeded 3 new memory doc(s)`, `Vector index: 3 docs`.

Input artifacts used by the demo:

| Artifact | Role |
|---|---|
| `data/sources/zendesk_tickets.csv` (200 tickets) | month-2 churn complaints |
| `data/sources/g2_reviews.csv` | onboarding friction reviews |
| `data/sources/nps_survey.csv` | promoter/detractor signal |
| `data/sources/interview_transcripts.md` | in-context quotes |
| `data/sources/competitor_scan.md` | competitor angle |
| `data/memory_seed/q1_onboarding_prd.md` (+2) | org memory — proves recall |

## 2. Start the UI

```powershell
python -m streamlit run productpilot/ui/app.py
```

Open `http://localhost:8501`. You should see the **Run ProductPilot** form
(no errors — verified).

## 3. Run the scenario (script for the demo)

### 3.1 Kick-off
- **Request:** `Churn is high in month 2`
- **Org:** `Metrica` (see `demo-story.md` for the full company backstory)
- **Sources:** select all 5 `data/sources/*` files (leave uploader empty)
- Click **Run ProductPilot**

> Say: "The planner detects the request is underspecified for research and
> halts for a human instead of guessing."

### 3.2 Checkpoint 1 — Clarification (⏸)
The app asks *"Which product area and user segment?"*
- Answer: `The analytics product, new trial signups`
- Click **Continue**

> Say: "The answer is routed back into state; the Q1 memory docs (seeded in step
> 1) now match — by semantic similarity — so the analyst can recall prior decisions."

### 3.3 Checkpoint 2 — Synthesis approval (⏸)
You'll see themes with sentiment + mention counts, contradictions, RICE
options, and (in the trace) injection quarantine.
- Click **Approve synthesis → draft PRD**

> Say: "The researcher summarized all raw sources (real parse of the CSVs,
> 200-row samples, web scan), the analyst clustered themes and priced RICE."

### 3.4 Checkpoint 3 — PRD approval (⏸)
- Left: full PRD draft; Right: **critic rubric** — 7 dimension bars + overall
- Click **Approve PRD → commit to memory**

> Say: "The writer drafted it, the critic scored it against the rubric; passes at 8/10, well above the 7.0 bar. Optionally reject once to show
> the revision loop live."

### 3.5 Done — committed
- Green **"Committed to org memory"**, PRD id + critic scores + RICE options
- **Org memory — semantic search test:** leave the query as `Churn is high in
  month 2` → you'll see the Q1 docs matched
- **Reasoning trace:** expandable JSON — every source row → theme → RICE →
  decision, 100% traceable

> Say: "The PRD is now part of org memory — next quarter this run informs the
> next one. Nothing was committed without a human approving it."

### 3.6 (Optional) Show the critic loop
At checkpoint 3, click **Reject & revise** — the writer revises and the critic
rescales. Then approve.

## 4. B-roll (if time permits)

- **Injection defense:** add `evals/fixtures/injection_review.csv` as a source
  → the synthesis screen shows *"N prompt-injection attempt(s) quarantined"*
  (sanitized before the model ever sees it). Fixture already generated.
- **Contradictions:** add `evals/fixtures/contradictory_tickets.csv` → a
  contradiction warning appears on the synthesis screen.
- **Recent PRDs** sidebar shows committed history.

## 5. Reset for a repeat run

```powershell
Remove-Item -Recurse -Force data\db; python seed_memory.py
```

## 6. LangSmith tracing (optional)

Set in `.env`:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=productpilot
```

Then repeat section 3. Traces will appear in LangSmith with full agent span details.