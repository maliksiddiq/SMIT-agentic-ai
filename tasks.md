# Tasks — Code Review Desk

This document is the **ordered implementation plan**. Every task below is independently verifiable, names the requirement(s) it serves, and is sequenced against the project's two-hour clock (Constitution/Spec — Phase 0 through Phase 3 + Demo). No task in Phase 1 onward may begin until every task in Phase 0 is committed (Constitution, Section 8).

This file is committed as part of Phase 0, alongside `constitution.md`, `spec.md`, and `plan.md` — before any implementation code exists.

---

## How to Read This Document

- Each task has an **ID** (`T0.1`, `T1.1`, …), a **requirement tag**, a **"done when"** check that can be verified without guessing, and its **plan.md file(s)**.
- Tasks are grouped by phase, matching the project clock exactly.
- **Dependencies** are listed only when a task cannot start before another finishes; otherwise tasks within a phase may be done in any order.
- The **cut list** (Section 8) tells you what to drop, and in what order, if a phase is running over time — never improvise a different cut.

---

## Phase 0 — Specify (0:00–0:35)

**Objective:** commit all four Phase 0 documents. No source code exists at the end of this phase.

| ID | Task | Requirement(s) | Done when | Depends on |
|---|---|---|---|---|
| T0.1 | Write `constitution.md` | Gate rule (Constitution) | File exists, covers model provider, secrets, tool behavior, reproducibility, output integrity, concurrency, observability, spec-before-code, environment/runtime, interface quality, project location, API-key build continuity | — |
| T0.2 | Write `spec.md` | Gate rule (Constitution) | File exists, restates every FR/NFR as behavior, states the 3 non-goals, includes user flows | T0.1 |
| T0.3 | Write `plan.md` | Gate rule (Constitution) | File exists, defines folder structure, data structures, agent inventory, tool inventory, turn ceiling + reasoning, hooks assignment + reasoning | T0.2 |
| T0.4 | Write `tasks.md` (this file) | Gate rule (Constitution) | File exists, every FR/NFR mapped to at least one task, cut list restated | T0.3 |
| T0.5 | Initialize git at project root (`05_Code_Review_Desk`), create `.gitignore` (`.env`, `.venv/`, `ledger.jsonl`, `__pycache__/`) | NFR-5 | `git status` is clean except the 4 docs + `.gitignore` | T0.1–T0.4 |
| T0.6 | Commit the four Phase 0 documents **and only these documents** in one commit (or a tight sequence of doc-only commits) | NFR-5, Constitution Section 8 | `git log` shows a commit containing only `constitution.md`, `spec.md`, `plan.md`, `tasks.md`, `.gitignore` — zero source files | T0.5 |
| T0.7 | Verify Phase 0 gate | NFR-5 | `git log --stat` on the first commit shows no `.py` file anywhere in it | T0.6 |

**Phase 0 exit check:** four documents committed, git history proves it, no code exists. Do not proceed to Phase 1 until T0.7 passes.

---

## Phase 1 — Intake and One Reviewer (0:35–1:05)

**Objective:** FR-1 through FR-4 working end-to-end for a single reviewer, provable without needing the other two reviewers to exist yet.

