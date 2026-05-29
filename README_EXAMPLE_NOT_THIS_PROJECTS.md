# Mini Nivii

A domain-scoped, semantics-grounded NL-to-SQL business intelligence agent.

Mini Nivii takes a natural language question about point-of-sale data and returns a structured analytical narrative — SQL, result table, and recommendation-grade insight — not just raw rows. The pipeline decomposes the problem into auditable stages (DIN-SQL pattern) with explicit tradeoff reasoning at each layer.

---

## Quick Start

```bash
git clone <repo>
cd minivii_challenge
# Place data.csv in the repo root (not committed — volume-mounted)
docker compose up
# Open http://localhost:3001
```

See [runtime_performance.md](runtime_performance.md) for Ollama host vs container latency (install host Ollama on Mac/Windows for acceptable inference speed).

**First-run note: ~29 GB download** (`qwen2.5-coder:14b` ~9 GB + `qwen3:32b` ~20 GB) and **~20 GB RAM or VRAM** recommended for the default model pair. Compose pulls into the **container** `ollama_cache` volume. If `/health` shows **host** Ollama (`host.docker.internal`), pull **both** tags on the host too (`ollama pull qwen2.5-coder:14b` and `ollama pull qwen3:32b`) — otherwise SQL may run and synthesis can fail with `model not found` (404). See [runtime_performance.md](runtime_performance.md#separate-model-libraries-host-vs-container).

**Compose bootstrapping:** On first clone, Ollama pulls models while `nlp` and `ui` wait on `ollama: service_healthy`. After models are cached, run `docker compose down && docker compose up` (or start `nlp`/`ui` manually) so the full stack comes up.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DB_URL` | `http://db:8001` | Database service endpoint |
| `OLLAMA_URL` | *(auto)* | Ollama endpoint. Unset: probe host, then fall back to container. Set to override either path. |
| `OLLAMA_HOST_URL` | `http://host.docker.internal:11434` | Host Ollama probe target when `OLLAMA_URL` is unset |
| `OLLAMA_FALLBACK_URL` | `http://ollama:11434` | Container Ollama fallback when host probe fails |
| `SQL_MODEL` | `qwen2.5-coder:14b` | SQL generation and refinement |
| `SYNTHESIS_MODEL` | `qwen3:32b` | Narrative synthesis |

Check which Ollama backend is active: `GET http://localhost:8002/health` returns `"ollama_url"` with the resolved endpoint.

### Service ports

| Service | Port |
|---|---|
| `db` | 8001 |
| `nlp` | 8002 |
| `ui` | 3001 (maps to container :3000) |
| `ollama` | 11434 (internal) |

---

## CPU-Only Fallback

On machines without a GPU, override the model environment variables before starting:

```bash
SQL_MODEL=qwen2.5-coder:7b SYNTHESIS_MODEL=qwen3:8b docker compose up
```

**Warning:** CPU-only generation runs at 2–4 tok/s. SQL generation: 8–15 min/step. Full pipeline: 45–90 min per query. GPU is strongly recommended for evaluation.

---

## Architecture Overview

Four-container Docker Compose layout on bridge network `nivii-net`:

```
┌──────────────────────────────────────────────────────────┐
│  docker-compose.yml                                      │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │  db      │    │  nlp         │    │  ui            │  │
│  │  FastAPI │◄───│  FastAPI     │◄───│  FastAPI +     │  │
│  │  SQLite  │    │  Pipeline    │    │  Jinja2 HTML   │  │
│  │  :8001   │    │  :8002       │    │  :3000         │  │
│  └──────────┘    └──────┬───────┘    └────────────────┘  │
│                         │                                │
│                  ┌──────▼───────┐                        │
│                  │  ollama      │                        │
│                  │  :11434      │                        │
│                  └──────────────┘                        │
└──────────────────────────────────────────────────────────┘
```

- **`db`** — ingests `data.csv`, normalizes dates to ISO at load time, exposes `POST /execute`, `GET /schema`, `GET /health`.
- **`nlp`** — multi-stage NL-to-SQL pipeline; calls `db` and Ollama.
- **`ui`** — single-page interface; async POST to `nlp` with 600s timeout.
- **`ollama`** — pulls and serves `SQL_MODEL` and `SYNTHESIS_MODEL` on first run.

---

## Pipeline Stages

```
NL Question
    │
    ▼
AmbiguityDetector     Rule-based pre-generation; dataset-anchored date resolution (not wall clock)
    │
    ▼
QueryClassifier       Keyword heuristic (60–70% coverage) + LLM fallback; aggregation override when ranking + time keywords co-occur
    │
    ▼
SchemaLinker          Injects CREATE TABLE DDL from semantic layer (full schema, single table)
    │
    ▼
SQLGenerator          NL + linked schema → SQL; returns filter injection when trigger terms detected (qwen2.5-coder:14b)
    │
    ▼
SQLExecutor           ReAct loop: execute → observe → decide → refine (semantic failure detection)
    │
    ▼
ResultSynthesizer     Result set → narrative (qwen3:32b; guarded on execution success)
    │
    ▼
Structured answer (SQL + table + narrative)
```

Each stage writes structured JSONL logs under `logs/runs/` for auditability.

---

## Architecture Decision Table

| Decision | Why | Tradeoff |
|---|---|---|
| DIN-SQL stage decomposition | Token budget management per stage; enables two-model strategy on local hardware | More code; each stage is a failure point |
| CREATE TABLE over natural language schema | Forces correct column reference and type awareness | Slightly more verbose in prompt |
| Date normalization at ingestion (not in SQL) | Source M/D/YYYY; fixed-position `substr()` fails for 48% of rows | Requires Python preprocessing step in `db` service |
| ReAct over fixed retry | Detects semantic failures (0 rows, wrong cardinality) that syntax retry misses | More complex; 2× latency per correction step |
| Rule-based AmbiguityDetector | Zero latency; LLM call adds 20–30s before SQL generation | Coverage is finite; open-domain queries may not resolve |
| Keyword heuristic QueryClassifier | Fires for 60–70% of questions at near-zero cost | May misclassify edge cases |
| SQLite over Postgres | Simplest possible db for demo scope; no infrastructure overhead | Not production-grade for concurrency |
| Four containers over monolith | Each service independently scalable; clear separation of concerns | More orchestration complexity |
| Two-model strategy (14B SQL + 32B synthesis) | Task-matched: SQL needs code precision, synthesis needs narrative reasoning | ~29 GB download; synthesis 2–5 min |
| Structural few-shot examples | Demonstrates expected SQL shape per class without overfitting to specific values | One example per class may not cover all variations |
| Dataset-anchored temporal disambiguation | Static 2024 CSV; wall-clock "recent" returns 0 rows | Requires semantic layer date bounds |
| Returns trigger injection in SQL prompt | Local SQL model ignores domain semantics for negative totals | False positives possible (e.g. "return customers") |
| Aggregation keyword override in classifier | Day-of-week keywords won map iteration over ranking terms | Finite override list |

---

## Engineering approach

Built with contract-first, staged execution rather than single-shot codegen:

- Spec-bound Docker scaffold, then service-by-service implementation with explicit kill criteria
- Tiered evaluation (structural → execution → composite), not a single pass-rate headline
- Failure-driven remediation (v1 → v1.1) traced to golden-set cases, not prompt thrashing
- Rule-based disambiguation and ReAct observation to limit LLM calls on the hot path
- Standing open-question backlog — see [open-questions.md](open-questions.md)

Process artifacts (plans, audits, full architecture index) are maintained privately; happy to walk through the workflow in a technical interview.

---

## Reviewer notes

- **First boot:** `docker compose up` pulls ~29 GB of models. `nlp` and `ui` may not start until Ollama is healthy — after models are cached, run `docker compose down && docker compose up` (or start `nlp`/`ui` manually).
- **Ollama routing:** The stack prefers **host Ollama** (GPU/Metal on Windows/Mac) when the API is reachable — **not** when models are present. Host and container have **separate model libraries**; `docker compose` pulls only into the container. If host Ollama is running without `qwen3:32b`, expect a late UI failure at synthesis (404). Pull both default models on the host or set `OLLAMA_URL=http://ollama:11434` on `nlp` to force the container — see [runtime_performance.md](runtime_performance.md).
- **Latency (GPU, default models):** UI queries ~3–7 min; full 12-case eval with judge ~90–120 min.
- **Eval outcome:** v1.1 composite **11/12** on the golden set; Case 11 (open-ended “recent sales”) remains the known residual — details in [Evaluation (v1 → v1.1)](#evaluation-v1--v11).
- **Fully local:** All inference via Ollama; no external API calls in the submitted system.
- **Informal handoff (EN/ES):** [handoff_notes_in_raw_criollo.md](handoff_notes_in_raw_criollo.md)
- **Portability (2nd machine):** [portability_check_on_my_laptop.md](portability_check_on_my_laptop.md) — clean clone on ~14 GB RAM Windows; `compose run -e` for CPU fallback when default models OOM
- **Stress / breaking points:** [documented_breaking_points.md](documented_breaking_points.md) — curated UI failures (trust, ops, eval-adjacent)

---

## Evaluation Harness

The evaluation harness is a **final-pass gate, not a CI regression suite**. A full run (12 cases, with judge) takes **90–120 minutes on GPU**.

- **12 POS-domain test cases** across 4 query classes (aggregation, filter, window, comparison)
- **Multi-tier validation:** structural SQL/class/ambiguity gates, execution success gate (`execution_pass`), and optional LLM-as-judge on narrative quality
- **`case_pass` (composite):** `sql_pass ∧ class_pass ∧ ambiguity_pass ∧ execution_pass`
- Per-case failure isolation; `--skip-judge` available for faster structural-only runs

From the repo root on the host (with `nlp/` on `PYTHONPATH`):

```bash
python -m nlp.eval.harness --skip-judge
```

Inside the `nlp` container (`WORKDIR /app`; top-level package is `eval`, not `nlp.eval`):

```bash
docker compose exec nlp python -m eval.harness
# or structural-only (Phase 2):
docker compose exec nlp python -m eval.harness --skip-judge
```

Results are written to `logs/eval_{timestamp}.json`.

### Evaluation (v1 → v1.1)

The golden set is 12 POS-domain cases across four query classes. v1 established the harness and a structural baseline; v1.1 added explicit execution gating, dataset-anchored temporal disambiguation, returns SQL constraints, classifier overrides, and synthesis/judge hardening. Composite pass rate moved **9/12 → 11/12**; structural gates **10/12 → 12/12**; execution stayed **11/12**. The remaining gap is Case 11 (open-ended "recent sales") — ReAct still exhausts max steps despite dataset date anchoring.

#### v1 baseline (2026-05-26, `--skip-judge`)

Run date: 2026-05-26  
Environment: Docker `nlp` container (Linux), host GPU Ollama via `host.docker.internal:11434`; models `qwen2.5-coder:14b` / `qwen3:32b`  
Command: `docker compose run --no-deps nlp python -m eval.harness --skip-judge`

#### v1.1 current (2026-05-27, with judge)

Run date: 2026-05-27  
Environment: host GPU Ollama via auto-routing; models `qwen2.5-coder:14b` / `qwen3:32b`  
Command: `docker compose exec nlp python -m eval.harness`  
Log: `nlp/logs/eval_20260527T211111Z.json`  
Wall clock: ~127 min logged pipeline latency (~90–120 min typical on GPU; judge calls add overhead beyond `latency_ms`)

Judge ran on 11/12 cases (skipped when execution failed). Cases 4, 7, and 8 received minor fidelity nitpicks (USD vs ARS symbol, unsupported inference); all still pass composite gates. Judge scores are informational — not part of `case_pass`.

#### Per-case comparison (v1 vs v1.1)

| Case | Question summary | v1 SQL | v1 Class | v1 Exec | v1 pass | v1.1 SQL | v1.1 Class | v1.1 Exec | v1.1 pass | Notes |
|------|-----------------|:------:|:--------:|:-------:|:-------:|:--------:|:----------:|:---------:|:---------:|-------|
| 1 | Most bought product on Fridays | ✓ | ✗ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | v1: classifier returned `time_filter` (Friday) vs `aggregation`. v1.1: aggregation override (T4) |
| 2 | Transactions on Saturdays | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| 3 | Busiest hours on weekdays | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| 4 | Total revenue October 2024 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v1.1 judge: USD symbol vs ARS reference |
| 5 | Waiter most revenue | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| 6 | Week-over-week revenue trend | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| 7 | Top 5 products by revenue | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v1.1 judge: minor percentage inflation, unsupported product inference |
| 8 | Transactions in November | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | v1.1 judge: contextual interpretation beyond raw count |
| 9 | Average ticket value per waiter | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| 10 | Most popular product (ambiguity) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Ambiguity resolution applied |
| 11 | Recent sales (ambiguity) | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | Both runs: ReAct max steps. v1.1: dataset date anchor (T2) fixes ambiguity text but execution still fails |
| 12 | Products with most returns | ✗ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | v1: omitted `total < 0`. v1.1: returns trigger injection (T3) |

**Tier pass rates:**

| Tier | Formula | v1 (skip_judge) | v1.1 (with judge) |
|------|---------|-----------------|-------------------|
| Structural | `sql_pass ∧ class_pass ∧ ambiguity_pass` | 10/12 (83%) | 12/12 (100%) |
| Execution | `execution_pass` | 11/12 (92%) | 11/12 (92%) |
| Composite (`case_pass`) | structural ∧ execution | 9/12 (75%) | 11/12 (92%) |

v1 clause-level: 11/12 SQL, 11/12 class.

**Known failure (v1.1):** Case 11 — open-ended "recent sales" query; ReAct observer hits max steps without a successful result set. Potential follow-up: relax the 10k-row aggregation-miss heuristic for open-ended time-filter queries.

---

## Scale-Out

Three scenarios for growing beyond this demo scope:

1. **More tables / larger schema** — Replace full schema injection in `SchemaLinker` with retrieval-augmented linking (ChromaDB or pgvector). Store table embeddings; retrieve top-k tables by cosine similarity to the question. Pipeline orchestration code unchanged; only `SchemaLinker` implementation swaps from `render_ddl()` to `retrieve_and_render(question)`.

2. **More data** — SQLite → PostgreSQL with read replicas. The `db` service interface (`POST /execute`) stays unchanged. Swap the backend, add connection pooling, adjust Compose.

3. **High traffic** — The `nlp` service is the bottleneck (3–7 min inference per query on GPU). Scale horizontally with multiple `nlp` replicas behind a load balancer. Add a Redis job queue between `ui` and `nlp` for async processing — UI submits job, polls for result — so the frontend stays responsive under concurrent load.

---

## Production Delta

What would change for a real Nivii deployment beyond this demo:

- **Automated schema enrichment** — profile new tables, generate descriptions, detect date format patterns
- **LLM-path AmbiguityDetector** — handle open-domain queries beyond finite rule coverage
- **Kubernetes per-client deployment** — data never leaves client environment
- **Continuous evaluation pipeline** — every prompt change triggers an eval run
- **Synthesis plausibility filter** — sanity-check narrative numbers against result data before returning
- **CHASE-SQL candidate consistency** — generate N=3 SQL candidates, execute all, select by result majority vote for business-critical queries

---

## Limitations

- **Ad-hoc stress cases** — off-domain questions, adversarial logic, and ops edge cases from manual UI probing: [documented_breaking_points.md](documented_breaking_points.md) (not covered by the golden eval).
- **Local model SQL reliability** — small models can produce syntactically valid but semantically wrong SQL. The ReAct loop catches common semantic failures but not all.
- **Host vs container model caches** — probing host Ollama does not use models pulled by the Compose `ollama` service; both tags must exist on whichever backend `/health` reports.
- **Latency on CPU-only machines** — see [CPU-Only Fallback](#cpu-only-fallback); 45–90 min per query.
- **Dataset scope** — 60 days (Sep 21 – Nov 20, 2024); annual or year-over-year queries return partial results only.
- **AmbiguityDetector rule coverage** — finite rule set; novel phrasings may not trigger resolution.
- **Open-ended temporal queries** — dataset-anchored "recent" disambiguation helps, but Case 11 still fails execution (ReAct max steps).
- **Narrative overreach** — LLM judge can flag unsupported inference or currency symbols even when composite gates pass (Cases 4, 7, 8 in v1.1).
- **Eval harness scope** — final-pass gate, not continuous regression in CI.

---

## Dataset

| Property | Value |
|---|---|
| Rows | 24,212 |
| Columns | 10 (`date`, `week_day`, `hour`, `ticket_number`, `ticket_prefix`, `waiter`, `product_name`, `quantity`, `unitary_price`, `total`) |
| Unique products | 68 |
| Unique tickets | 11,771 |
| Unique waiters | 9 |
| Date range | **60 days: Sep 21 – Nov 20, 2024** |
| Revenue | Sep 34.3M ARS · Oct 110.6M ARS · Nov 70.3M ARS |

**Column note:** `ticket_prefix TEXT` is extracted from `ticket_number` at ingest (register/type code: FCA, FCB, NCA, NCB).

**Date handling:** source dates are `M/D/YYYY` (not zero-padded). Dates are normalized to ISO at ingestion — all SQL uses `strftime()` on the normalized column, never fixed-position `substr()` on raw strings.
