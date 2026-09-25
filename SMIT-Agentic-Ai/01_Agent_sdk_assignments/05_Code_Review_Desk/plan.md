# Plan — Code Review Desk

This document is the **architecture** of the Code Review Desk: which agents exist, which run concurrently, what every tool takes and returns, and the exact shape of every structure that crosses a boundary. It builds directly on `constitution.md` (the rules) and `spec.md` (the behavior) — nothing here may contradict either. Together with `tasks.md`, these four files are the complete and only definition of this project (Constitution, Section 13).

This file is committed as part of Phase 0, before a single line of implementation code exists.

---

## 1. Project Root and Environment

- **Project root:** `05_Code_Review_Desk`, located at
  `D:\Agentic-Ai\SMIT-Agentic-Ai\01_Agent_sdk_assignments\05_Code_Review_Desk` (Constitution, Section 11).
- **Python version:** the project checks the active interpreter against Chainlit's supported range before any UI work begins. If the system default is incompatible, a dedicated virtual environment (`.venv`) is created inside the project root, pinned to a Python version confirmed to run Chainlit cleanly (Constitution, Section 9). The exact version selected, and the commands used to create/activate the venv, are recorded in the project `README.md` once chosen.
- **Package manager:** `pip`, with dependencies pinned in `pyproject.toml` (or `requirements.txt` if the coding agent prefers) — installed only inside `.venv`, never system-wide.
- **Model provider:** Google Gemini, accessed through whichever Gemini-compatible client the Agents SDK setup uses. Model strings are never hardcoded inline in multiple places — they are read from two environment variables (Section 3 below) so both the primary and fallback model are swappable without touching agent code.

---

## 2. Folder Structure

```
05_Code_Review_Desk/
│
├── constitution.md
├── spec.md
├── plan.md
├── tasks.md
├── README.md
├── .env.example
├── .env                      # gitignored, real secrets only
├── .gitignore
├── pyproject.toml            # or requirements.txt
├── ledger.jsonl              # created at runtime, gitignored
│
├── src/
│   ├── __init__.py
│   ├── cli.py                 # FR-1 async CLI entry point
│   │
│   ├── agents_/                # trailing underscore to avoid shadowing the SDK's own "agents" package
│   │   ├── __init__.py
│   │   ├── base_reviewer.py    # the one base reviewer definition (FR-5)
│   │   ├── security_reviewer.py
│   │   ├── tests_reviewer.py
│   │   ├── style_reviewer.py
│   │   ├── merge_specialist.py   # as_tool (FR-6)
│   │   └── remediation_specialist.py  # handoff target (FR-6)
│   │
│   ├── context/
│   │   ├── __init__.py
│   │   └── review_context.py   # ReviewContext dataclass (FR-2)
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── diff_tools.py       # diff-chunk-reading tools (FR-1, FR-9)
│   │   └── ruleset_tool.py     # required ruleset-lookup tool (FR-2, FR-9)
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── finding.py          # Finding pydantic model (FR-3)
│   │
│   ├── guardrails/
│   │   ├── __init__.py
│   │   └── secret_guardrail.py # output guardrail (FR-8)
│   │
│   ├── hooks/
│   │   ├── __init__.py
│   │   ├── run_hooks.py        # per-reviewer latency/token hooks (FR-10)
│   │   └── agent_hooks.py      # single-reviewer agent-level hooks (FR-10)
│   │
│   ├── runners/
│   │   ├── __init__.py
│   │   └── ledger_runner.py    # custom runner writing ledger.jsonl (FR-11)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── diff_splitter.py    # splits diff into per-file chunks (FR-1)
│   │   ├── concurrency.py      # launches the 3 reviewers together (FR-5)
│   │   └── report_builder.py   # assembles report + footer (FR-10)
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py         # env var loading, startup key validation (NFR-1)
│
├── chainlit_app/
│   ├── app.py                  # Chainlit page (FR-12)
│   └── chainlit.md             # Chainlit welcome/readme shown in the UI
│
├── rulesets/
│   └── <ruleset files by ruleset_id, e.g. python_default.md>
│
└── tests/
    ├── test_diff_splitting.py
    ├── test_context_isolation.py
    ├── test_structured_output.py
    ├── test_dynamic_instructions.py
    ├── test_concurrency_benchmark.py
    ├── test_merge_and_handoff.py
    ├── test_run_level_override.py
    ├── test_output_guardrail.py
    ├── test_required_tool_and_ceiling.py
    ├── test_hooks_and_footer.py
    ├── test_ledger.py
    └── test_tracing_manual_checklist.md   # manual trace-inspection steps, not automatable
```