| ID | Task | Requirement(s) | Done when | Depends on |
|---|---|---|---|---|
| T1.1 | Set up `.venv` (per `plan.md` Section 1) if the system Python is incompatible with Chainlit; create `pyproject.toml`/`requirements.txt`; install Agents SDK, `pydantic`, `python-dotenv` | Constitution Section 9 | `.venv` activates; `python --version` matches the pinned version; imports succeed | T0.7 |
| T1.2 | Create `.env.example` and `src/config/settings.py` — load env vars, validate `GEMINI_API_KEY` at startup, fail with one clear sentence if missing | NFR-1, FR-1 | Removing `GEMINI_API_KEY` from `.env` produces one clear sentence, not a traceback | T1.1 |
| T1.3 | Implement `src/models/finding.py` — the `Finding` Pydantic model | FR-3 | `Finding(file=..., line=..., severity="critical", message=...)` constructs; an invalid `severity` value is rejected | T1.1 |
| T1.4 | Implement `src/context/review_context.py` — the `ReviewContext` dataclass, with `strictness` validated/defaulted | FR-2 | `ReviewContext(repo=..., language=..., ruleset_id=...)` defaults `strictness` to `"normal"`; an invalid strictness value is caught at construction | T1.1 |
| T1.5 | Implement `src/services/diff_splitter.py` — splits a unified diff into per-file chunks, before any model call | FR-1 | A 2-file diff produces exactly 2 chunks; an empty/malformed diff returns a clear message object, not an exception | T1.1 |
| T1.6 | Implement `src/cli.py` — async entry point reading a diff path from the command line, calling the splitter | FR-1 | Running the CLI against a malformed diff path prints one clear message and exits cleanly, no traceback | T1.5 |
| T1.7 | Implement `src/tools/diff_tools.py` (`read_diff_chunk`) and `src/tools/ruleset_tool.py` (`lookup_ruleset`), both with internal error handling that never raises | FR-2, FR-9 (partial: error-handling control) | Calling either tool with a bad/missing input returns a plain string, never an exception | T1.4, T1.5 |
| T1.8 | Write dynamic instruction builder — assembles a reviewer's system prompt per run from `ReviewContext` (ruleset + language + strictness) | FR-4 | Two different `ReviewContext` values produce two visibly different printed prompt strings, with no model call made | T1.4, T1.7 |
| T1.9 | Implement `src/agents_/base_reviewer.py` — the one base reviewer, model configured per `plan.md` Section 1 (`GEMINI_MODEL_PRIMARY`, default `gemini-3.5-flash`, fallback `gemini-2.5-flash`), `output_type = list[Finding]` | FR-1 (model config), FR-3 | Agent object constructs with no global/default client set anywhere in the codebase (grep check) | T1.3, T1.8 |
| T1.10 | Run the base reviewer once, end-to-end, against a real small diff; inspect the generated strict-output schema | FR-3 | `final_output` is a plain Python `list[Finding]`; the raw schema shows the single-key object wrapper around the list root, and this can be pointed at and explained | T1.9 |
| T1.11 | **Checkpoint commit:** Phase 1 code only, referencing FR-1…FR-4 in the commit message | NFR-5 | `git log` shows this commit strictly after the Phase 0 doc commit | T1.2–T1.10 |

**Phase 1 exit check:** a single reviewer can take a diff path, split it, build a per-run prompt from context, call its tools without ever raising, and return a validated `list[Finding]` with a demonstrably-wrapped schema.

---

## Phase 2 — Fan Out (1:05–1:40)

**Objective:** FR-5 through FR-9 — three concurrent reviewers, merge/handoff, run-level override, the output guardrail, and the three FR-9 controls.

