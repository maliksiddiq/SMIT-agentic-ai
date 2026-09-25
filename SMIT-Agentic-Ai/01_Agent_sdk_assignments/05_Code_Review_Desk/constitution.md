# Constitution — Code Review Desk

This document defines the rules that this build **may not break**, at any phase, under any circumstance. If any decision made later — in `spec.md`, `plan.md`, `tasks.md`, or in actual code — conflicts with something written here, the decision is wrong, not this document. From this point forward, this constitution together with `spec.md`, `plan.md`, and `tasks.md` are the **only** source of truth for this project. There is no external specification document behind them; these four files fully define what is being built.

This file is committed first, as part of Phase 0, before a single line of implementation code exists.

---

## 1. Model Provider

- The project uses **Google Gemini** as its model provider, for every agent, with no exceptions.
- **Two model variants are supported side by side**, not just one:
  - **`gemini-3.5-flash`** — the default, primary model used by every reviewer agent unless explicitly overridden.
  - **`gemini-2.5-flash`** — kept as a fully supported fallback/alternate model, not removed or deprecated. It must be selectable without touching any agent's core definition — for example, via an environment variable (e.g. `GEMINI_MODEL_PRIMARY` / `GEMINI_MODEL_FALLBACK`) or a run-level override, so the project can drop back to `2.5-flash` if `3.5-flash` is ever unavailable, rate-limited, or otherwise unusable, without a code change.
  - Whichever of the two is active as the "default" for an agent, it is still configured **at the agent level** — the fallback mechanism does not violate agent-level model configuration; it simply lets the *value* assigned at that level be chosen from two known-good options.
  - Documentation, `.env.example`, and `plan.md` must name both model strings explicitly, so it is never ambiguous which one is currently active.
- The model is configured **at the agent level**, never via a global/default client. No file in this project may create a process-wide default model or default client — every agent declares its own model explicitly, whether that value resolves to `3.5-flash` or `2.5-flash`.
- A run-level override (used specifically for the "cheaper second opinion" requirement) is permitted and expected, but it must only ever change the model **for that one run call**. It must never mutate an agent's own stored `model=` attribute, and it must never be confused with the primary/fallback selection described above — those are two separate mechanisms serving two separate purposes.

---

## 2. Secrets

- All credentials (Gemini API key, tracing export key, and any other secret) live **only** in a `.env` file.
- `.env` is listed in `.gitignore` and must never be committed — not once, not accidentally, not "temporarily for testing."
- A `.env.example` file (with placeholder values, no real secrets) is committed instead, so the required variables are documented without exposing anything.
- If a required key is missing at startup, the program fails immediately with **one clear, human-readable sentence** — never a raw stack trace or traceback.
- No secret may ever appear in:
  - the final report shown to the user,
  - `ledger.jsonl`,
  - trace/log output sent to the tracing backend,
  - anything printed to stdout/stderr during normal operation.
- Anything that resembles a credential found *inside a reviewed diff* is treated as sensitive content and is subject to the output guardrail (Section 5) before it can leave the Desk in any form — report, footer, or streamed UI text.

---

## 3. Tool Behavior

- **No tool may ever raise an exception directly into the Runner.** Every tool capable of failing (diff reading, ruleset lookup, file access, etc.) must catch its own failures internally and return a clear, model-usable error message instead of propagating an exception upward.
- A tool that raises into the Runner is, by definition, **a defect** in this project — not an acceptable edge case, not something to "fix later." It must be corrected before the project can be considered done.
- Tools that are required for correctness (e.g., the ruleset-consultation tool for the reviewer that must use it) are configured so the model has **no choice** but to call them. This is an explicit, structural tool-use requirement enforced by configuration — not a soft suggestion placed in instruction text.
- Every review runs under an enforced **turn ceiling**. When that ceiling is reached, the resulting exception is caught and the result is reported to the user as a **partial review**, clearly labeled as such — never as a silent failure or a crash.

---

## 4. Reproducibility

