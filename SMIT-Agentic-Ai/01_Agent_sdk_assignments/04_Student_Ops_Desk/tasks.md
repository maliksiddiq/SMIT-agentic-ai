



# Specification — 04_Student_Ops_Desk
**Document Type:** Behavioural Specification
**Status:** Binding
**Version:** 1.0
**Related Documents:** constitution.md, plan.md, tasks.md

This document is the authoritative description of **what** the system must do.
It defines observable behaviour, inputs, outputs, constraints, and precise acceptance criteria.
It deliberately does **not** prescribe implementation details, file structure, class names, or library choices.
Those belong in `plan.md` and the eventual source code.
Any implementation that fails to produce the behaviours described in this document is incomplete — even if the code is elegant, even if unit tests pass, and even if a coding agent generated it.

---

## 1. Project Overview

### 1.1 Purpose

04_Student_Ops_Desk is the single front door for all student questions related to the bootcamp.
A student asks a question in ordinary natural language. The system must:

- Decide whether the question is about an assignment, a career matter, or course administration.
- Answer the question using only real, authoritative course data.
- Route the conversation to the correct specialist when the question requires specialised handling.
- Refuse any question that is not related to the bootcamp.
- Close every successfully resolved conversation by emitting a structured, typed ticket that downstream systems could file.

The system is not a general-purpose chatbot. It is a constrained, auditable, course-aware operations desk.

### 1.2 Core Behavioural Loop

The following sequence must occur for every student interaction:

1. The student submits a natural-language question.
2. An input guardrail evaluates whether the question belongs to the bootcamp domain.
3. If the question is off-topic, the system issues a polite refusal and the Desk model is never invoked (zero cost). **No Ticket is produced for this path** (see FR-8 and FR-8A below).
4. If the question is on-topic, the student's profile is supplied as local context and a dynamic system prompt is constructed from that profile.
5. The Desk may:
   - Call tools to retrieve course data,
   - Answer directly using course-data tools when the question is a general administrative matter belonging to no specialist domain (see §3.2A),
   - Hand the conversation off to a specialist agent, or
   - Call a specialist that has been exposed as a tool.
6. When the conversation reaches a terminal state — resolved or not — the system produces a typed Ticket object (see §3.7A).
7. The entire run is fully traceable and produces an ordered audit timeline.

This loop is the heart of the product. Every functional requirement exists to support one or more steps of this loop.

### 1.3 Explicit Non-Goals

The system is explicitly forbidden from doing the following three things:

1. **Answering off-topic questions**  
   Questions about weather, politics, general knowledge, personal life advice unrelated to the bootcamp career path, or any other non-course subject must be refused. The system must not attempt to be helpful on these topics.
2. **Inventing course data**  
   The system must never fabricate course identifiers, assignment identifiers, schedules, due dates, policies, or any other factual course information that does not exist in the authoritative data source.
3. **Embedding raw student identity in the prompt**  
   The student's name, roll number, or tier must never appear as free-form text inside the system prompt. Student identity may reach the model only through deliberately constructed dynamic instructions or through tools that read local context.

These three non-goals are absolute. Violating any of them is a failure of the specification.

---

## 2. Actors and Context

### 2.1 Primary Actor — Student

The only primary actor is the student.
A student is a human who asks questions about the bootcamp.
The student is never identified by free-form text inside prompts.
The student is identified solely by a structured profile object that is supplied as local context on every run.

### 2.2 StudentProfile

Every run of the system receives a StudentProfile.
This profile is the single source of truth for student-specific information.

The profile must contain at least the following fields:

- `name` (string) — the student's display name
- `roll_no` (string) — the student's unique roll number
- `course_id` (string) — the identifier of the course the student is enrolled in
- `tier` (string) — either `"regular"` or `"scholarship"`
- `open_tickets` (integer) — the number of currently open tickets for this student

**Rules governing the profile:**

- The profile is passed into every run as **local context**.
- Tools that need student information must read it from this local context.
- The profile must never be serialised as free text into the system prompt.
- The only permitted ways for student data to influence the model are:
  1. Dynamic instructions that are deliberately written to incorporate selected fields, and
  2. Tools that read the profile from local context at runtime.

If a concrete student name, roll number, or tier value can be found anywhere in the source code except at the single site where the StudentProfile object is constructed, the implementation violates this specification.

