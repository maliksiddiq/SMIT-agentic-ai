# Specification — Code Review Desk

This document describes **what the Code Review Desk does, as behavior** — not how it is coded. Every functional and non-functional requirement is restated here in plain terms, together with *why* it exists, what a person would actually see happen, and the edge cases that must be handled. Together with `constitution.md`, `plan.md`, and `tasks.md`, this file is part of the complete and only definition of the project (see Constitution, Sections 8 and 13).

This file is committed as part of Phase 0, before a single line of implementation code exists.

---

## 1. What the Desk Is

The Code Review Desk is an AI-powered code review pipeline built on the OpenAI Agents SDK, using Google Gemini as the model provider.

A user submits a **unified diff** — either as a file path on the command line, or pasted directly into a web page. The Desk splits that diff by file and hands it to three specialist reviewers — **Security**, **Tests**, and **Style** — who each read it **at the same time**, from their own angle, using instructions tuned specifically for what they're looking for. Their individual findings are merged into one deduplicated, severity-ordered report. If any reviewer surfaces a **critical security finding**, control of the conversation passes to a **Remediation** specialist, who proposes a concrete fix directly to the user instead of returning a plain report. Before anything reaches the user, the finished report is checked to guarantee it never quotes a secret that happened to be sitting in the diff. In the web interface, findings appear progressively as they're produced — not dumped all at once at the end — and every full review, from the three reviewers through any handoff, is captured as a single, inspectable trace.

**In one sentence:** it is a fan-out/fan-in agent pipeline — one diff goes in, three agents work on it in parallel, and one safe, structured, observable result comes out.

---

## 2. Why This Project Exists

This build exists to demonstrate, in a single working system, a set of Agents SDK capabilities that don't show up in a simple single-agent chatbot:

- Running multiple agents **concurrently** instead of one at a time.
- Passing **local context** to tools without ever exposing it to the model.
- Getting **structured, typed output** back from a model instead of parsing prose.
- Using **agents-as-tools** and **handoffs** for two genuinely different kinds of delegation.
- Enforcing **output-side safety** with a guardrail that can refuse a finished result.
- Giving **required tools**, **non-raising tool failures**, and a **turn ceiling** so a model can't spiral out of control.
- Recording **real, measured** performance data (hooks) instead of estimates.
- Making the whole thing **observable** end-to-end (tracing + a ledger).
- Delivering the result through a **streaming**, live interface instead of a single blocking response.

Every requirement below exists to force one of these capabilities to actually be built and demonstrated, not just described.

---

## 3. Behavior, Requirement by Requirement

Each requirement below states: what happens, why it's required, what a person would concretely observe, and the edge cases that must be handled correctly.

---

### 3.1 FR-1 — Diff Intake and Splitting

**What happens:**
The user provides a unified diff via a file path given on the command line. The Desk reads that file **asynchronously** and, **before any model ever sees the content**, splits it into one chunk per file changed in the diff. Only after this splitting is complete does any reviewer agent receive input. The model used by every agent is configured directly on that agent (primary `gemini-3.5-flash`, with `gemini-2.5-flash` as a fully supported fallback, per `constitution.md` Section 1) — there is no single shared/global default client anywhere in the code.

**Why this exists:**
Splitting before any model call keeps each reviewer's context focused on relevant file content rather than a giant undifferentiated blob, and it proves the pipeline is a real intake/parsing stage, not just "paste the whole diff into a prompt."

**What a person observes:**
- Pointing the Desk at a two-file diff produces exactly two chunks, one per file.
- Pointing it at an empty or malformed diff produces a **plain, readable error message** — never a Python traceback.
- Grepping the codebase for a global/default client configuration call finds nothing.

**Edge cases covered:**
- Diff path does not exist → clear message, not a crash.
- Diff file exists but is empty → clear message.
- Diff file exists but is not valid unified-diff format → clear message, not a parser exception surfacing raw.
- Diff touches a file with no actual content changes (e.g., a mode-only change) → still produces a chunk for that file, even if trivial.

---

### 3.2 FR-2 — Repository Rules Live in Context