- A review must be **fully reproducible from the diff alone.** Given the same unified diff and the same `ReviewContext` (repo, language, ruleset_id, strictness), the pipeline must be able to reproduce the same review, with no hidden inputs, no reliance on local mutable state, and no side channels outside of the diff and the context object.
- No review step may depend on data that is not either (a) contained in the diff itself, or (b) explicitly present in the `ReviewContext` passed into that run.
- Session-held state in the Chainlit UI (e.g., "last report," reused context within a session) is a **user convenience**, not a hidden dependency the underlying review pipeline relies on to function. The pipeline itself must work correctly even outside of a Chainlit session (e.g., run from the CLI).

---

## 5. Output Integrity

- Nothing leaves the Desk that quotes a secret found in the diff, in any surface — CLI, report, or Chainlit UI. This is enforced programmatically by an **output guardrail** that inspects the finished report before it is handed to the user.
- If the guardrail's tripwire fires, the program **catches it and reports a refusal** — it never crashes, and it never silently strips the offending content and continues as if nothing happened. The refusal itself, clearly shown, is the correct and expected outcome.
- A clean report — one containing nothing credential-shaped — passes through the guardrail untouched and reaches the user normally.

---

## 6. Concurrency Is Not Optional

- The three reviewers — Security, Tests, and Style — **must** run concurrently: launched together and awaited as a group, over the same diff.
- A sequential implementation that merely produces correct results does **not** satisfy this project, even if every individual review is accurate. Concurrency is a first-class, non-negotiable architectural requirement here, not a performance optimization to add "if there's time."
- The difference between concurrent and sequential wall-clock time must be demonstrable at any point, on demand.

---

## 7. Observability

- Every review is traceable as **one single trace** — all three reviewers, the merge step, and any handoff (when triggered) live inside that one trace, with the three reviewer spans shown **overlapping** in time, never stacked one after another.
- Every run is recorded as exactly one line in `ledger.jsonl`, written by a custom runner that is registered **once**, at startup. No agent definition may reference the ledger directly or know that it exists.
- Token and latency figures shown to the user (in the report footer) must come from **actual run-context data**, never estimated or guessed at.

---

## 8. Specification Before Implementation

- No source code file is written until all four Phase 0 documents — `constitution.md`, `spec.md`, `plan.md`, `tasks.md` — are committed to git.
- A single commit containing **both** spec content and implementation code **fails Phase 0**, even if the resulting code runs correctly. Specification and code must be cleanly separated in commit history, because that history is the evidence that specification preceded implementation.
- These four documents, once committed, are the complete and only definition of the project going forward — there is no separate external spec to reconcile against.

---

## 9. Environment and Runtime Constraints

- **The goal at runtime is simple: Chainlit must run smoothly, without friction, regardless of what Python version happens to be installed on the machine.**
- Before any implementation work touching the Chainlit interface begins, the currently active Python interpreter must be checked against Chainlit's supported version range.
- **If the system's current/default Python version is not compatible with Chainlit**, a **dedicated virtual environment must be created for this project**, and that virtual environment must be pinned to whichever Python version is known to let Chainlit run easily and without issues (i.e., a version squarely inside Chainlit's officially supported range at the time of setup — not the newest available version by default, and not an assumption carried over from an unrelated project).
- All project dependencies — the Agents SDK, Chainlit itself, Pydantic, `python-dotenv`, and anything else the project needs — are installed **inside that virtual environment only**. Nothing is installed into the system-wide Python installation.
- The chosen Python version and the exact virtual-environment setup steps must be documented (in the README and/or `plan.md`), so environment setup is fully reproducible by anyone re-running this project from scratch — consistent with the reproducibility principle in Section 4.
- Do **not** attempt to force Chainlit onto an incompatible interpreter by downgrading, patching, or pinning individual package versions around it. The correct and only accepted fix is an isolated virtual environment running a Chainlit-compatible Python version. This is treated as a setup prerequisite, not an optional troubleshooting step.

---

## 10. Interface Quality