### 2.2A Category Ownership

Every question the Desk receives must resolve to exactly one of the three Ticket categories — `"assignment"`, `"career"`, or `"admin"` — and each category has exactly one owner:

| Category     | Owner                  | Mechanism                                                    |
| ------------ | ---------------------- | ------------------------------------------------------------ |
| `assignment` | Assignments Specialist | Handoff (FR-5)                                               |
| `career`     | Careers Specialist     | Handoff (FR-5)                                               |
| `admin`      | The Desk itself        | Direct tool calls against `courses.json` (FR-2) — no handoff |

**Required Behaviour**

Questions about course schedules, general enrolment policies, or any administrative matter not tied to a specific assignment or to career guidance are answered by the Desk directly, using its own course-data tools (FR-2). These questions are never handed off to the Assignments or Careers specialist, and the Summariser tool may still be used to compress a long policy answer before the Desk replies.

**Acceptance Criteria**

- A purely administrative question (for example, "What are the batch timings for agentic-ai-w4?") is answered without any handoff event appearing in the run's items.
- The resulting Ticket for such a question carries `category: "admin"`.

**Rationale**

Without an explicit owner, "admin" would be an orphaned category that no component is responsible for, and the routing logic would be ambiguous by construction. Naming the Desk as the direct owner keeps the three-way category split total and unambiguous.

---

## 3. Functional Requirements

### FR-1 — Gemini-backed Desk Agent

**Required Behaviour**

The central conversational agent (the Desk) must be powered by the model `gemini-3.6-flash`.
The model must be reached through an OpenAI-compatible client.
The model configuration must be attached directly to the agent instance itself; it must not be set globally and must not be set on a per-run basis.
The program's entry point must be an asynchronous function that is launched with `asyncio.run`.

**Acceptance Criteria**

- When a question is typed into the terminal interface, the response is generated by Gemini.
- A search of the entire codebase finds no occurrence of any global default-client setter (including but not limited to `set_default_openai_client`).
- The main entry point of the program is an `async` function.

**Rationale**

This requirement establishes the foundational runtime and model configuration style for the entire system. All later requirements build on a correctly configured, agent-level, asynchronous Desk.

---

### FR-2 — Course Knowledge Accessible Only Through Tools

**Required Behaviour**

All authoritative information about courses, schedules, policies, and assignments lives in a single structured data file named `courses.json`.
The Desk and every specialist may obtain this information **only** by calling tools.
Direct embedding of course data into prompts or instructions is forbidden.
The system must never invent data that is absent from the file.

**Minimum Tool Capabilities**

The system must provide at least the following tool behaviours:

- List all available courses.
- Retrieve the schedule and policies of a specific course.
- Look up a single assignment by its unique identifier.

**Acceptance Criteria**

- If a course is deleted from `courses.json`, the Desk immediately stops answering questions about that course. No code change is required.
- If a student asks about an assignment identifier that does not exist in the file, the system declines the request. It never fabricates an answer.

**Rationale**

This requirement enforces a clean separation between knowledge and reasoning. The model is not allowed to "know" course facts; it is only allowed to retrieve them.

---

### FR-3 — Student Identity Lives Exclusively in Local Context

**Required Behaviour**

The StudentProfile is supplied to every run as local context.
Any tool that needs student information must read it from that context.
The system prompt itself must never contain the student's name, roll number, or tier as free-form text.

**Acceptance Criteria**

- The JSON schema (or equivalent) generated for any tool that reads the profile contains no wrapper parameter whose purpose is to receive the profile.
- A full-text search of the source code for a concrete student name returns a match only at the location where the StudentProfile object is instantiated.

**Rationale**

This requirement protects student privacy and forces correct use of the local-context mechanism. It also makes the system auditable: student identity cannot leak into prompts accidentally.

---

### FR-4 — Dynamic System Prompt Constructed Per Request

**Required Behaviour**

The Desk's system prompt is not a static string.
It is constructed at the moment of each request, using the current StudentProfile as input.

At minimum the constructed prompt must:

- Greet the student by name.
- Explicitly name the course in which the student is enrolled.
- Become noticeably shorter and more concise when the student's `open_tickets` value is 3 or greater.

**Acceptance Criteria**

- Supplying three different StudentProfile instances produces three system prompts that are visibly different from one another.
- It is possible to print or log the fully resolved system prompt **before** any call to the model is made.

