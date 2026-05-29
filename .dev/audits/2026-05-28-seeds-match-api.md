# Audit Report — seeds-match-api

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-28  
**Auditor focus areas:** Integration seams (singleton init → `agent_loop` → routes; conftest mock boundary); Failure paths (startup key validation, agent 500 envelope); Regression surface (plan §2 vs shipped envelopes, closure artifact chain)  
**Plan version:** 1.1 (`seeds-match-api`, status Complete)  
**Context map:** Absent (documented greenfield deferral in plan §0 — not a `context-map-missing` violation)  
**Audit-time HEAD SHA:** `ada6731c3a56a159c5772d779c19174cb45bb32b` (matches plan §8.1 handoff SHA)

---

## 1. Audit metadata

| Field | Value |
|-------|-------|
| Task | Build FastAPI conversational ReAct agent with Yahoo Finance tool, in-process memory, `POST /chat` + `GET /chat/{conversation_id}`, Docker single-worker |
| Plan | `.dev/plans/seeds-match-api/plan.md` v1.1 |
| Closure SHA claimed | `ada6731` |
| pytest at audit | `59 passed, 2 warnings` in 0.77s (Python 3.14, pytest 9.0.2) |
| Phase 0 discipline | Completed before reading decision logs, changelog, or plan prose beyond §1 + §2 |

---

## 2. Provenance log

| Check | Result |
|-------|--------|
| Context map path | **Absent** — plan §0 documents greenfield; binding spec used instead of scout map |
| SHA comparison (context map) | N/A |
| Working tree at audit | **Dirty** — untracked: `.dev/plans/`, `seeds-match-challenge-spec.md`, `__pycache__/`, `.pytest_cache/` |
| Scout grep coverage | N/A (no context map) |
| Closure SHA vs HEAD | **Match** (`ada6731`) |

### Plan-artifact provenance (`git show ada6731:<path>`)

| Artifact | On disk | In `ada6731` | Status |
|----------|---------|--------------|--------|
| `seeds-match-challenge-spec.md` | Yes | **No** | `artifact-not-in-HEAD` |
| `.dev/plans/seeds-match-api/plan.md` | Yes | **No** | `artifact-not-in-HEAD` |
| `.dev/plans/seeds-match-api/packets/T1.md` … `T8.md` | Yes | **No** | `artifact-not-in-HEAD` (×8) |
| `.dev/decision-logs/T5-agent-loop.md` | Yes | **Yes** | present-in-HEAD |
| `.dev/decision-logs/T6-main.md` | Yes | **Yes** | present-in-HEAD |
| `CHANGELOG.MD` | Yes | **Yes** | present-in-HEAD |
| Application + tests | Yes | **Yes** | present-in-HEAD |

**Closure SHA verification (§8.2):** Plan §8.2 states *"All paths resolve at `git show HEAD:<path>` at the handoff SHA."* That statement is **false** for the binding spec, orchestrator plan, and all eight executor packets at `ada6731`. Only decision logs, changelog, and implementation are in the tree.

---

## 3. Context chain completeness

| Artifact | Provided | Notes |
|----------|----------|-------|
| Context map | No | Acceptable per plan §0 (greenfield) |
| Binding spec | Yes (untracked on disk) | Not in git — limits merge archaeology |
| Orchestrator plan | Yes (untracked) | §1–§8 read after Phase 0 |
| Packets T1–T8 | Yes (untracked) | |
| Decision logs T5, T6 | Yes (in HEAD) | |
| Changelog | Yes (in HEAD) | |
| Codebase | Yes | 8 commits T1→T8 |
| Tests | Yes | 59 tests, 9 files |

**Limitation:** Post-merge auditors cannot reconstruct intent from `git show` alone without committing the binding spec and plan artifacts.

---

## 4. Cold-read log (Phase 0 — pinned)