- The Chainlit UI is not a throwaway debug console — it is the primary surface this project is demonstrated and judged through. It must be **clean, well-organized, and genuinely pleasant to use**, not merely functional.
- At minimum:
  - Findings must be clearly readable as they stream in — formatted and legible, not a raw dump of unstructured text.
  - The final report and its metrics footer must be visually distinguishable from the live streaming findings that preceded it.
  - Error and refusal states (e.g., a guardrail refusal, a partial-review-due-to-turn-ceiling message) must be presented clearly and legibly — never as a blank screen, a broken layout, or an unhandled exception surfaced to the user.
  - Reused session context and a "second diff in the same session" should feel like a natural continuation of the interface, not a jarring reset.
- Polish is secondary to correctness and to whatever the cut list in `tasks.md` dictates under time pressure — but within the time available, UI clarity is treated as a genuine requirement, not an afterthought bolted on at the end.

---

## 11. Project Location and Folder Name

- The entire project — all four Phase 0 documents, all source code, `ledger.jsonl`, `.env`/`.env.example`, the virtual environment, tests, and the Chainlit app — lives inside a single fixed project folder named **`05_Code_Review_Desk`**.
- On the developer's machine, this folder's full path is:

  ```
  D:\Agentic-Ai\SMIT-Agentic-Ai\01_Agent_sdk_assignments\05_Code_Review_Desk
  ```

- `05_Code_Review_Desk` is the **project root**. Every path referenced anywhere in this project — in `plan.md`, `tasks.md`, code, scripts, or documentation — is relative to this root, never to an absolute path outside it, so the project stays portable to any machine (only the drive/parent path changes; the folder name and its internal structure do not).
- **There is no permission to work outside this folder, and no permission to create any other project folder anywhere else.** All files, folders, code, environments, and configuration created for this project — with zero exceptions — are created strictly inside `05_Code_Review_Desk`. No sibling folder, no folder one level up, no folder under a different name, and no folder in a different location is ever created to hold any part of this project, even temporarily, even for testing, even "just to try something."
- Nothing belonging to this project is created, written, or committed outside `05_Code_Review_Desk`. Anything that must exist outside it (e.g., a system-wide tool install) is documented separately, not treated as part of the project itself.
- Git is initialized at the root of `05_Code_Review_Desk`, and it is this folder's own `.git` history — starting with the Phase 0 commit — that serves as the graded evidence referenced in Sections 4 and 8.

---

## 12. Build Continuity When API Keys or Quota Are a Problem During Development

- This section applies specifically to the **build/development phase** — while the project itself is being created — as distinct from how the finished product behaves for an end user at runtime (that is covered separately below and in Section 2).
- **If, during development, the Gemini API key is missing, invalid, or its quota is exhausted, this must never stop the build from being completed.** The coding agent does not pause implementation, does not ask to wait for a working key, and does not leave requirements half-implemented because a live call could not be made. The project must be carried all the way to completion regardless of whether a working key was available at every step along the way.
- This continuity is achieved **only** through the project's own proper key-handling and error-handling logic — the same startup validation, `.env`-based configuration, and tool/guardrail error handling already required elsewhere in this constitution (Sections 2 and 3) — never through ad-hoc `if/else` shortcuts, hardcoded bypasses, skipped requirements, or temporary "fake it for now" branches scattered through the code. In other words: the API-key handling that the project needs anyway (fail clearly, don't crash, don't leak secrets) is the same logic that lets development continue smoothly past a key/quota problem — it is not a separate workaround bolted on for convenience.
- **This behavior is strictly a development-phase instruction, not a product feature.** The finished, running application does not silently continue or fabricate results when it has no working key. Once the project is complete:
  - If an end user interacts with the finished app (CLI or Chainlit UI) and no valid API key is configured, the UI must clearly display a message such as **"API key required"** (or an equivalently clear, human-readable message) — never a silent failure, a blank screen, a raw traceback, or fabricated output pretending a review happened.
  - This end-user-facing message is exactly the "fails immediately with one clear, human-readable sentence" behavior already mandated in Section 2 — it is the same rule, simply surfaced through the Chainlit UI as well as the CLI.

---

## 13. Amendments

This constitution may only be amended by explicitly editing this file and recommitting it — it is never silently overridden or contradicted by a later document or by code. If `spec.md`, `plan.md`, or `tasks.md` ever appear to conflict with anything written here, this file takes precedence, and the conflicting document must be corrected to match it.