**Rationale**

Dynamic instructions demonstrate that the system can adapt its behaviour to the individual student without violating the rule against embedding raw identity in the prompt.

---

### FR-5 — Two Specialist Agents Reached by Handoff

**Required Behaviour**

Two specialist agents exist:

- Assignments Specialist — handles questions about deadlines, submission rules, and assignment content. Its tone is cold and factual.
- Careers Specialist — handles questions about career paths, skill development, and professional guidance related to the bootcamp. Its tone is warmer.

Both specialists are created by cloning a single base agent.
They may differ only in their instructions and their model settings.
The model configuration of the base agent is shared; it is not restated on the specialists.
When the Desk decides that a question belongs to one of these domains, it performs a handoff.
After the handoff, the specialist (not the Desk) is responsible for producing the answer to the student.

**Acceptance Criteria**

- After a run completes, it is possible to determine from the run result which agent produced the final answer.
- The handoff event is visible in the run's items.
- Both specialists inherit the base agent's model without re-declaring it.
- The differing model settings of each specialist can be named and justified as deliberate choices, not defaults left by accident.

**Rationale**

Handoffs demonstrate multi-agent collaboration. The cloning requirement ensures that configuration remains consistent and that specialisation is achieved only through instructions and settings.

---

### FR-6 — One Specialist Exposed as a Tool

**Required Behaviour**

A third specialist, the Summariser, exists.
Its sole job is to take a long policy answer and reduce it to three concise lines.

Unlike the Assignments and Careers specialists, the Summariser is **not** reached by handoff.
It is exposed to the Desk as a tool.
Because it is a tool, the Desk remains in control of the conversation.
After the Summariser returns its result, the Desk itself produces the final message that the student sees.

**Acceptance Criteria**

- It is possible to articulate a clear design reason why the Summariser is a tool while the other two specialists are handoffs.
- After the Summariser has been used, the final message delivered to the student still originates from the Desk.

**Rationale**

This requirement forces a deliberate architectural choice between handoff and tool-calling, and demonstrates that the designer understands the difference in control flow and voice ownership.

---

### FR-7 — Structured Ticket Produced on Every Resolved Conversation

**Required Behaviour**

When a conversation reaches a successful resolution, the system's final output must be a typed Ticket object, not free-form prose and not a plain dictionary.

The Ticket must contain at least the following fields:

- `category` — one of the literal values `"assignment"`, `"career"`, or `"admin"`
- `summary` — a short textual summary of the issue
- `next_step` — the recommended next action
- `resolved` — a boolean indicating whether the issue is considered resolved
- `escalate` — a boolean indicating whether human escalation is required

**Acceptance Criteria**

- Evaluating `type(result.final_output) is Ticket` returns `True`.
- The `resolved` field is consumed by real program logic (for example, an `if` statement that branches on its value).
- When a deliberately impossible or malformed request is made, the system surfaces the official structured-output parsing error from the underlying SDK. It does not silently return a partially filled or invalid object.

**Rationale**

A typed ticket is the contract between the conversational system and any downstream ticketing or analytics system. Free-form text cannot fulfil that contract.

---

### FR-7A — Ticket Production on Unresolved and Escalated Conversations

**Required Behaviour**

A Ticket is produced for **every** conversation that reaches the Desk's terminal state — via `close_ticket` (FR-9) or via the turn ceiling being reached (FR-9) — regardless of whether the underlying issue was actually solved. An unresolved outcome is not the absence of a Ticket; it is a Ticket whose fields say so.

Specifically:

- `resolved: false` combined with `escalate: true` is a valid, complete Ticket, not a failure state and not an exception.
- `escalate` must be set to `true` whenever any of the following is true:
  - The Desk and its specialists cannot answer the question using the tools and data available to them (for example, the student asks about a policy that does not exist in `courses.json`).
  - The turn ceiling defined in FR-9 is reached before the conversation naturally concludes.
  - The student explicitly asks to speak to a human or states that the automated answer is not sufficient.
- `escalate` must be `false` whenever the question was fully answered from authoritative course data and no human follow-up is required.

**Acceptance Criteria**