**What happens:**
Every review run carries a `ReviewContext`:

```python
@dataclass
class ReviewContext:
    repo: str
    language: str
    ruleset_id: str
    strictness: str = "normal"      # "normal" or "strict"
```

This context is **local, application-level data**, attached to the run itself. Tools that need it (like the ruleset-lookup tool) read it through the run's context wrapper — never through a parameter the model has to fill in.

**Why this exists:**
This is the clearest demonstration in the whole project of the difference between **local/application context** (data your code needs) and **model-visible context** (data the model actually sees in its prompt). Repository names and internal ruleset identifiers are exactly the kind of information that should never leak into a prompt — this FR forces that separation to be real, not assumed.

**What a person observes:**
- A tool reads `ruleset_id` successfully during a run — but that tool's generated schema, as the model sees it, has **no** parameter for repo, language, ruleset, or strictness.
- Grepping every prompt string sent to Gemini across a full review finds **no occurrence of the repository name**, anywhere.

**Edge cases covered:**
- `strictness` is omitted by the caller → defaults to `"normal"`, not an error.
- `strictness` is given a value other than `"normal"`/`"strict"` → rejected/normalized at construction time, not silently accepted and misinterpreted downstream.

---

### 3.3 FR-3 — Findings Come Back as Typed Objects

**What happens:**
A reviewer never returns free-form prose. Every reviewer's `output_type` is `list[Finding]`:

```python
class Finding(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "major", "minor"]
    message: str
```

Internally, when the SDK builds a **strict** JSON schema for "a list of findings," it wraps that list inside a single-key object, because strict schemas require an object at the root — a bare list can't be the root of a strict schema. This wrapping is purely a schema-generation detail. What the developer actually gets back in `final_output` after a run is a **plain Python list** of `Finding` objects.

**Why this exists:**
Structured output is what makes findings mergeable, sortable, countable, and guardrail-inspectable in code — a paragraph of prose can't be deduplicated or ordered by severity programmatically with any reliability.

**What a person observes:**
- Counting critical findings from a completed review is a one-line Python expression (e.g., `sum(1 for f in final_output if f.severity == "critical")`) — no string-parsing involved.
- Printing the tool/output schema shows the object-wrapper around the list, and that wrapper can be pointed at and explained on demand.

**Edge cases covered:**
- A reviewer finds nothing wrong → returns an empty list, not `None` and not omitted output.
- A model attempts to return something that doesn't validate against `Finding` → this is a structured-output validation failure, handled the same way any other model-output problem is handled (surfaced clearly, not silently coerced into a wrong shape).

---

### 3.4 FR-4 — Reviewer Instructions Are Built Per Run

**What happens:**
A reviewer's system prompt is not a fixed string baked in when the agent is defined. It is assembled **fresh, at the moment a run starts**, using the ruleset and language from that run's `ReviewContext`. When `strictness` is `"strict"`, the resulting prompt is noticeably **terser** than the prompt produced for the same ruleset/language under `"normal"` strictness.

**Why this exists:**
This demonstrates dynamic instructions — proving that agent behavior can meaningfully change per-run based on context, without needing a separate hardcoded agent for every ruleset/language/strictness combination.

**What a person observes:**
- Two different `ReviewContext` values (different language, or same language with different strictness) produce two visibly different resolved prompt strings.
- Because instructions are resolved before any model call happens, the exact prompt text can be printed and inspected **without spending an API call** — this is testable offline.

**Edge cases covered:**
- An unknown or unsupported `language` value in context → the instruction-builder degrades gracefully (e.g., falls back to generic language-agnostic phrasing) rather than throwing.
- A `ruleset_id` with no matching ruleset content → produces an instruction set that says so plainly, consistent with FR-9's "deleting the ruleset file" test case.

---

### 3.5 FR-5 — Three Reviewers, Cloned, Running Concurrently *(never cut — see Constitution Section 6)*

**What happens:**
There is exactly **one base reviewer** definition. The Security, Tests, and Style reviewers are each a **clone** of that base — sharing everything about how a reviewer fundamentally works, but each with its own tuned instructions (what to look for) and its own model settings. All three are handed the **same diff** and run **at the same time**: launched together and awaited as a single group, not started one after another.