| ID | Task | Requirement(s) | Done when | Depends on |
|---|---|---|---|---|
| T2.1 | Clone the base reviewer into `security_reviewer.py`, `tests_reviewer.py`, `style_reviewer.py` per `plan.md` Section 5.2–5.4 (distinct instructions/model settings each) | FR-5 | Three distinct agent objects exist, all sharing the base reviewer's core definition | T1.9 |
| T2.2 | Configure `lookup_ruleset` as a forced/required tool call specifically on the Security Reviewer | FR-9 (control #1) | Security Reviewer's run always includes a `lookup_ruleset` call; this is enforced by configuration, not instruction text alone | T2.1, T1.7 |
| T2.3 | Implement `src/services/concurrency.py` — launches all three reviewers together via a concurrent gather over the same diff, returns `list[ReviewerResult]` | FR-5 | The three reviewer calls are started together in code, not awaited one at a time | T2.1 |
| T2.4 | Set the turn ceiling (8 turns, per `plan.md` Section 6) on every reviewer run; catch the ceiling exception and mark `ReviewerResult.partial = True` | FR-9 (control #3) | Artificially lowering `TURN_CEILING` for a test forces a partial-review result that is caught, not a crash | T2.3 |
| T2.5 | Write `tests/test_concurrency_benchmark.py` — runs the same 3 reviewers both concurrently and sequentially against the same diff, records both wall-clock times | FR-5 | Both numbers print/assert; concurrent time is close to the slowest single reviewer, not the sum of all three | T2.3, T2.4 |
| T2.6 | Implement `src/agents_/merge_specialist.py`, exposed via `as_tool`, taking `list[ReviewerResult]` and returning `MergedReport` (deduped, severity-ordered) | FR-6 (merge half) | Calling Merge with overlapping findings from two reviewers returns one deduplicated, severity-ordered list | T2.3 |
| T2.7 | Implement `src/agents_/remediation_specialist.py` with `RemediationHandoffInput`, wired as a `handoff` target, triggered only when `MergedReport.findings` contains a `severity == "critical"` finding from Security | FR-6 (handoff half) | A diff with a planted critical security issue triggers the handoff and Remediation states which finding triggered it; a diff with only major/minor findings never triggers it | T2.6 |
| T2.8 | Write the two-sentence justification (tool vs. handoff) into `spec.md` Section 3.6 if not already present; verify it matches `plan.md` Section 5.5/5.6 | FR-6 | Justification text exists and is consistent across `spec.md` and `plan.md` | T2.7 |
| T2.9 | Implement the run-level model override path — same reviewer object, one call on its own model, one call overridden to `GEMINI_MODEL_FALLBACK` at the run boundary only | FR-7 | Diffing the reviewer object's `model=` attribute before/after the override call shows no change | T2.1 |
| T2.10 | Implement `src/guardrails/secret_guardrail.py` — output guardrail scanning the assembled report text for credential-shaped strings; wire it to fire just before final delivery | FR-8 | A diff with a planted fake API key produces a caught refusal; a clean diff passes through untouched | T2.6 |
| T2.11 | Write `tests/test_output_guardrail.py` covering both the refusal case and the clean-pass-through case, and pointing at the exact catch line | FR-8 | Both test cases pass; the catch-site line number/location is documented in the test or a comment | T2.10 |
| T2.12 | Wire `read_diff_chunk` and `lookup_ruleset` error handling into every reviewer clone (not just Security) so no tool failure ever raises into the Runner | FR-9 (control #2), NFR-4 | Deleting the ruleset file produces a review that still completes with a sensible message, for every reviewer, not just Security | T2.2, T1.7 |
| T2.13 | **Checkpoint commit:** Phase 2 code, referencing FR-5…FR-9 in the commit message | NFR-5 | `git log` shows this commit strictly after the Phase 1 checkpoint | T2.1–T2.12 |

**Phase 2 exit check:** three cloned reviewers run concurrently and provably faster than sequential; Merge (tool) and Remediation (handoff) both fire correctly and are individually justified; a cheaper run-level override works without mutating any agent; the output guardrail refuses leaked credentials; required tools, non-raising tool failures, and the turn ceiling are all demonstrated.

---

## Phase 3 — Observe and Ship (1:40–1:55)

**Objective:** FR-10 through FR-13 — hooks/footer, ledger, Chainlit streaming, tracing.

| ID | Task | Requirement(s) | Done when | Depends on |
|---|---|---|---|---|
| T3.1 | Implement `src/hooks/run_hooks.py` — attached to every reviewer run, records `HookMetrics` (duration, tokens) from real run-context data | FR-10 (run hooks) | Metrics for all three reviewers are non-estimated, pulled from the actual run result object | T2.3 |
| T3.2 | Implement `src/hooks/agent_hooks.py`, attached **only** to the Tests Reviewer per `plan.md` Section 7 | FR-10 (agent hooks) | Only the Tests Reviewer carries agent-level hooks; the other two do not | T3.1, T2.1 |
| T3.3 | Implement `src/services/report_builder.py` — assembles `FinalReport` with a 3-row footer sourced from `HookMetrics` | FR-10 | Footer shows 3 rows, numbers trace back to `HookMetrics`, none hardcoded/estimated | T3.1 |
| T3.4 | Implement `src/runners/ledger_runner.py` — custom runner appending one JSON line per run to `ledger.jsonl`, per the exact shape in `plan.md` Section 4.8 | FR-11 | Reviewing a 3-file diff produces the expected number of ledger lines (≥3, one per run that actually happened) | T2.3, T2.6 |
| T3.5 | Register the ledger runner **once**, in `src/config/settings.py` (or equivalent single bootstrap point); confirm no agent file references it | FR-11 | Grepping every file in `src/agents_/` finds zero references to `ledger_runner` or `ledger.jsonl` | T3.4 |
| T3.6 | Write `tests/test_ledger.py` — confirms line count and shape; confirms removing the one registration call is the only change needed to disable it | FR-11 | Test passes; commenting out the single registration line stops new ledger lines from appearing, with no other code change | T3.5 |
| T3.7 | Initialize tracing once at startup (shared by CLI and Chainlit), exported under `TRACING_API_KEY` | FR-13 | A live review produces exactly one trace containing all reviewer spans, the Merge call, and (when triggered) the Remediation handoff | T2.3, T2.6, T2.7 |
| T3.8 | Manually verify the trace: open it, confirm the three reviewer spans overlap in time, name the slowest reviewer; record this walkthrough in `tests/test_tracing_manual_checklist.md` | FR-13 | Checklist file completed once, with the slowest-reviewer name written down for that run | T3.7 |
| T3.9 | Build `chainlit_app/app.py` — paste-a-diff page, async handler (never the sync Runner variant), findings streamed progressively, session state holding `ReviewContext` and the last report | FR-12 | Findings visibly appear progressively during a live review, not all at once at the end | T3.3, T3.7 |
| T3.10 | Confirm session reuse: paste a second diff in the same Chainlit session and confirm the existing `ReviewContext` is reused, not re-requested | FR-12 | Second review in the same session skips re-asking for repo/language/ruleset/strictness | T3.9 |
| T3.11 | Add clear UI states in Chainlit for: guardrail refusal, partial review (turn ceiling), and missing/invalid API key (`"API key required"` message) | FR-12, Constitution Sections 10 & 12 | Triggering each of the three states shows a clear, legible message — never a blank screen or raw exception in the UI | T3.9, T2.10, T2.4, T1.2 |
| T3.12 | Style pass on the Chainlit UI — legible streamed findings, footer visually distinct from findings, consistent layout | Constitution Section 10 | A reviewer glancing at the UI can tell streamed findings, the final report, and the footer apart at a glance | T3.9–T3.11 |
| T3.13 | **Checkpoint commit:** Phase 3 code, referencing FR-10…FR-13 in the commit message | NFR-5 | `git log` shows this commit strictly after the Phase 2 checkpoint | T3.1–T3.12 |

**Phase 3 exit check:** footer shows real per-reviewer metrics; exactly one reviewer carries agent-level hooks and the difference from run-level hooks is demonstrable; every run lands in the ledger via one central registration; Chainlit streams findings live with session reuse and clear error/refusal/missing-key states; one trace covers a full review with visibly overlapping reviewer spans.

---

## Phase 4 — Demo (1:55–2:00)

**Objective:** one full, live, end-to-end review, streamed and traced, ready to defend.

| ID | Task | Requirement(s) | Done when | Depends on |
|---|---|---|---|---|
| T4.1 | Prepare one clean demo diff and one diff containing a critical security issue (for the handoff path) and one diff containing a planted fake credential (for the guardrail path) | FR-5, FR-6, FR-8 | All three sample diffs exist under a `demo/` or `tests/fixtures/` folder | T3.13 |
| T4.2 | Run the clean diff live through Chainlit; narrate concurrency, streaming, footer, ledger | FR-5, FR-10, FR-11, FR-12 | Live run completes and every element named above is visibly shown | T4.1 |
| T4.3 | Run the critical-security diff live; narrate the handoff and the typed `RemediationHandoffInput` | FR-6 | Remediation visibly takes over the conversation and names the triggering finding | T4.1 |
| T4.4 | Run the credential-leak diff live; narrate the guardrail refusal and the cost-already-incurred point | FR-8 | A clear refusal is shown instead of a report | T4.1 |
| T4.5 | Open the trace from T4.2's run live; name the slowest reviewer on the spot | FR-13 | Slowest reviewer is correctly identified from the trace, live, without pre-reading it | T4.2, T3.8 |
| T4.6 | Rehearse answers to all 8 defense questions (`spec.md` viva reference) against this specific implementation | All | Each of the 8 questions can be answered in under a minute, pointing at real code/output | T4.1–T4.5 |

---

## Phase 5 — Stretch Goals (Only If All Above Is Complete Early)

Per Constitution Section 6 / `spec.md` Section 5, these are explicitly out of core scope and are only attempted after every task above is done and verified.

| ID | Task | Notes |
|---|---|---|
| T5.1 | Confirm `RemediationHandoffInput` typing already satisfies "typed remediation input" (it does, per T2.7 — no extra work needed unless expanding it further) | Already covered as baseline, per `plan.md` Section 4.5 |
| T5.2 | Add a second output guardrail rejecting any finding whose line number isn't actually present in the diff | Separate guardrail function, chained after `secret_guardrail.py` |
| T5.3 | Persist reports (e.g., append to a local JSON/SQLite store) so the Desk can answer "what changed since the last review of this repo?" | Explicitly out of core scope (`spec.md` Section 5, non-goal #3) — only build if genuinely finished early |
| T5.4 | Point the Desk at a real pull request from an actual repository and observe which reviewer contributes the least value | Evaluation exercise, not a code deliverable |

---

## Requirement → Task Coverage Matrix

| Requirement | Tasks |
|---|---|
| FR-1 | T1.5, T1.6, T1.9 |
| FR-2 | T1.4, T1.7, T1.8 |
| FR-3 | T1.3, T1.9, T1.10 |
| FR-4 | T1.8 |
| FR-5 | T2.1, T2.3, T2.5 |
| FR-6 | T2.6, T2.7, T2.8 |
| FR-7 | T2.9 |
| FR-8 | T2.10, T2.11 |
| FR-9 | T2.2, T2.4, T2.12 |
| FR-10 | T3.1, T3.2, T3.3 |
| FR-11 | T3.4, T3.5, T3.6 |
| FR-12 | T3.9, T3.10, T3.11, T3.12 |
| FR-13 | T3.7, T3.8 |
| NFR-1 | T1.2 |
| NFR-2 | T2.4 (turn ceiling), T1.9/T2.1 (declared model settings) |
| NFR-3 | T3.6, T3.8 |
| NFR-4 | T1.7, T2.12 |
| NFR-5 | T0.5–T0.7, T1.11, T2.13, T3.13 |

Every FR and NFR has at least one task above. If any row were empty, this document would be incomplete — it is not.

---

## Cut List (Restated — Use Only in This Order)

If a phase is running over its allotted time, cut from the bottom of this list, never from whatever currently looks hardest:

1. **First cut:** T3.4–T3.6 (FR-11, the ledger). Remove the single registration call; T3.1–T3.3, T3.7–T3.12 are unaffected.
2. **Second cut:** T2.9 (FR-7, run-level override). Reviewers keep working on their primary model alone.
3. **Third cut:** T3.2 (agent-level hooks on the Tests Reviewer only). Leave T3.1/T3.3 (run-level hooks and the footer) fully intact.

**Never cut:** T2.1/T2.3/T2.5 (FR-5, concurrency) or T2.10/T2.11 (FR-8, the output guardrail) — per Constitution Section 6, these are what this project is for and what the viva focuses on.

---

## Definition of Done (Task-Level)

This `tasks.md` is complete when:
- Every task has a concrete, checkable "done when" condition — nothing reads "make it work."
- Every FR and NFR appears in the coverage matrix above with at least one task.
- The phase boundaries match the project clock in `constitution.md`/`spec.md` exactly (0:35, 1:05, 1:40, 1:55, 2:00).
- The cut list here matches the cut list in `constitution.md` and `plan.md` exactly, in the same order.