- A question that cannot be answered from `courses.json` (for example, an assignment id that does not exist) still produces a Ticket, with `resolved: false` and `escalate: true`, rather than an error or a bare refusal.
- A run that is terminated by the turn ceiling produces a Ticket with `escalate: true`, generated by the exception-handling path described in FR-9, not by the normal `close_ticket` path.
- It is possible to point to the specific condition in the code that sets `escalate` to `true` for each of the three triggers listed above.

**Rationale**

FR-7 alone only describes the "success" path. Because `Ticket.escalate` exists as a field, the specification must define when it is used — otherwise it is decoration with no defined behaviour, and the viva question "does an unresolved conversation still produce a ticket?" has no answer in this document.

---

### FR-8 — Input Guardrail That Rejects Off-Topic Questions

**Required Behaviour**

Before the Desk model is ever called, an input guardrail examines the student's question.
If the question is not related to the bootcamp, the guardrail rejects it.
The program must catch the rejection and respond to the student with a polite refusal.
The program must not crash.
The Desk model must never be invoked for a rejected question.

**Acceptance Criteria**

- An obviously off-topic question (for example, "What is the weather in Karachi today?") produces a courteous refusal.
- Inspection of the trace proves that the Desk model was not called for that question (zero cost).
- The process remains running after the refusal.
- The exact location in the program where the guardrail's tripwire exception is caught can be pointed out on demand.

**Rationale**

The guardrail is the primary cost-control and safety mechanism. It must operate before any expensive model call.

---

### FR-8A — No Ticket Is Produced on Guardrail Refusal

**Required Behaviour**

A guardrail refusal is a distinct terminal path from a resolved or escalated conversation. When the input guardrail's tripwire fires:

- No Ticket object of any kind is constructed — not a resolved one, not an unresolved one, not an escalated one.
- The run terminates at the guardrail layer, before the Desk agent, any specialist, or any Ticket-producing logic is ever reached.
- The polite refusal message returned to the student is plain text, not a typed object, since a refusal was never an operation the course-ops ticketing system needs to file.

**Acceptance Criteria**

- After an off-topic question is refused, inspecting the program's return value shows plain text or an explicit "refused" marker — never `type(result) is Ticket`.
- A search of the guardrail-handling code path shows no call into the Ticket-construction logic.

**Rationale**

Key Behavioural Guarantee #7 in the original specification already implies this ("every *successfully resolved* conversation ends with a Ticket") but never states it directly for the refusal case, leaving an ambiguity that a viva examiner is likely to probe. This requirement closes that gap explicitly, and keeps FR-7A's expanded Ticket-on-every-terminal-state rule from being misread as "even a refusal gets a Ticket."

---

### FR-9 — Tool Gating, Stopping Rule, and Turn Ceiling

**Required Behaviour**

Three independent control mechanisms must be present:

1. **Tier-based tool gating**  
   At least one tool is available only to students whose tier is `"scholarship"`.  
   For every other student that tool is completely absent from the list of tools offered to the model.  
   It is not sufficient to offer the tool and then refuse its use; the tool must not appear at all.

2. **Stopping rule**  
   A tool named `close_ticket` exists.  
   When this tool is called, the run terminates immediately and the tool's output becomes the final result of the run.

3. **Turn ceiling**  
   Every run is subject to a hard maximum number of turns.  
   If the ceiling is exceeded, an exception is raised, caught, and reported cleanly.  
   Infinite or unbounded generation is forbidden.  
   Per FR-7A, the exception handler for this case must still surface a Ticket, with `escalate: true`, rather than a bare error to the student.

**Acceptance Criteria**

- Running the identical question once with a `"regular"` profile and once with a `"scholarship"` profile results in two different sets of tools being presented to the model.
- The numeric value of the turn ceiling is known and can be justified.
- Invoking `close_ticket` ends the run.
- Deliberately exceeding the turn ceiling results in a caught exception and a Ticket with `escalate: true`, not an unhandled crash.

**Rationale**

These three controls together prevent runaway cost, enforce policy differences by student tier, and give the system a clean termination path.

---

### FR-10 — Audit Trail and Selective Agent-Level Hooks

**Required Behaviour**

Run-level hooks record an ordered timeline of the entire conversation.
The timeline must include every agent that participated and must record handoff events.
Independently, agent-level hooks are attached to **exactly one** specialist (no more, no less).

**Acceptance Criteria**