**Why this exists:**
This is the architectural centerpiece of the whole project — proving that a fan-out of specialized agents over the same input is materially different, and materially faster, than calling one agent three times in sequence.

**What a person observes:**
- The three reviewers' calls are visibly launched together in code (e.g., via a concurrent-gather pattern), not called and awaited one at a time.
- The total wall-clock time for all three to complete is close to whichever single reviewer is the **slowest** — not the sum of all three individual times.
- Both numbers — the concurrent total, and what a sequential run of the same three reviewers would take — can be shown side by side on demand.

**Edge cases covered:**
- One reviewer fails or times out while the other two succeed → the pipeline still needs to report the two successful reviews plus a clear note about the failed one, rather than the entire review failing because one of three agents had a problem.
- **Explicitly disallowed:** a version where all three reviewers technically produce correct findings but are called sequentially. This produces identical-looking output to the user but **does not satisfy this requirement** — concurrency and the ability to prove it via timing is the requirement itself, not just correctness of the findings.

---

### 3.6 FR-6 — Merge as a Tool, Remediation as a Handoff

**What happens:**
Two specialists exist, wired **two deliberately different ways**:

- **Merge specialist**, exposed as a tool (`as_tool`). It receives the raw findings from all three reviewers, removes duplicate/overlapping findings, and orders what remains by severity. The Desk calls it like any other tool, receives a result back, and **stays in control of the conversation** the entire time.
- **Remediation specialist**, reached by **handoff**. This activates only when the merged findings include at least one **critical security finding**. When triggered, control of the conversation **transfers** to Remediation, which speaks to the user directly, proposing a concrete patch.

**Why merging is a tool call:** Merging is a bounded, single-purpose transformation with a clear input (raw findings) and a clear output (deduplicated, ordered findings). The Desk needs that result back so it can keep composing the rest of the report — exactly what a tool call is designed for.

**Why remediation is a handoff:** Proposing a fix is open-ended and conversational — it may need follow-up, clarification, or back-and-forth about the proposed patch. It doesn't hand a tidy result back to the Desk to continue with; it takes over and finishes the interaction on its own terms — exactly what a handoff is designed for.

**What would break if swapped:** If Merge were a handoff, the Desk would lose control of the conversation over something as mechanical as deduplication — an awkward, unnecessary conversational transfer for a task that has one clean answer. If Remediation were a tool, its open-ended, potentially multi-turn patch discussion would be forced into a single bounded tool response, losing the ability to have a real conversation about the fix.

**What a person observes:**
- A diff with no critical security finding → Merge runs, the Desk delivers the final report itself, no handoff occurs.
- A diff with a critical security finding → Merge still runs as a tool first (to produce the merged findings), then the handoff to Remediation fires, and Remediation — not the Desk — delivers the next message to the user.

**Edge cases covered:**
- Multiple critical security findings in one diff → Remediation must address the situation as a whole (not just the first finding found), and the spec expects Remediation's response to make clear which finding(s) it's responding to.
- A critical finding from **Tests** or **Style** (not Security) → per this requirement, the handoff trigger is specifically a **critical security finding**; non-security critical findings do not trigger Remediation, and this distinction must be preserved exactly.

---

### 3.7 FR-7 — A Cheaper Second Opinion, Configured at the Run Level

**What happens:**
The Desk can re-run an already-defined reviewer on a **cheaper model**, purely by changing something about *that one run call* — never by editing, cloning, or redefining the reviewer itself.

**Why this exists:**
This demonstrates that model selection can be a **run-time** decision, not just a fixed agent-time one — useful for cost control (e.g., "give me a fast/cheap pass first, escalate to the primary model only if needed").

**What a person observes:**
- The exact same reviewer object is used for two calls: one using its own configured model, one using a run-level override.
- Inspecting the reviewer object's own `model=` attribute before and after the cheaper run shows **no change** — the override exists only at the run boundary, never mutating the agent.

