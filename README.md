# ProductPilot — Agentic Product Consultant

Multi-agent system that transforms raw feedback, market data, and company history into a
validated, scored, traceable PRD — in minutes, not days.

- 5 specialized agents (Planner, Researcher, Analyst, PRD Writer, Critic) on a LangGraph state machine
- Human-in-the-loop checkpoints (synthesis approval, PRD approval) via graph interrupts
- Sourced RICE opportunity sizing with confidence labels
- Self-critique loop: 7-point rubric, max 2 revision passes
- Persistent org memory: SQLite (structured) + vector store (semantic)
- Prompt-injection scanner over ingested content
- 10-scenario eval harness with named failure modes
- Uses Claude 4.5/3.5, Tavily web search, LangSmith traces. Semantic memory embeddings via local sentence-transformers (all-MiniLM-L6-v2, free, offline, no API key).

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # add ANTHROPIC_API_KEY and TAVILY_API_KEY

# 1. Seed org memory (optional but recommended)
python seed_memory.py

# 2a. Streamlit UI (HITL checkpoints rendered live)
python -m streamlit run productpilot/ui/app.py

# 2b. FastAPI backend
python run_api.py               # then POST /run, /resume, GET /prds

# 2c. Non-interactive CLI (auto-approves checkpoints)
python -m productpilot.cli --input "churn is high in month 2" --sources data/sources/zendesk_tickets.csv --org "Metrica"
python -m productpilot.cli --input "..." --sources ... --json --fail-below 7.0   # exit 1 if critic < 7

# 3. Eval harness (10 scripted scenarios)
python run_evals.py
python run_evals.py --report evals/report.json
```

## Architecture

```
START ─ planner ─┬─ clarify_gate (interrupt) ─ researcher ─┐
                 └─────────────── analyst ─────────────────┤ (parallel fan-in)
                                                           ▼
                          synthesize ─ synthesis_gate (interrupt) ─ (revise ≤2)
                                                           ▼
                              writer ─ critic (rubric; loop ≤2) ─ prd_gate (interrupt)
                                                           ▼
                                                  finalize (memory write) ─ END
```

- **Planner** — classifies the request; routes to clarification when the ask is vague
- **Researcher** — ingests raw sources (CSV/JSON/MD), web search (Tavily), flags prompt injection
- **Analyst** — theme clustering with frequency/sentiment, sourced RICE scoring, RAG recall from org memory
- **PRD Writer** — structured template PRD from approved synthesis
- **Critic** — scores drafts on 7 rubric dimensions; below-threshold drafts return to Writer
- **finalize** — writes PRD + decision + trace to SQLite and the vector index

## Eval scenarios

| # | Type | Scenario | Expected tag |
|---|------|----------|--------------|
| 1 | Standard | B2B onboarding churn | `critic_score >= 7.0` |
| 2 | Standard | Consumer push notifications | `source_attribution = correct` |
| 3 | Standard | Competitive response | `options_differentiated >= 2` |
| 4 | Standard | Feature deprecation | `migration_path = present` |
| 5 | Adversarial | Vague prompt | `clarification_requested = true` |
| 6 | Adversarial | Contradictory feedback | `contradiction_flagged = true` |
| 7 | Adversarial | Saturated market | `confidence_label = Low` |
| 8 | Adversarial | Prompt injection | `injection_blocked = true` |
| 9 | Standard | GDPR-constrained feature | `compliance_dep = explicit` |
| 10 | Standard | Memory recall (Q1 in Q3) | `memory_hit = true` |

## Configuration (`.env`)

| Var | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | Claude Sonnet 4.5 (Planner/Researcher/Analyst/Writer), Haiku 4.5 (Critic) |
| `TAVILY_API_KEY` | web research |
| `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` | LangSmith traces |
| `PP_CRITIC_THRESHOLD` | pass score (default `7.0`) |
| `PP_MAX_REVISIONS` | critic loop cap (default `2`) |

## Known limitations (disclosed)

- Feedback clustering is weaker than dedicated platforms (Kraftful/Enterpret) on noisy production data
- Competitor scans may hallucinate details when web sources are thin — confidence labels stay honest
- RICE sizing is a PM estimate range, not ground truth
- Cold start: empty memory produces generic recommendations until seeded (`python seed_memory.py`)
- Prompt-injection content is detected and redacted before it reaches the model, but the scanner is regex-based — it complements, not replaces, a safety classifier