- A single student question produces one timeline that lists the participating agents in the order they ran.
- It is possible to explain, from the observed behaviour, why the agent-level hooks stop receiving events at the moment a handoff occurs.

**Rationale**

Observability is a first-class requirement. The combination of run-level and agent-level hooks demonstrates that the system can be audited both broadly and deeply.

---

### FR-11 — Custom Runner

**Required Behaviour**

A custom runner wraps every run that occurs in the process.
The wrapper stamps a unique request identifier and records the elapsed wall-clock time of the run.
The custom runner is registered once, at application startup.
No agent definition is modified in order to support the runner.

**Acceptance Criteria**

- The request identifier and elapsed time appear in the output of both the Desk's run and any specialist's run.
- A search of all agent definition files finds no reference to the custom runner.

**Rationale**

The custom runner provides process-level observability that agent-level and run-level hooks cannot supply. Keeping agent definitions unaware of the runner preserves clean separation of concerns.

---

### FR-12 — Browser Interface with Per-Session Memory

**Required Behaviour**

The Desk is usable through a browser-based chat interface.
When a new browser session begins, the agent instance and the StudentProfile are created once.
They are not recreated on every subsequent message.
The conversation retains memory of earlier turns within the same session.
Two different browser windows or sessions must not share conversation history.
The message handler in the interface must await the asynchronous runner; the synchronous variant must not be used.

**Acceptance Criteria**

- A second message that refers to information given in the first message is correctly understood.
- Opening the interface in two separate browser windows produces two completely isolated conversations.
- The handler that processes incoming messages uses `await` with the asynchronous runner.

**Rationale**

A terminal-only system is insufficient for real student use. Session isolation and proper asynchronous handling are mandatory for a correct multi-user interface.

---

### FR-13 — Fully Traceable Conversations

**Required Behaviour**

Tracing is enabled for every conversation.
Traces are exported under a key that belongs to the project (default or shared keys are forbidden).
A single student conversation must appear as one coherent trace, not as multiple disconnected traces.

**Acceptance Criteria**

- It is possible to open the produced trace, name every span that appears inside it, and identify at least one model or tool call that the Desk made which was not strictly necessary for answering the question.

**Rationale**

Traceability is required both for debugging and for the final viva. An owner who cannot explain the spans in a trace has not finished the requirement.

---

## 4. Non-Functional Requirements

### NFR-1 — Secrets Management

**Required Behaviour**

All secret values (API keys, tracing keys, etc.) live exclusively in a `.env` file.
That file is listed in `.gitignore` and is never committed.
If a required key is missing at startup, the program fails immediately with a clear, human-readable error message. A deep stack trace is not acceptable.

**Acceptance Criteria**

- Deleting or renaming `.env` and starting the program produces a single, human-readable message naming the missing key, not a Python traceback.
- Running `git log --all --full-history -- .env` on the repository returns no results.

---

### NFR-2 — Cost Control

**Required Behaviour**

Every agent declares its own model settings.
No agent is permitted to generate text without a declared ceiling (turn limit or equivalent hard stop).

**Acceptance Criteria**

- Every agent's effective model settings can be traced to an explicit declaration in the codebase — either in its own definition or, for cloned specialists, in the base agent from which it was cloned. No agent relies on an undeclared default that was never set anywhere.
- Every entry point into a run passes an explicit turn-ceiling value; none call the runner with an implicit or unbounded configuration.

---

### NFR-3 — Observability

**Required Behaviour**

Every conversation is fully traceable.
In addition, the ordered audit timeline produced by the run-level hooks is written to a durable location (file or database). Printing the timeline only to the console does not satisfy this requirement.

**Acceptance Criteria**

- After a conversation ends, the audit timeline for that run can be retrieved from disk or a database without re-running the conversation.
- Restarting the process does not erase previously written timelines.

---

### NFR-4 — Failure Behaviour of Tools

**Required Behaviour**

When a tool receives invalid or missing data, it returns a clear natural-language sentence that the model can understand and act upon.
A tool that allows an exception to propagate into the runner is considered defective.

**Acceptance Criteria**

- Calling a course-data tool with a non-existent course id or assignment id returns a descriptive string (e.g. "No assignment with id X exists for this course") rather than raising `KeyError`, `IndexError`, or any other unhandled exception.
- A deliberately malformed tool call does not appear as an unhandled exception anywhere in the trace or the process logs.

---