**Edge cases covered:**
- The override target model is itself unavailable → this falls under Constitution Section 1's primary/fallback mechanism, which is a *separate* concern from the FR-7 run-level override and must not be conflated with it in the implementation.

---

### 3.8 FR-8 — Nothing Leaks: an Output Guardrail *(never cut — see Constitution Section 6)*

**What happens:**
After the report is fully assembled — after all three reviewers ran and Merge has already produced its output — but **before** it reaches the user, the finished report passes through an **output guardrail**. This guardrail inspects the report's text for anything shaped like a credential: something resembling an API key, a token, or a password, most likely one that was copied out of the diff into a finding's message.

**Why this exists:**
This is the project's explicit safety net against the single worst outcome for a code-review tool: repeating a live secret back to whoever is reading the review. It exists specifically as a **final** checkpoint, catching anything that slipped through the reviewers themselves.

**What a person observes:**
- A diff containing a planted fake credential (e.g., a fake API key string) → the guardrail's tripwire fires, the Desk **catches** it internally, and the user sees a clear **refusal** message instead of the report.
- A clean diff with nothing credential-shaped in it → passes through the guardrail completely untouched, and the normal report reaches the user.
- The exact line of code where the tripwire exception is caught can be pointed at and explained on demand.

**Edge cases covered:**
- The guardrail must never **crash** the program — catching the tripwire is mandatory, not optional.
- The guardrail must never **silently strip** the offending text and ship the rest of the report as if nothing happened — a refusal is the only acceptable outcome once the tripwire fires.
- By the time this guardrail runs, all three reviewer calls and the merge call have **already happened and already cost money/tokens** — this is a deliberate, known trade-off (a late gate rather than an early filter) and must be explainable as such, not treated as an oversight.

---

### 3.9 FR-9 — Required Tools, Failing Tools, and a Turn Ceiling

**What happens:** Three separate controls, all present simultaneously:

1. **A forced tool call.** The reviewer responsible for consulting the ruleset is configured so it has **no choice** but to call the ruleset tool during its run — this is enforced by configuration, not left to instruction-text persuasion.
2. **Tools fail softly.** If a diff-reading tool hits a problem, a dedicated error handler catches it and returns a plain, model-readable message. The failure never becomes an unhandled exception reaching the Runner.
3. **A turn ceiling.** Every review is bounded by a maximum number of turns. If a review hits that ceiling, the resulting exception is caught, and the Desk reports the result as a clearly labeled **partial review**.

**Why this exists:**
Together, these three controls are what stop a reviewer from spiraling — calling a tool in an unbounded loop, silently failing into a crash, or simply never finishing. This is the project's answer to "what happens when a model misbehaves," addressed structurally rather than hoped away.

**What a person observes:**
- Deleting the ruleset file entirely still results in a review that **finishes** and reports a sensible message about the missing ruleset — the whole pipeline does not break.
- The specific turn-ceiling number chosen, and the reasoning behind it, are documented in `plan.md` and must be explainable on request (this is one of the eight defense questions).

**Edge cases covered:**
- A tool failure that happens on the very first call a reviewer makes → the reviewer must still be able to continue and produce *some* usable output/message, not simply die immediately.
- A review that finishes normally, well under the turn ceiling → the ceiling logic must be provably inert in this case (no artificial delay, no spurious "partial" labeling).

---

### 3.10 FR-10 — Latency and Tokens per Reviewer

**What happens:**
Every finished report includes a **footer** with one row per reviewer (three rows total) showing how long that reviewer took and how many tokens it used. These numbers come from **run-level hooks**, which observe every reviewer's execution and pull real duration and real token counts from the run's own context. In addition, exactly **one** reviewer (chosen and documented in `plan.md`) also carries its own **agent-level hooks**.

**Why this exists:**
This forces a real distinction between two different hook mechanisms in the SDK — one that watches a run from the outside (all reviewers, uniformly), and one attached to a single agent that sees that agent's own internal lifecycle in more detail. Measuring real numbers (not estimates) also reinforces the project's observability requirements.

