# Tasks — 04_Student_Ops_Desk

**Document Type:** Implementation Task List  
**Status:** Binding  
**Version:** 1.0  
**Related Documents:** constitution.md, spec.md, plan.md  

This document breaks the architecture defined in `plan.md` into an ordered sequence of small, independently verifiable implementation tasks.  
Each task names the requirement(s) it satisfies.  
No implementation code may be written until this document (together with the other three Phase 0 documents) has been committed.

---

## Phase 0 Gate (Must be complete before any code)

- [ ] Confirm `constitution.md`, `spec.md`, `plan.md` and `tasks.md` exist and are committed.
- [ ] Verify `git log` shows these four documents committed before any `.py` or other source file.
- **Satisfies:** NFR-5, Constitution §2

---

## 1. Project Skeleton & Secrets

### Task 1.1 — Project structure

- Create the folder layout inside `04_Student_Ops_Desk` only.
- Add `.gitignore` that includes `.env`, virtual-environment folders, and common Python artefacts.
- **Satisfies:** Constitution §1 (Scope Boundary), NFR-1

### Task 1.2 — Environment & secrets

- Create `.env.example` (no real secrets).
- Ensure the real `.env` is gitignored.
- Implement early, clear startup failure when a required key is missing.
- **Satisfies:** NFR-1, Constitution §4

### Task 1.3 — Async entry point

- Create the main asynchronous entry point driven by `asyncio.run`.
- **Satisfies:** FR-1, Constitution §3

---

## 2. Core Data Structures

### Task 2.1 — StudentProfile

- Implement the `StudentProfile` dataclass exactly as specified.
- Ensure it is passed only as local context.
- **Satisfies:** FR-3, Constitution §5

### Task 2.2 — Ticket model

- Implement the Pydantic `Ticket` model with the exact fields:
  `category`, `summary`, `next_step`, `resolved`, `escalate`.
- **Satisfies:** FR-7, FR-7A

### Task 2.3 — TimelineEntry

- Implement the `TimelineEntry` dataclass for the durable audit log.
- **Satisfies:** FR-10, NFR-3, Plan §3.4

### Task 2.4 — courses.json

- Create `courses.json` with at least one realistic course containing schedule, policies and assignments.
- **Satisfies:** FR-2

---

## 3. Tools (never raise)

### Task 3.1 — Course-data tools

- Implement `list_courses`, `get_course`, `get_assignment`.
- All failures return clear natural-language sentences; no exceptions propagate.
- **Satisfies:** FR-2, NFR-4, Constitution §6

### Task 3.2 — close_ticket tool

- Implement `close_ticket` so that calling it immediately ends the run and its output becomes the final result.
- **Satisfies:** FR-9, Constitution §6

### Task 3.3 — Tier-gated tool

- Implement `get_scholarship_resources`.
- Offer it only when `StudentProfile.tier == "scholarship"`; for all other students the tool must be completely absent from the tool list.
- **Satisfies:** FR-9, Constitution §6, Plan §4.3

---

## 4. Dynamic Instructions & Context

### Task 4.1 — Dynamic system-prompt builder

- Build the Desk system prompt at request time from the current `StudentProfile`.
- Must greet by name, name the course, and become terser when `open_tickets >= 3`.
- Make the fully resolved prompt printable/loggable before any model call.
- **Satisfies:** FR-4, Constitution §5

### Task 4.2 — Local-context injection

- Ensure `StudentProfile` is injected as local context on every run.
- Verify that profile-reading tools have no wrapper parameter in their schema.
- **Satisfies:** FR-3

---

## 5. Core Desk Agent (FR-1)

### Task 5.1 — Desk agent configuration

- Create the Desk agent with `gemini-2.5-flash` configured at the agent level.
- Confirm no `set_default_openai_client` (or equivalent) appears anywhere.
- **Satisfies:** FR-1, NFR-2, Constitution §3

### Task 5.2 — Desk with tools and structured output

- Attach course-data tools, `close_ticket`, tier-gated tool and Summariser tool to the Desk.
- Configure the Desk to produce a typed `Ticket` as final output.
- Add a minimal terminal loop (read question → print answer/Ticket) so FR-1's done-when is demonstrable in the terminal before the Chainlit interface exists.
- **Satisfies:** FR-1, FR-2, FR-7, FR-9

---

## 6. Specialists & Handoffs

### Task 6.1 — Base specialist agent

- Define a single base specialist agent that carries the shared model configuration.
- **Satisfies:** FR-5, Constitution §7

### Task 6.2 — Assignments Specialist

- Clone the base agent.
- Set temperature 0.2 and cold/factual instructions.
- Do not re-declare the model.
- **Satisfies:** FR-5, Plan §2.3

### Task 6.3 — Careers Specialist

- Clone the base agent.
- Set temperature 0.7 and warmer instructions.
- Do not re-declare the model.
- **Satisfies:** FR-5, Plan §2.4

### Task 6.4 — Wire handoffs