| ID | Severity (guess) | File / surface | Finding |
|----|------------------|----------------|---------|
| CR-01 | major | Plan §8.2 vs git | Declared artifacts (spec, plan, packets) not retrievable from handoff SHA |
| CR-02 | minor | `plan.md` §2 vs `app/main.py:94` | §2 says "FastAPI default 404 detail"; code uses custom `Conversation '…' not found` string |
| CR-03 | observation | `app/agent/loop.py:37` | Sync `invoke()` inside `async def agent_loop` — event-loop blocking under concurrent load |
| CR-04 | observation | `tests/` layout | Nine test modules vs plan §2 "single file `tests/test_app.py`" |
| CR-05 | minor | `tests/test_app.py:220-229` | Store-isolation tests depend on collection order (`seed` before `verify`) |
| CR-06 | observation | `requirements.txt` | No `pytest` / dev deps; T8 packet requested `requirements-dev.txt` |
| CR-07 | unknown | `loop.py:41` | `if not response.tool_calls` — behavior if `tool_calls` is `None` vs `[]` unverified |

---

## 5. Findings table

| ID | Severity | Type | Phase | Subtask | Description |
|----|----------|------|-------|---------|-------------|
| F-01 | **major** | `artifact-not-in-HEAD` | 0.5 | closure | Binding spec not in `ada6731` |
| F-02 | **major** | `artifact-not-in-HEAD` | 0.5 | closure | Plan + 8 packets not in `ada6731` |
| F-03 | **major** | `process-violation` | 0.5 / 1 | §8.2 | §8.2 falsely claims all artifacts resolve via `git show HEAD` |
| F-04 | minor | `contract-violation` | 2 | T6 | Plan §2 Error Envelope row for GET 404 contradicts T6 packet, binding spec, and code |
| F-05 | minor | `coverage-gap` | 5 | T6/T8 | No test for `ROLE_MAP.get(..., "unknown")` fallback (promised in T6 decision log) |
| F-06 | minor | `coverage-gap` | 5 | T6/T8 | Lifespan `RuntimeError` on empty-string `OPENAI_API_KEY` not falsified (CHANGELOG deferred) |
| F-07 | minor | `intent-drift` | 1 | T8 | T8 packet files-to-touch `{test_app.py, conftest.py}`; delivery spread tests across T2–T7 modules (benign widening) |
| F-08 | observation | `intent-drift` | 1 | §2 vs §8 | §2 Tests says single `test_app.py`; §8 closure documents 9 files — §2 stale |
| F-09 | observation | — | 4 | T5 | Sync `invoke` in async loop — documented in T5 decision log; demo-acceptable |
| F-10 | observation | — | 4 | T8 | `test_client_store_isolation_*` order-dependent; passes under default collection order |

---

## 6. Detailed findings (above minor)

### F-01 — Binding spec not in HEAD (`artifact-not-in-HEAD`)

**Expected:** Plan §0 and §8.2 cite `seeds-match-challenge-spec.md` as the binding artifact committed at repo root, resolvable at handoff SHA.

**Found:** File exists on disk but `git show ada6731:seeds-match-challenge-spec.md` fails. `git status` shows `?? seeds-match-challenge-spec.md`.

**Evidence:** Shell verification at audit time; plan §8.2 row 406.

**Impact:** Merge archaeology and auditor replay cannot anchor implementation to the binding spec from git alone.

---

### F-02 — Plan and packets not in HEAD (`artifact-not-in-HEAD`)

**Expected:** §8.2 artifact chain includes plan and T1–T8 packets in the closure commit.

**Found:** All nine paths exist on disk under `.dev/plans/seeds-match-api/` but none are in `ada6731`. Working tree shows `?? .dev/plans/`.

**Evidence:** `git ls-files` lists no plan/packet paths; `git show ada6731:.dev/plans/seeds-match-api/plan.md` → fatal.

---

### F-03 — False closure provenance claim (`process-violation`)

**Expected:** Orchestrator §8.2 written only after verifying `git show HEAD:<path>` for every listed artifact.