**What a person observes:**
- The footer's three rows show token counts that trace directly back to real run-context data — never a hardcoded or approximated number.
- What the one agent-hooked reviewer's hooks can observe (its own internal steps, its own tool calls in detail) versus what the run-level hooks see about all three reviewers from the outside can be explained clearly, with a concrete example from that reviewer's run.

**Edge cases covered:**
- A reviewer that fails or hits the turn ceiling → its footer row must still show *something* meaningful (e.g., partial timing, or a clear "incomplete" marker) rather than being silently omitted from the footer.

---

### 3.11 FR-11 — Every Run Lands in a Ledger

**What happens:**
Every time any agent runs, one line is appended to `ledger.jsonl` — timestamp, request ID, agent name, duration in milliseconds, and number of findings produced. This is handled by a **custom runner**, registered exactly **once** at application startup. No individual agent definition knows the ledger exists.

```json
{"ts": "2026-09-23T19:04:11Z", "request_id": "rev_8f21", "agent": "SecurityReviewer", "ms": 2140, "findings": 3}
```

**Why this exists:**
This demonstrates a custom Runner as a cross-cutting observability layer — something that applies uniformly to every run without any individual agent needing to be aware of or coupled to it.

**What a person observes:**
- Reviewing a three-file diff produces one ledger line for **every run that actually happened** during that review — which may be more than three, since Merge (and Remediation, if triggered) are runs too.
- Turning the ledger off requires removing **only** the one central registration call — nothing about any agent's own definition needs to change.

**Edge cases covered:**
- A review that has more ledger lines than the person expected (e.g., they expected exactly 3 but got 5) → this is expected behavior, not a bug, if Merge and/or Remediation also ran as their own logged runs during that review; this must be explainable, not treated as an anomaly to suppress.

---

### 3.12 FR-12 — Findings Stream Into the Interface

**What happens:**
A Chainlit web page lets a user paste a diff directly and watch the review happen live. Findings appear progressively as reviewers produce them — never as one large block dumped at the end. Session state holds the current `ReviewContext` and the most recent report, so pasting a second diff into the same session reuses the existing context rather than asking for it again. The handler behind this page always **awaits** the asynchronous run — never a blocking/synchronous variant.

**Why this exists:**
This is the project's user-facing demonstration of everything else working together — concurrency, structured output, guardrails, and hooks all have to come together to produce a coherent, live-updating interface, not just work correctly in isolated backend tests.

**What a person observes:**
- Text/findings appear progressively during a review, not all at once at the end.
- A second diff pasted into the same session reuses the existing `ReviewContext` — the user is not re-prompted for repo/language/ruleset/strictness.
- Per Constitution Section 9, this page only ever runs inside the project's dedicated virtual environment, on a Python version Chainlit is confirmed to support.
- Per Constitution Section 10, the page is visually clean: findings are legibly formatted as they stream, the final report/footer is visually distinct from the findings that streamed in before it, and refusal/partial-review states are shown clearly — never a blank or broken screen.

**Edge cases covered:**
- A guardrail refusal occurring mid-session → the Chainlit UI must show this clearly (per Constitution Section 10) rather than leaving the user staring at a stalled or blank interface.
- No API key configured → per Constitution Section 12, the UI shows a clear **"API key required"** message rather than hanging or crashing.

---

### 3.13 FR-13 — One Review, One Trace

**What happens:**
Tracing is enabled for the whole application and exported under the developer's own tracing key. A single review — all three reviewers, the merge call, and the remediation handoff if triggered — is captured as **one trace**, not as several separate, disconnected traces.

**Why this exists:**
This is the project's proof, at the observability layer, of everything FR-5 claims about concurrency — a single trace with overlapping spans is direct visual evidence that the reviewers really ran in parallel, not just correct-looking output that happens to have been produced quickly.

**What a person observes:**
- Opening the trace for a review shows the three reviewer spans **overlapping in time** with each other — not stacked one after another.
- From that same trace, the **slowest** of the three reviewers for that specific run can be identified by name.

**Edge cases covered:**
- A review that triggers the Remediation handoff → that handoff's span must appear **inside the same trace** as the rest of the review, not as a separate trace tied only loosely to the original review.