- Make the Desk able to hand off to Assignments or Careers.
- After handoff the specialist (not the Desk) answers the student.
- Ensure the handoff appears in the run items and the answering agent is identifiable.
- **Satisfies:** FR-5, Constitution §7

### Task 6.5 — Summariser agent wired as tool

- Implement the Summariser specialist and expose it to the Desk as a tool (not a handoff).
- After it returns, the Desk still produces the final message.
- **Satisfies:** FR-6

---

## 7. Guardrail

### Task 7.1 — Input guardrail

- Implement an input guardrail that rejects non-bootcamp questions before the Desk model is called.
- Catch the tripwire, return a polite plain-text refusal, and never construct a Ticket.
- Confirm zero cost at the Desk model for refused questions.
- **Satisfies:** FR-8, FR-8A, Constitution §9

---

## 8. Turn Ceiling & Termination Paths

### Task 8.1 — Turn ceiling

- Set the hard turn ceiling to 10.
- On exhaustion: catch the exception and still produce a Ticket with `escalate: true`.
- **Satisfies:** FR-9, FR-7A, NFR-2, Plan §9

### Task 8.2 — Escalation logic

- Implement the three triggers that set `escalate: true`:
  1. Unanswerable from `courses.json`
  2. Turn-ceiling reached
  3. Student explicitly requests a human
- **Satisfies:** FR-7A

---

## 9. Observability

### Task 9.1 — Run-level hooks

- Attach run-level hooks that record an ordered `TimelineEntry` sequence for every agent and handoff.
- Persist the timeline to a durable location (JSONL file or database).
- **Satisfies:** FR-10, NFR-3

### Task 9.2 — Agent-level hooks

- Attach agent-level hooks to exactly one specialist.
- Confirm they become silent at the moment of a handoff and that this behaviour is explainable.
- **Satisfies:** FR-10, Constitution §10

### Task 9.3 — Custom runner

- Implement a custom runner that stamps `request_id` and elapsed time.
- Register it once at startup.
- Ensure no agent definition mentions it.
- Confirm it wraps every run, including guardrail-terminated runs.
- **Satisfies:** FR-11, Plan §1 & §8.3

### Task 9.4 — Tracing

- Enable tracing under the project’s own key.
- Ensure one student conversation appears as one coherent trace.
- **Satisfies:** FR-13, Constitution §10

---

## 10. Category Routing (Admin path)

### Task 10.1 — Admin ownership

- Ensure purely administrative questions (schedules, general policies) are answered by the Desk using course-data tools with no handoff.
- Resulting Ticket must carry `category: "admin"`.
- **Satisfies:** Spec §2.2A, Key Behavioural Guarantee 13

---

## 11. Chainlit Interface

### Task 11.1 — Session setup

- On session open, create the agent instance and `StudentProfile` once.
- Do not recreate them on every message.
- **Satisfies:** FR-12, Constitution §11

### Task 11.2 — Memory & isolation

- Maintain conversation memory within the session.
- Ensure two browser windows do not share history.
- **Satisfies:** FR-12

### Task 11.3 — Async handler

- Make the message handler `await` the asynchronous runner.
- Forbid the synchronous variant.
- **Satisfies:** FR-12, Constitution §11

---

## 12. Final Verification Checklist

### Task 12.1 — End-to-end behavioural tests

Demonstrate on demand:

- [ ] Off-topic question → polite refusal, zero Desk-model cost, no Ticket (FR-8, FR-8A)
- [ ] Delete a course from `courses.json` → Desk stops answering about it (FR-2)
- [ ] Three different profiles → three different resolved prompts (FR-4)
- [ ] Assignment question → handoff to Assignments Specialist (FR-5)
- [ ] Career question → handoff to Careers Specialist (FR-5)
- [ ] Long policy → Summariser tool used, Desk still speaks final message (FR-6)
- [ ] Resolved conversation → `type(result.final_output) is Ticket` (FR-7)
- [ ] Unanswerable / turn-ceiling → Ticket with `escalate: true` (FR-7A)
- [ ] Regular vs scholarship → different tool sets offered (FR-9)
- [ ] One question → one ordered audit timeline + one coherent trace (FR-10, FR-13)
- [ ] Custom runner output visible for Desk and specialist runs (FR-11)
- [ ] Chainlit: second message understood, sessions isolated (FR-12)
- [ ] Fully resolved prompt printable before model call (FR-4)
- [ ] `git log` shows Phase 0 documents before any source file (NFR-5)
- [ ] Malformed output request → SDK parsing error surfaced, no half-filled Ticket (FR-7)
- [ ] resolved field branched on in real Python if logic (FR-7)
- [ ] Grep source for student name → only at StudentProfile construction (FR-3)
- [ ] Profile-reading tool schema has no wrapper parameter (FR-3)

---

## Cut Order (only if time forces cuts)

If features must be dropped, cut strictly in this order:

1. FR-11 (Custom Runner)
2. FR-6 (Summariser-as-tool)
3. AgentHooks half of FR-10

**Never cut FR-7 or FR-8.**

---

**End of Tasks**