**Found:** §8.2 prose *"All paths resolve at git show HEAD:<path> at the handoff SHA"* is incorrect for 10 of 13 listed artifacts (spec + plan + 8 packets). Decision logs and changelog do resolve.

**Evidence:** Plan lines 400–418 vs git verification table in §2 above.

**Impact:** Downstream auditor or reviewer trusting §8.2 would falsely believe the context chain is git-pinned.

---

## 7. Adversarial test log (Phase 4)

### Focus A — Integration seams (required)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Lifespan calls `init_singletons` before first `/chat` | `get_llm_with_tools()` non-None after startup | `conftest.py` patches `ChatOpenAI`; `test_chat_generates_conversation_id` passes | **passes** |
| `agent_loop` reads same module singletons as lifespan | `from app.agent.tools import get_*` same object as `app.agent import tools` | Import paths match; `test_agent_loop_tool_call_then_final_answer` exercises tool_map | **passes** |
| `SYSTEM_PROMPT` injected at invoke, not stored | GET history has no `system` role from prompt | `test_agent_loop_smoke_no_tool_calls` asserts no `SystemMessage` in store | **passes** |
| Mock boundary prevents live OpenAI | No network in tests | All 59 tests pass with mocks only | **passes** |
| Fresh store per TestClient test | Prior conversation IDs 404 | `test_client_store_isolation_*` passes in default order | **passes** (order-sensitive) |

### Focus B — Failure paths

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| Agent exception → structured 500 | `detail.error == "Agent execution failed"` | `app/main.py:84-87`; `test_chat_500_on_agent_exception` | **passes** |
| Missing `OPENAI_API_KEY` at import | `ValidationError`, app won't import | `test_config_module_import_fails_without_openai_api_key` (subprocess) | **passes** |
| Empty string `OPENAI_API_KEY` at lifespan | `RuntimeError` in lifespan | No dedicated test; `if not settings.openai_api_key` would fire | **unknown** (deferred in CHANGELOG) |
| `tool_calls is None` on AIMessage | Should not terminate early with pending tools | `not None` is True → treats as final answer | **unknown** |

### Focus C — Regression / contract literals

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| 500 error string exact | `"Agent execution failed"` | Byte-equal in `main.py` and tests | **passes** |
| GET 404 for unknown ID | 404, not empty list | `store.exists` guard; tests assert 404 | **passes** |
| No `AgentExecutor` | Non-goal | Grep: no matches in `app/` | **passes** |
| `MAX_ITERATIONS` fallback | Fallback string, 10 invokes | `test_loop.py` + `test_app.py` | **passes** |
| Docker CMD frozen string | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | `Dockerfile` CMD JSON array | **passes** |

---

## 8. Coverage gap list (prioritized)

| Priority | Gap | Kill criterion / source | Mitigation noted |
|----------|-----|-------------------------|------------------|
| P1 | Binding spec + plan not in git | §8.2 artifact chain | Commit artifacts before merge |
| P2 | Empty-string API key lifespan | T6/T8 CHANGELOG deferred | pydantic may accept `""`; lifespan check exists but untested |
| P3 | `ROLE_MAP` `"unknown"` fallback | T6 decision log | No falsifier test |
| P4 | `tool_calls is None` termination | ReAct correctness | LangChain typically uses `[]`; no test |
| P5 | Docker compose smoke | T7 — manual Phase 3 | Acceptable per plan; no automated test |
| P6 | `requirements-dev.txt` | T8 packet | pytest assumed from environment |

---

## 9. Phase 1 — Intent traceability (summary)