**Why `agents_` and not `agents`:** the OpenAI Agents SDK itself is commonly imported as a package that may be named `agents` — naming our own package `agents_` avoids an import collision. This choice must be respected consistently across all implementation files.

---

## 3. Environment Variables (`.env` / `.env.example`)

| Variable | Purpose | Required? |
|---|---|---|
| `GEMINI_API_KEY` | Credential for the Gemini API. | Yes — startup fails with one clear sentence if missing (NFR-1). |
| `GEMINI_MODEL_PRIMARY` | Primary model string. Defaults to `gemini-3.5-flash` if unset. | No (has a default) |
| `GEMINI_MODEL_FALLBACK` | Fallback model string. Defaults to `gemini-2.5-flash` if unset. | No (has a default) |
| `TRACING_API_KEY` | Key used to export traces under the developer's own account (FR-13). | Yes for tracing to function — its absence must not crash the whole app, but tracing will not export without it; this must be surfaced clearly, not silently. |
| `TURN_CEILING` | Integer, overrides the default turn ceiling (Section 6 below) for local testing. | No (has a default of 8 — see Section 6) |
| `CHAINLIT_PORT` | Local port for the Chainlit dev server. | No (Chainlit's own default is acceptable) |

`.env.example` contains every one of these keys with placeholder values (e.g., `GEMINI_API_KEY=your-key-here`) and is committed. `.env` itself is never committed (Constitution, Section 2).

---

## 4. Data Structures (Every Boundary Crossing)

### 4.1 `ReviewContext` (local context — never in prompt text)
```python
@dataclass
class ReviewContext:
    repo: str
    language: str
    ruleset_id: str
    strictness: str = "normal"      # "normal" or "strict"
```
- **Producer:** CLI entry point / Chainlit session handler, at the start of a review.
- **Consumer:** passed into every `Runner.run(...)` call as the run's context object; read internally by tools (`ruleset_tool.py`) and by the dynamic-instruction builder.
- **Validation:** `strictness` is checked/normalized to `"normal"` or `"strict"` at construction; an unrecognized value does not silently pass through.
- **Never appears in:** any prompt string, any tool's model-visible input schema, any log line printed for the user.

### 4.2 `Finding` (structured reviewer output)
```python
class Finding(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "major", "minor"]
    message: str
```
- **Producer:** each reviewer agent (`output_type = list[Finding]`).
- **Consumer:** Merge specialist (input), report builder (input), output guardrail (inspects rendered text derived from these).
- **Validation:** enforced by Pydantic + the SDK's structured-output schema validation; a reviewer's run fails cleanly (not silently) if the model's output can't validate against this shape.

### 4.3 Reviewer Result (internal, post-run wrapper)
```python
@dataclass
class ReviewerResult:
    agent_name: str              # "SecurityReviewer" | "TestsReviewer" | "StyleReviewer"
    findings: list[Finding]
    duration_ms: int
    tokens_used: int
    partial: bool = False        # True if the turn ceiling was hit
```
- **Producer:** the concurrency service (`concurrency.py`), after awaiting each reviewer and combining its `final_output` with hook-derived timing/token data.
- **Consumer:** Merge specialist (as its raw input), report builder (footer data), ledger runner (per-run log line).

### 4.4 Merge Input / Output
- **Input:** `list[ReviewerResult]` (all three).
- **Output:**
```python
class MergedReport(BaseModel):
    findings: list[Finding]      # deduplicated, ordered by severity: critical > major > minor
```
- **Producer:** Merge specialist, called via `as_tool` by the Desk.
- **Consumer:** the Desk (to continue composing the report), the output guardrail (to inspect before delivery), and — if triggered — the Remediation handoff's incoming context.

### 4.5 Remediation Handoff Input
```python
class RemediationHandoffInput(BaseModel):
    triggering_finding: Finding   # the specific critical security finding that caused the handoff
    all_findings: list[Finding]   # full merged findings, for context
```
- **Producer:** the Desk, at the moment it decides to hand off (a critical security finding exists in `MergedReport.findings`).
- **Consumer:** Remediation specialist — this typed input is what lets Remediation state clearly, in its response, which finding triggered it (spec.md, Section 3.6 edge cases; also listed as a "finish early" stretch enhancement in the original brief, but implemented here as the baseline behavior since it costs little and directly satisfies FR-6's spirit).

### 4.6 Guardrail Result
```python
class GuardrailResult:
    tripwire_triggered: bool
    reason: str | None = None     # human-readable reason if triggered, never the secret itself
```
- **Producer:** the output guardrail function, run against the fully rendered report text.
- **Consumer:** the Runner (catches `tripwire_triggered=True` as an exception per the SDK's guardrail mechanism), which the application layer catches and turns into a user-facing refusal message.

### 4.7 Hook Metrics (per reviewer)
```python
@dataclass
class HookMetrics:
    agent_name: str
    started_at: float
    ended_at: float
    duration_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
```
- **Producer:** `run_hooks.py` (all three reviewers) and `agent_hooks.py` (the one designated reviewer only — see Section 7).
- **Consumer:** `report_builder.py` (footer), `ledger_runner.py` (the `ms` and `findings` fields of each ledger line).

### 4.8 Ledger Entry
```json
{"ts": "2026-09-23T19:04:11Z", "request_id": "rev_8f21", "agent": "SecurityReviewer", "ms": 2140, "findings": 3}
```
- **Producer:** `ledger_runner.py`, once per run, appended to `ledger.jsonl`.
- **Consumer:** none at runtime (write-only from the app's perspective) — read only by a developer inspecting the file directly, or by tests.
- **Fields:** `ts` (ISO 8601 UTC), `request_id` (generated once per top-level review, shared across that review's ledger lines, with a short random suffix, e.g. `rev_` + 4 hex chars), `agent` (the exact agent class/name that ran), `ms` (integer milliseconds), `findings` (integer count of findings that specific run produced; `0` for Merge/Remediation if not applicable, defined per-agent in `ledger_runner.py`).

### 4.9 Final Report (user-facing)
```python
class FinalReport(BaseModel):
    findings: list[Finding]
    footer: list[HookMetrics]           # one entry per reviewer
    partial: bool = False               # True if any reviewer hit the turn ceiling
    remediation_triggered: bool = False
```
- **Producer:** `report_builder.py`, the last assembly step before the output guardrail runs.
- **Consumer:** CLI stdout renderer, Chainlit streaming renderer.

### 4.10 Footer Metrics (rendering shape, derived from 4.7/4.9)
Rendered as three rows, one per reviewer:
```
SecurityReviewer   | 2140ms | 512 tokens
TestsReviewer      | 1875ms | 430 tokens
StyleReviewer      | 1990ms | 401 tokens
```
Sourced strictly from `HookMetrics`, never estimated (Constitution, Section 7; spec.md, Section 3.10).

---

## 5. Agent Inventory

### 5.1 Base Reviewer
- **Responsibility:** shared scaffolding for all three specialist reviewers — how a reviewer reads a diff chunk, how it's expected to format findings, how it consults the ruleset.
- **Model:** `GEMINI_MODEL_PRIMARY` (default `gemini-3.5-flash`), agent-level configuration.
- **Model settings:** conservative temperature (e.g., `0.2`) — reviewers should be consistent, not creative.
- **Instructions:** a shared skeleton, filled in dynamically per run (FR-4) with ruleset + language + strictness.
- **Tools:** diff-chunk access tool, ruleset-lookup tool.
- **Required tools:** none at the base level — "required" status is applied at the clone level (see 5.2–5.4).
- **Output type:** `list[Finding]`.
- **Context:** `ReviewContext`.
- **Guardrails:** none directly (guardrail applies at the report level, post-merge — see Section 8).
- **Hooks:** run-level hooks apply to every clone by default (Section 7).
- **Handoffs:** none.
- **Tracing:** included automatically as part of the single review trace (FR-13).

### 5.2 Security Reviewer *(clone of Base)*
- **Overrides:** instructions tuned toward security concerns (injection, secrets, unsafe deserialization, auth flaws, dependency risk). This is the **required-ruleset-tool** clone (FR-9, control #1) — it cannot skip the ruleset lookup.
- **Model settings:** same base temperature; may use a lower temperature if security findings should be more conservative/deterministic — documented at implementation time in this same section if changed from the base default.
- **Special role:** the only reviewer whose `severity == "critical"` findings can trigger the Remediation handoff (FR-6).

### 5.3 Tests Reviewer *(clone of Base)*
- **Overrides:** instructions tuned toward test coverage, missing edge-case tests, broken/skipped tests introduced by the diff.
- **Special role:** this is the reviewer designated to carry **agent-level hooks** in addition to the shared run-level hooks (FR-10) — see Section 7 for the reasoning.

### 5.4 Style Reviewer *(clone of Base)*
- **Overrides:** instructions tuned toward readability, naming, formatting, and ruleset-defined style conventions.
- **Special role:** none beyond the shared base behavior — deliberately the "plainest" of the three clones, to keep a clear contrast against Security (required tool) and Tests (agent-level hooks) for demonstration purposes.

### 5.5 Merge Specialist
- **Responsibility:** deduplicate overlapping findings across the three reviewers' outputs, then order the result by severity (`critical` → `major` → `minor`).
- **Model:** `GEMINI_MODEL_PRIMARY` (or a smaller/cheaper model if deduplication proves reliable at lower cost — decided at implementation time, documented here once fixed).
- **Exposure:** `as_tool` — called by the Desk, returns `MergedReport`, does not take over the conversation.
- **Output type:** `MergedReport`.
- **Context:** does not need `ReviewContext` directly; operates purely on the `list[ReviewerResult]` passed to it.
- **Guardrails:** none directly — the guardrail (Section 8) runs on the report as a whole, after this step.

### 5.6 Remediation Specialist
- **Responsibility:** propose a concrete patch/fix for the triggering critical security finding, in conversation with the user.
- **Model:** `GEMINI_MODEL_PRIMARY`.
- **Exposure:** `handoff` — reached only when the Desk detects a critical security finding in `MergedReport.findings`; takes over the conversation from that point on.
- **Input:** `RemediationHandoffInput` (Section 4.5).
- **Output type:** conversational (no strict `output_type` — Remediation's job is to converse, not return a single structured object), though anything it says is still subject to the output guardrail before reaching the user.
- **Guardrails:** output guardrail applies to Remediation's responses exactly as it applies to the Desk's own report (Constitution, Section 5; spec.md, Section 3.8).

### 5.7 Desk (Orchestrator)
- **Responsibility:** the top-level agent/coordinator the user is "talking to" by default. It performs diff intake, launches the three reviewers concurrently, calls Merge as a tool, runs the output guardrail, and either returns the final report itself or — on a critical security finding — hands off to Remediation.
- **Model:** `GEMINI_MODEL_PRIMARY` (the Desk itself may need to reason lightly about orchestration, even though most of its work is deterministic Python code calling the SDK, not model calls).
- **Tools:** Merge specialist (`as_tool`).
- **Handoffs:** Remediation specialist.
- **Guardrails:** output guardrail attached at the point the Desk is about to deliver its final report.
- **Tracing:** the Desk's run is the root of the single trace that contains everything else (FR-13).

---

## 6. Concurrency Architecture (FR-5)

- The three reviewer clones (Security, Tests, Style) are each called via `Runner.run(...)`, and all three calls are gathered together (e.g., `asyncio.gather(...)`) rather than awaited one at a time.
- **Turn ceiling: 8 turns per reviewer**, applied uniformly via each run's `max_turns` (or the SDK's equivalent run-configuration setting).
  **Reasoning:** a reviewer's expected flow is: (1) read its diff chunk, (2) consult the ruleset tool (required for Security; optional-but-typical for the others), (3) reason about the code, (4) produce structured findings. That's realistically 2–4 tool-involving turns plus a small buffer for the model correcting a malformed structured-output attempt. 8 gives comfortable headroom above the expected 2–4 without allowing a runaway tool-calling loop to run indefinitely — which is exactly the failure mode this ceiling exists to stop (see spec.md, viva question 8).
- **Benchmark requirement:** `tests/test_concurrency_benchmark.py` runs the same three reviewers both concurrently and sequentially against the same diff and asserts/reports both wall-clock numbers, so the FR-5 "show both numbers" requirement is always demonstrable, not just claimed.

---

## 7. Hooks Architecture (FR-10)

- **Run-level hooks** (`run_hooks.py`) are attached to every run of every reviewer, uniformly, via the run configuration — not per-agent. They observe start/end timing and pull token usage from the run's own result object. This is what populates the three-row report footer.
- **Agent-level hooks** are attached to exactly **one** reviewer: the **Tests Reviewer** (Section 5.3).
  **Reasoning for choosing Tests:** Security is already special-cased as the required-tool reviewer and the handoff trigger; keeping Style as the "plain" baseline clone makes the three reviewers' differences easy to explain individually in the viva (Security = required tool + handoff trigger, Tests = agent-level hooks, Style = baseline). Tests was chosen over Style arbitrarily between the two remaining candidates, and this choice is fixed here so it doesn't drift during implementation.
- **What agent-level hooks see that run-level hooks don't:** agent-level hooks are scoped to that one agent's own internal lifecycle — e.g., they can observe each individual tool call that specific agent makes, and any intermediate reasoning steps the SDK exposes at the agent level — detail a run-level hook, which watches the run as a whole from the outside across all three reviewers uniformly, does not surface in the same granular, per-agent way.

---

## 8. Guardrail Architecture (FR-8)

- The output guardrail (`secret_guardrail.py`) is attached at the point where the Desk is about to deliver its final report (and, per Constitution Section 5, also governs Remediation's responses).
- **Detection approach:** pattern-based scanning for credential-shaped strings — e.g., long high-entropy alphanumeric tokens, strings matching common API-key prefixes (`sk-`, `AIza`, etc.), and strings explicitly labeled as secrets/passwords/tokens in the surrounding diff/finding text. The exact pattern set is refined during implementation but must, at minimum, catch an obviously fake planted key used in `tests/test_output_guardrail.py`.
- **On trigger:** the SDK's output-guardrail tripwire mechanism raises; the application layer catches this specific exception and returns a `GuardrailResult(tripwire_triggered=True, reason=...)`-driven refusal message to the user — never a raw exception, never a silently-edited report.
- **Cost note (explicit, for the viva):** by the point this guardrail runs, all three reviewer calls and the Merge tool call have already completed and already consumed tokens/cost. This is a deliberate architectural trade-off — catching leaks as a final gate rather than filtering each reviewer's output individually — and is documented here so it is never mistaken for an oversight.

---

## 9. Tool Inventory (FR-1, FR-2, FR-9)

### 9.1 `read_diff_chunk`
- **Purpose:** given a file identifier, return that file's chunk of the already-split diff.
- **Used by:** all three reviewer clones.
- **Input (model-visible):** `{ "file": str }`
- **Output:** the raw diff text for that file, or a plain error string if the chunk can't be found.
- **Context use:** none beyond looking up the pre-split chunks held in the run's local state.
- **Required?** Yes, implicitly, since a reviewer cannot produce findings without it — but not configured as SDK-level "forced," since a reviewer might legitimately call it more than once per file across turns.
- **Error handler:** wraps any file-lookup failure and returns `"Could not read diff for file: <file>. It may not be part of this diff."` — never raises.

### 9.2 `lookup_ruleset`
- **Purpose:** given the `ruleset_id` from `ReviewContext` (read via the context wrapper, never as a model-supplied parameter), return the applicable ruleset text.
- **Used by:** all three reviewer clones; **forced/required** specifically for the Security Reviewer (FR-9, control #1).
- **Input (model-visible):** none — the tool's generated schema takes no parameters at all, since `ruleset_id` comes from context, not from the model.
- **Output:** the ruleset's text content, or a plain message if the ruleset file is missing (`"No ruleset found for id '<ruleset_id>'. Proceeding with general best practices."`) — this is exactly the FR-9 "deleting the ruleset file" scenario, and it must never raise.
- **Context use:** reads `ruleset_id` from the wrapped `ReviewContext`.
- **Required?** Yes for Security (SDK-level forced-tool-use configuration); available-but-optional for Tests and Style.
- **Error handler:** internal try/except around file access; always returns a string, never an exception.

---

## 10. Tracing Architecture (FR-13)

- Tracing is initialized once at application startup (CLI and Chainlit share the same initialization path), exported under the value of `TRACING_API_KEY`.
- The Desk's top-level run is the root span. The three reviewer runs, the Merge tool call, and the Remediation handoff (if triggered) are all nested/associated spans under that same root — the SDK's default behavior of grouping a `Runner.run(...)` call and everything it triggers into one trace is relied upon here, and no code path is allowed to start a second, disconnected trace mid-review.
- **Manual verification step (documented in `tests/test_tracing_manual_checklist.md`):** after a live review, open the exported trace and confirm (a) exactly one trace exists for that review, (b) the three reviewer spans visibly overlap in time, and (c) the slowest of the three can be identified directly from the trace's span durations.

---

## 11. Custom Runner / Ledger Architecture (FR-11)

- `ledger_runner.py` defines a custom Runner subclass/wrapper that, after every individual agent run completes (reviewer, Merge, or Remediation), appends one JSON line to `ledger.jsonl` using the shape in Section 4.8.
- This custom runner is registered **once**, at application startup, in `src/config/settings.py` or an equivalent single bootstrap location — never referenced from within any individual agent's own definition file.
- **To disable the ledger:** remove that single registration call. No agent file changes.
- `request_id` is generated once per top-level review (not per individual agent run) and threaded through every ledger line belonging to that review, so all of a single review's lines can be grouped together when reading the file back.

---

## 12. Report Assembly and Delivery Flow

```
Diff path / paste
    ↓
diff_splitter.py → per-file chunks
    ↓
ReviewContext constructed
    ↓
concurrency.py → asyncio.gather(Security, Tests, Style)   [FR-5]
    ↓
list[ReviewerResult]  (findings + hook metrics per reviewer)
    ↓
Merge specialist (as_tool)  →  MergedReport                [FR-6]
    ↓
report_builder.py → FinalReport (findings + footer)        [FR-10]
    ↓
secret_guardrail.py  → pass through  OR  refusal            [FR-8]
    ↓                                        ↓
critical security finding? ──yes──▶ Remediation handoff     [FR-6]
    │no
    ▼
FinalReport delivered to user (CLI print / Chainlit stream) [FR-12]
    ↓
ledger_runner.py has already logged each run as it happened  [FR-11]
    ↓
One trace covers the whole thing, viewable after the fact    [FR-13]
```

---

## 13. Dependencies

| Package | Purpose |
|---|---|
| OpenAI Agents SDK | Agents, Runner, tools, handoffs, guardrails, hooks, tracing |
| `pydantic` | `Finding`, `MergedReport`, `FinalReport`, and other typed models |
| `python-dotenv` | Loading `.env` at startup |
| Gemini-compatible client/adapter (as required by the Agents SDK's model-provider configuration) | Connecting agents to `gemini-3.5-flash` / `gemini-2.5-flash` |
| `chainlit` | Web UI (FR-12), installed only inside the project's dedicated virtual environment (Constitution, Section 9) |
| `pytest` / `pytest-asyncio` | Automated tests across `tests/` |

---

## 14. Cut List (Restated From Constitution, for Implementation Reference)

If time runs short during the build, cut in this exact order, and no other:

1. **First:** FR-11 (ledger) — remove the one custom-runner registration; everything else keeps working.
2. **Second:** FR-7 (run-level cheaper override) — the reviewers still work fine on their primary model alone.
3. **Third:** the agent-level hooks portion of FR-10 specifically (leave the run-level hooks/footer intact).

**Never cut:** FR-5 (concurrency) or FR-8 (output guardrail) — these are architecturally load-bearing for the rest of the plan above and are what the viva will focus on.

---

## 15. Open Implementation Decisions Deferred to `tasks.md`

The following are intentionally left for `tasks.md` to sequence, since they are ordering/process decisions rather than architecture:

- Exact commit boundaries within Phase 0 vs. Phase 1–3.
- Which tests are written before vs. after their corresponding implementation task.
- The precise wording of UI copy (refusal messages, partial-review labels, the "API key required" message) — content decisions, not architectural ones.