---

## 4. Non-Functional Requirements, as Behavior

### NFR-1 — Secrets
The application never asks the user for an API key inside the UI; it only ever reads one from `.env`. If that key is absent or invalid when the application starts, the user sees **one clear sentence** explaining that a key is required — never a Python stack trace. No secret — not the Gemini key, not the tracing key, not anything resembling one pulled from a diff — is ever written into `ledger.jsonl` or shown in a report, at any point, under any circumstance.

### NFR-2 — Cost
Every single agent in this project — every reviewer, Merge, Remediation — declares its own model settings explicitly. Nothing in the system generates without some bound on it: turn ceilings are always in effect, and "let it run and see what happens" is never an acceptable configuration state anywhere in this project.

### NFR-3 — Observability
For any review that has run, two independent ways exist to look back at it afterward: opening its trace (FR-13) and finding its line(s) in `ledger.jsonl` (FR-11). Combined with hooks (FR-10), nothing about a run's timing, token usage, or outcome is a mystery after the fact — every claim the footer or trace makes can be independently verified against the ledger.

### NFR-4 — Failure
Every tool in this project, when given bad input, responds with a plain sentence the model can act on or explain to the user — it does not throw an exception that the Runner has to deal with. Any tool that does raise into the Runner is treated as a **bug to fix**, never as a known/accepted limitation to work around or document away.

### NFR-5 — Provenance
`git log` for this project shows `constitution.md`, `spec.md`, `plan.md`, and `tasks.md` committed — as a distinct commit or commits containing only these documents — strictly **before** the first commit that contains any implementation code. This ordering is itself part of what gets checked and graded, per Constitution Section 8.

---

## 5. What This Project Deliberately Does Not Do

To keep scope honest and prevent quiet feature creep during the two-hour build, this project explicitly does **not**:

1. **Does not review more than one diff at a time, or review multiple repositories in a single run.** The Desk takes one unified diff per review. There is no batch mode, no multi-repo comparison, and no queue of pending diffs — one diff in, one report out, every single time.
2. **Does not automatically apply, commit, or push the Remediation specialist's proposed patch.** Remediation only ever *proposes* a fix in conversation with the user. Nothing in this project writes to the user's actual codebase, opens a pull request, or merges anything on its own — a human always remains the one who applies a fix.
3. **Does not persist review history across sessions or across restarts as a first-class feature.** Beyond the ledger (which exists purely for observability, per FR-11/NFR-3) and the current session's "last report" convenience in Chainlit (FR-12), the Desk does not build a searchable review history, does not answer "what changed since the last review of this repo," and offers no long-term storage of past reports. (Persisting reports for exactly that kind of question is explicitly listed as a stretch goal in `tasks.md`, not part of the core, required build.)

---

## 6. End-to-End User Flows

### 6.1 Normal Review, No Critical Security Finding
1. User provides a diff (CLI path or Chainlit paste).
2. Desk splits the diff by file.
3. `ReviewContext` is constructed for the run.
4. Security, Tests, and Style reviewers are launched together and run concurrently.
5. Their findings (each a `list[Finding]`) are collected once all three finish.
6. Merge specialist (tool call) deduplicates and severity-orders the combined findings.
7. Output guardrail inspects the merged report; it passes through untouched.
8. The final report — including the FR-10 latency/token footer — reaches the user (streamed live if via Chainlit).
9. One trace and one or more ledger lines exist for this review.

### 6.2 Review With a Critical Security Finding
1–6. Same as above.
7. The merged findings include at least one `severity == "critical"` finding from the Security reviewer.
8. Instead of only returning the merged report, the Desk hands off the conversation to the Remediation specialist.
9. Remediation examines the relevant finding(s) and proposes a concrete patch directly to the user, in conversation, stating clearly which finding triggered the response.
10. The output guardrail still governs anything Remediation says — no credential is ever repeated back to the user, by Remediation or by the Desk.