### NFR-5 — Provenance of the Specification

**Required Behaviour**

The Git history of the repository must demonstrate that the four Phase 0 documents (`constitution.md`, `spec.md`, `plan.md`, `tasks.md`) were committed before any implementation source file.

**Acceptance Criteria**

- `git log --diff-filter=A --name-only` shows the four Phase 0 documents added in commits that precede, chronologically, the first commit that adds a `.py` (or other source) file.
- No single commit in the history contains both a Phase 0 document and an implementation source file added for the first time.

---

## 5. Key Behavioural Guarantees

The following properties must be observably true in a running system:

1. An off-topic question is refused before the Desk model is called and incurs zero cost at that model.
2. Changing the contents of `courses.json` changes the Desk's answers without any code modification.
3. A student's name, roll number, or tier never appears as free text inside a system prompt.
4. Different StudentProfile instances produce visibly different system prompts.
5. After a handoff, the specialist (not the Desk) produces the answer that reaches the student.
6. After the Summariser tool is used, the Desk still produces the final message.
7. Every conversation that reaches a terminal state inside the Desk (resolved, unresolved, or escalated) ends with a value whose type is exactly `Ticket`; a conversation that is refused by the guardrail before reaching the Desk ends with plain text and never a `Ticket`.
8. The `resolved` field of the Ticket is read by program logic, not merely displayed.
9. The set of tools offered to the model differs according to the student's tier.
10. Every conversation produces both one ordered audit timeline and one coherent trace.
11. The fully resolved system prompt can be inspected before the model is invoked.
12. Every run is wrapped by a custom runner that records a request identifier and elapsed time, and no agent definition knows about that runner.
13. Every administrative (non-assignment, non-career) question is answered directly by the Desk using course-data tools, with no handoff event in the run's items.
14. `escalate: true` on a Ticket always traces back to one of exactly three causes: unanswerable question, turn-ceiling exhaustion, or explicit student request for human help.

---

## 6. Definition of Done

A functional or non-functional requirement is considered done **only** when its stated acceptance criteria can be demonstrated on demand in a live run.
Claims such as "the code looks correct" or "it should work" are insufficient.
The behaviour must be observable.

---

## 7. Document Authority

This specification, together with the constitution, constitutes the complete and binding description of required system behaviour.

- If an implementation contradicts this document, the implementation is wrong.
- If this document is silent on a point, the prohibitions and rules in the constitution still apply.
- No later document (including `plan.md` or source code) may weaken or override the behaviours defined here.

---

## 8. Requirements Traceability Matrix

This table maps every functional and non-functional requirement to the architectural concept it exercises, so that `plan.md` can be written directly against it without re-deriving the mapping.

| Requirement  | Concept Exercised                              | Primary Architectural Component                    |
| ------------ | ---------------------------------------------- | -------------------------------------------------- |
| FR-1         | Agent-level model configuration, async runtime | Desk agent, entry point                            |
| FR-2         | Tool-mediated knowledge access                 | `courses.json` + course-data tools                 |
| FR-3         | Local context                                  | StudentProfile, RunContext                         |
| FR-4         | Dynamic instructions                           | Desk system-prompt builder                         |
| FR-5         | Cloning, handoffs, model settings              | Assignments/Careers specialists                    |
| FR-6         | Agents-as-tools                                | Summariser                                         |
| FR-7 / FR-7A | Structured output                              | `Ticket` model                                     |
| FR-8 / FR-8A | Guardrails                                     | Input guardrail on the Desk                        |
| FR-9         | Tool gating, stopping rule, turn ceiling       | Tool list construction, `close_ticket`, run config |
| FR-10        | Lifecycle hooks (run-level and agent-level)    | RunHooks, AgentHooks                               |
| FR-11        | Custom runners                                 | Runner subclass                                    |
| FR-12        | Session-scoped state, async handlers           | Chainlit interface                                 |
| FR-13        | Tracing                                        | Trace/span configuration                           |
| NFR-1        | Secrets management                             | `.env`, startup validation                         |
| NFR-2        | Cost ceilings                                  | Per-agent model settings, turn limits              |
| NFR-3        | Durable observability                          | Timeline persistence layer                         |
| NFR-4        | Defensive tool design                          | Tool error handling                                |
| NFR-5        | Spec-before-code provenance                    | Git history                                        |

---