- **Task statement → code:** Delivers explicit `agent_loop` with `not response.tool_calls` termination, Yahoo tool, in-process `ConversationStore`, both HTTP routes, single-worker Docker — **aligned**.
- **Non-goals:** No `AgentExecutor`, auth, streaming, or multi-worker — **respected**.
- **Plan §2 vs binding spec vs code (GET 404):** Binding spec (`seeds-match-challenge-spec.md` §4) and T6 packet specify the custom `Conversation '…' not found` detail; implementation matches. Plan §2 table row *"FastAPI default 404 detail string"* is **stale** (F-04) — orchestrator inconsistency, not implementation drift from the binding spec.
- **Packet files-to-touch vs diff:** T8 delivered extra per-subtask test modules beyond packet list (F-07) — improves coverage; should update §2 or record amendment.
- **§8 closure vs reality:** Implementation evidence table (§8.3) is largely accurate for code/tests in HEAD; §8.2 provenance claim is not (F-03).

**Narrative-concealment:** None. Cold-read CR-01 (missing artifacts) is not acknowledged in §8 prose — qualifies as omission in closure narrative (folded into F-03).

---

## 10. Phase 2 — Contract compliance (summary)

| Contract area | Status |
|---------------|--------|
| Types / interfaces (§2 table) | **Pass** — spot-checked `Settings`, schemas, store async API, `agent_loop`, tools, `ROLE_MAP`, `MAX_ITERATIONS` |
| Error envelope POST 500 | **Pass** — literal `"Agent execution failed"` exact |
| Error envelope GET 404 | **Pass** vs binding spec; **plan §2 row wrong** (F-04) |
| Naming / module paths | **Pass** |
| Logging / no `print()` | **Pass** in `app/` |
| Tests framework / mocking | **Pass** — no live API in suite |
| CLI surface (Docker CMD, paths) | **Pass** |

---

## 11. Phase 3 — Decision log audit

### T5 (`T5-agent-loop.md`)

| Check | Result |
|-------|--------|
| Explicit loop vs AgentExecutor | **Implemented** — `for iteration in range(MAX_ITERATIONS)`, `not response.tool_calls` |
| System prompt not stored | **Implemented** — prepend only in `loop.py:35` |
| MAX_ITERATIONS = 10, fallback not raised | **Implemented** — line 65 |
| Sync invoke gap acknowledged | **Accurate** — still present at `loop.py:37`; not contradicted by log |

No `decision-log-stale` for T5.

### T6 (`T6-main.md`)

| Check | Result |
|-------|--------|
| Explicit `ROLE_MAP` | **Implemented** |
| `serialize_content` list handling | **Implemented** |
| Module-level store singleton | **Implemented** |
| Lifespan init | **Implemented** |
| "Test for unknown role in T8" | **Not implemented** — F-05 |

Minor stale promise in T6 log body; no banner supersession.

---

## 12. Scout-prediction reconciliation

No context map — table empty per skill. Greenfield intake recorded in plan §0.

---

## 13. Verdict

### **`fail`**

**Must resolve before merge (major):**

1. **F-01 / F-02:** Commit `seeds-match-challenge-spec.md`, `.dev/plans/seeds-match-api/plan.md`, and all packets (or amend §8.2 to reflect intentional out-of-tree storage — not recommended for this challenge).
2. **F-03:** Correct plan §8.2 provenance language after artifacts are committed; re-verify `git show HEAD:<path>` for each row.

**Runtime quality note:** Application code, architectural decision logs in git, and the test suite (59/59) demonstrate strong alignment with the binding spec's behavioral intent — explicit ReAct loop, async store, structured 500, tool error-as-string, and mocked integration tests. The failure is primarily **process / audit-archive integrity**, not core feature correctness.

**If artifacts are committed and §8.2 corrected:** Re-audit would likely yield `pass-with-conditions` on F-04–F-06 (documentation drift and minor coverage gaps).

---

## 14. Conditions for re-audit

- [ ] `git show HEAD:seeds-match-challenge-spec.md` succeeds
- [ ] `git show HEAD:.dev/plans/seeds-match-api/plan.md` and all packets succeed
- [ ] §8.2 prose matches verification outcome
- [ ] Optional: add `requirements-dev.txt`; falsify empty API key lifespan; add `unknown` role test