### 6.3 Diff-Reading Tool Failure
1. A diff-reading tool encounters bad input (e.g., a malformed file chunk).
2. The dedicated error handler catches this internally and returns a plain message.
3. The affected reviewer continues its review using that message rather than crashing.
4. The overall review still completes and is reported to the user, with the affected finding(s) reflecting the limitation honestly.

### 6.4 Turn Ceiling Reached
1. A reviewer's run exceeds the configured maximum number of turns.
2. The resulting exception is caught.
3. The Desk reports this review as a clearly labeled **partial review**, showing whatever findings were produced before the ceiling was hit.

### 6.5 Output Guardrail Fires
1. The merged report is assembled and contains something credential-shaped (traced back to the diff).
2. The output guardrail's tripwire fires.
3. The Desk catches this and shows the user a clear **refusal** message instead of the report.
4. Nothing resembling the detected credential is ever displayed, logged, or streamed to the UI at any point after detection.

### 6.6 Missing or Exhausted API Key at Runtime (Post-Build)
1. A user runs the finished application (CLI or Chainlit) without a valid, working Gemini API key configured in `.env`.
2. Per Constitution Section 12 and NFR-1, the application does not attempt a call, does not silently continue, and does not fabricate a review.
3. The user sees a clear, human-readable message — e.g., **"API key required"** — surfaced through the CLI output or the Chainlit UI, as appropriate to how they're interacting with the Desk.

### 6.7 Ruleset File Missing (Required-Tool Edge Case)
1. A review starts for a reviewer that is configured to require the ruleset tool.
2. The ruleset file for the given `ruleset_id` does not exist on disk.
3. The forced ruleset tool call still happens (per FR-9), but returns a plain "ruleset not found" message rather than raising.
4. The review still completes, and the final report/notes make clear that the ruleset could not be consulted for this run.

---

## 7. Summary Traceability Table

| Requirement | Section Above | Core Behavior in One Line |
|---|---|---|
| FR-1 | 3.1 | Diff split by file, before any model call, async entry point |
| FR-2 | 3.2 | `ReviewContext` passed to tools, never appears in prompt text |
| FR-3 | 3.3 | Reviewers return `list[Finding]`; schema wraps it, `final_output` doesn't |
| FR-4 | 3.4 | Instructions built per run from ruleset/language/strictness |
| FR-5 | 3.5 | Three cloned reviewers run concurrently, not sequentially — never cut |
| FR-6 | 3.6 | Merge = tool call (Desk keeps control); Remediation = handoff (control transfers) |
| FR-7 | 3.7 | Cheaper model applied at run level, agent definition untouched |
| FR-8 | 3.8 | Output guardrail refuses reports containing credential-shaped text — never cut |
| FR-9 | 3.9 | Forced ruleset tool, non-raising tool failures, enforced turn ceiling |
| FR-10 | 3.10 | Footer shows real per-reviewer latency/tokens from run hooks; one reviewer also has agent hooks |
| FR-11 | 3.11 | One ledger line per run, via a single centrally-registered custom runner |
| FR-12 | 3.12 | Chainlit streams findings live, session reuses context, always async |
| FR-13 | 3.13 | One trace per review, reviewer spans overlap, slowest reviewer identifiable |
| NFR-1 | 4 | Secrets only in `.env`, clear startup failure, never logged or shown |
| NFR-2 | 4 | Every agent declares model settings; nothing unbounded |
| NFR-3 | 4 | Every review traceable and ledgered |
| NFR-4 | 4 | Tools fail with messages, never raise into the Runner |
| NFR-5 | 4 | Git history proves spec preceded code |

---

## 8. Definition of "Behavior Complete" for This Document

This specification is considered complete and ready to hand to `plan.md` when, for every requirement above, a reader can answer without guessing:

- What the user does to trigger it.
- What the user sees as a result.
- What "correct" looks like versus what a failure/edge case looks like.
- Why the requirement is architected the way it is (where a design reason is called for, e.g., FR-6, FR-8).

All thirteen FRs and five NFRs meet that bar above. Anything not yet at that bar (exact numeric thresholds, file layout, specific library calls) is intentionally deferred to `plan.md` and `tasks.md`, which build on top of this document rather than duplicating it.