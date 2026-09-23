# Plan — 04_Student_Ops_Desk

**Document Type:** Architectural Plan  
**Status:** Binding  
**Version:** 1.0  
**Related Documents:** constitution.md, spec.md, tasks.md  

This document describes **how** the system will be structured to satisfy the behaviours defined in `spec.md` while obeying every rule in `constitution.md`.  

It defines the agents, their relationships, the tools, the data structures that cross boundaries, the control flow, and the observability mechanisms.  

It does **not** contain implementation code. It is the blueprint that `tasks.md` will break into ordered, verifiable work items.

---

## 1. High-Level Architecture

The system is organised as a multi-agent operations desk with a clear separation of concerns:

```
Student
   │
   ▼
┌─────────────────────┐
│  Input Guardrail    │  ← rejects off-topic before any model cost
└──────────┬──────────┘
           │ (only if on-topic)
           ▼
┌─────────────────────┐
│   Custom Runner     │  ← stamps request_id + elapsed time
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│       Desk          │  ← owns the conversation, builds dynamic prompt,
│  (Primary Agent)    │     decides routing, produces final Ticket
└──────────┬──────────┘
           │
     ┌─────┴──────────────────────────────┐
     │                                    │
     ▼                                    ▼
┌─────────────┐                  ┌─────────────────┐
│  Tools      │                  │  Specialists    │
│             │                  │                 │
│ • list_     │                  │ • Assignments   │ ← handoff
│   courses   │                  │ • Careers       │ ← handoff
│ • get_      │                  │ • Summariser    │ ← tool
│   course    │                  │                 │
│ • get_      │                  └─────────────────┘
│   assignment│
│ • close_    │
│   ticket    │
│ • (tier-    │
│   gated)    │
└─────────────┘
```

**Key principles enforced by this architecture:**

- The Desk always owns the final voice except when a true handoff occurs.
- Course knowledge is reached only through tools.
- Student identity never appears as free text in prompts.
- Every terminal state inside the Desk produces a typed Ticket.
- Off-topic questions never reach the Desk model and never produce a Ticket.
- The custom runner is the outermost wrapper: it wraps every run invocation, including runs that terminate at the guardrail.

---

## 2. Agents

### 2.1 Desk (Primary Agent)

- **Role:** Owns the conversation. Receives the student question, builds the dynamic system prompt, decides whether to answer directly, call tools, hand off, or use the Summariser tool, and is responsible for producing the final Ticket.
- **Model:** `gemini-2.5-flash`, configured at the agent level.
- **Instructions:** Dynamically constructed at request time from the current `StudentProfile` (see Section 5).
- **Tools available to Desk:**
  - Course-data tools (`list_courses`, `get_course`, `get_assignment`)
  - `close_ticket`
  - Tier-gated tool (only for scholarship students)
  - Summariser (exposed as a tool)
- **Handoffs available to Desk:**
  - Assignments Specialist
  - Careers Specialist
- **Output type:** `Ticket` (structured output)

### 2.2 Base Specialist Agent

A single base agent is defined once.  
Both Assignments and Careers specialists are created by cloning this base agent.  

The base agent carries the shared model configuration (`gemini-2.5-flash`).  
Specialists do not re-declare the model; they only override instructions and any deliberate model-settings differences.

### 2.3 Assignments Specialist

- **Created by:** Cloning the base specialist agent.
- **Tone:** Cold and factual.
- **Domain:** Assignment deadlines, submission rules, late policies, assignment content.
- **Reached by:** Handoff from the Desk.
- **After handoff:** This specialist (not the Desk) produces the answer that reaches the student.
- **Model settings:** temperature 0.2 — deliberately low, because assignment deadline and policy answers must be deterministic and factual. The model itself (gemini-2.5-flash) is inherited from the base agent, not re-declared.

### 2.4 Careers Specialist

- **Created by:** Cloning the base specialist agent.
- **Tone:** Warmer.
- **Domain:** Career paths, skill development, professional guidance related to the bootcamp.
- **Reached by:** Handoff from the Desk.
- **After handoff:** This specialist produces the answer.
- **Model settings:** temperature 0.7 — deliberately higher, because career guidance benefits from a warmer, more varied tone. The model itself (gemini-2.5-flash) is inherited from the base agent, not re-declared.

### 2.5 Summariser

- **Role:** Condenses a long policy answer into exactly three concise lines.
- **Exposure:** Exposed to the Desk **as a tool**, not as a handoff.
- **Control flow:** Desk calls the Summariser tool → receives the three-line summary → Desk itself speaks the final message to the student.
- **Rationale for tool (not handoff):** The Desk must retain ownership of the conversational voice after summarisation.

---

## 3. Data Structures Crossing Boundaries

### 3.1 StudentProfile

```python
@dataclass
class StudentProfile:
    name: str
    roll_no: str
    course_id: str
    tier: str = "regular"          # "regular" | "scholarship"
    open_tickets: int = 0
```

- Passed to every run as **local context**.
- Never serialised as free text into any system prompt.
- Tools that need student data read it from local context.
- The generated schema of any profile-reading tool must contain no wrapper parameter for this object.

### 3.2 Ticket

```python
class Ticket(BaseModel):
    category: Literal["assignment", "career", "admin"]
    summary: str
    next_step: str
    resolved: bool
    escalate: bool
```

- This is the only permitted final output type for any conversation that reaches a terminal state inside the Desk.
- `type(result.final_output) is Ticket` must hold.
- `resolved` is consumed by real Python control flow.
- `escalate` is set according to the rules in FR-7A.

### 3.3 courses.json (Authoritative Knowledge)

Shape (minimum required):

```json
{
  "courses": [
    {
      "id": "agentic-ai-w4",
      "title": "Agentic AI - weekdays batch 4",
      "schedule": "Mon-Thu, 7-9pm",
      "policies": {
        "late_submission": "48 hours, 20% penalty"
      },
      "assignments": [
        {
          "id": "a3",
          "title": "First coded agent",
          "due": "2026-10-02"
        }
      ]
    }
  ]
}
```

- This file is the single source of truth for all course facts.
- No agent may invent data that is absent from this file.
- Deleting a course from this file must cause the Desk to stop answering questions about it with zero code change.

### 3.4 TimelineEntry (Audit Log Record)

```python
@dataclass
class TimelineEntry:
    request_id: str
    timestamp: str        # ISO-8601
    event: str            # e.g. "agent_start", "tool_call", "handoff", "agent_end"
    agent_name: str
    details: str
```

- Written by run-level hooks to a durable append-only log (a JSONL file or a database row).
- One student conversation produces one ordered sequence of these entries.
- This is the durable record required by NFR-3 — printing to console alone is not sufficient.

---

## 4. Tools

All tools obey the constitutional rule: they never raise exceptions to the caller.  
Any failure is returned as a clear natural-language sentence the model can act on.

### 4.1 Course-Data Tools

| Tool Name        | Purpose                                      | Returns                                      |
|------------------|----------------------------------------------|----------------------------------------------|
| `list_courses`   | List all available courses                   | List of course summaries                     |
| `get_course`     | Retrieve schedule + policies for one course  | Course details or “not found” sentence       |
| `get_assignment` | Look up one assignment by id                 | Assignment details or “not found” sentence   |

### 4.2 Control Tools

| Tool Name      | Purpose                                                                 | Behaviour on call                                     |
|----------------|-------------------------------------------------------------------------|-------------------------------------------------------|
| `close_ticket` | Terminate the run cleanly and produce the final Ticket                  | Ends the run immediately; output becomes final result |

### 4.3 Tier-Gated Tool

Tool name: `get_scholarship_resources`

- At least one tool is offered **only** to students whose `tier == "scholarship"`.
- For all other students the tool is completely absent from the tool list presented to the model (not merely refused at runtime).
- Returns: a descriptive string listing the scholarship resources relevant to the student's enrolled course.

### 4.4 Summariser Tool

- Input: a long policy text.
- Output: exactly three concise lines.
- Called by the Desk; the Desk remains the speaker after the call.

---

## 5. Dynamic Instructions (System Prompt Construction)

The Desk’s system prompt is never a static string.  

At the start of every request the following information is taken from the current `StudentProfile` and used to build the prompt:

- Student’s name → used for greeting
- Course the student is enrolled in → named explicitly
- `open_tickets` value → if ≥ 3 the prompt becomes noticeably shorter and more concise

The fully resolved prompt must be printable / loggable **before** any model call is made.

---

## 6. Category Ownership & Routing Logic

Every question that passes the guardrail must be classified into exactly one of three categories:

| Category     | Owner                  | Mechanism                     |
|--------------|------------------------|-------------------------------|
| `assignment` | Assignments Specialist | Handoff from Desk             |
| `career`     | Careers Specialist     | Handoff from Desk             |
| `admin`      | The Desk itself        | Direct tool calls; no handoff |

- Administrative questions (schedules, general policies, enrolment matters) stay with the Desk.
- The Summariser tool may still be used by the Desk on long admin answers.
- After a handoff the specialist, not the Desk, produces the answer that reaches the student.

---

## 7. Guardrail

- An input guardrail runs **before** the Desk model is ever called.
- If the question is off-topic the guardrail trips.
- The program catches the tripwire exception, returns a polite plain-text refusal, and never constructs a Ticket.
- The Desk model incurs zero cost on this path.
- The exact location where the exception is caught must be pointable on demand.

---

## 8. Lifecycle Hooks & Observability

### 8.1 Run-level Hooks

- Attached at the run level.
- Record an ordered audit timeline covering every agent that participates, including handoff events.
- One student question → one timeline that names the agents in order.
- The timeline is written to a durable location (file or database), not only printed.

### 8.2 Agent-level Hooks

- Attached to **exactly one** specialist (no more, no less).
- Become silent at the moment of a handoff (this behaviour must be explainable).

### 8.3 Custom Runner

- Wraps every run in the process.
- Stamps a unique `request_id` and records elapsed wall-clock time.
- Registered once at application startup.
- No agent definition is modified to accommodate it.
- Its output appears for both the Desk’s run and any specialist’s run.

### 8.4 Tracing

- Enabled for every conversation.
- Exported under the project’s own key.
- One student conversation appears as exactly one coherent trace.
- Every span in the trace must be nameable and explainable by the project owner.

---

## 9. Turn Ceiling & Termination

- The turn ceiling is a fixed numeric value: 10 turns. Justification: a resolved conversation needs at most roughly four model interactions (guardrail pass, tool calls, a possible handoff, ticket production), so 10 gives comfortable headroom while hard-stopping any loop. This number is the value referenced by FR-9's acceptance criterion.
- Every run operates under a hard turn ceiling.
- Exceeding the ceiling raises an exception that is caught and reported.
- The exception-handling path still produces a Ticket with `escalate: true` (FR-7A).
- The `close_ticket` tool provides a clean, deliberate termination path whose output becomes the final result.

---

## 10. Chainlit Interface

- The Desk is exposed through a browser-based chat interface.
- On session open the agent instance and the `StudentProfile` are created **once**.
- They are not recreated on subsequent messages.
- Conversation memory is maintained for the lifetime of the session.
- Different browser windows / sessions are completely isolated.
- The message handler uses `await` with the asynchronous runner (synchronous variant is forbidden).

---

## 11. Secrets & Startup

- All secrets live exclusively in `.env` (gitignored).
- Missing required keys produce a clear, early, human-readable startup error.
- No secrets appear in source, comments, or documentation.

---

## 12. Failure Handling Contract

- Tools never raise to the caller. Bad data → clear sentence the model can act on.
- Guardrail refusal → plain text, no Ticket, process stays alive.
- Turn-ceiling exhaustion → caught exception + Ticket with `escalate: true`.
- Malformed structured output → official SDK parsing error is surfaced; half-filled Tickets are rejected.

---

## 13. Data Flow Summary (Happy Path)

1. Student question arrives.
2. Guardrail evaluates domain → passes.
3. Custom Runner starts, stamps `request_id`.
4. `StudentProfile` is injected as local context.
5. Dynamic system prompt is built and (optionally) logged.
6. Desk decides:
   - **Admin** → calls course tools (and optionally Summariser) → answers → `close_ticket` → Ticket.
   - **Assignment / Career** → handoff → specialist answers → Ticket.
7. Run-level hooks record the ordered timeline.
8. Trace is emitted as one coherent unit.
9. Custom Runner records elapsed time.
10. Final output is a typed `Ticket`.

---

## 14. Alignment with Constitution & Specification

This plan is deliberately constrained by:

- Constitution §3 (model rules)
- Constitution §5 (student data & dynamic prompt)
- Constitution §6–7 (tools & agents)
- Constitution §8–9 (Ticket & guardrail)
- Constitution §10 (hooks, runner, tracing)
- All FR-1 … FR-13 and FR-7A / FR-8A behaviours
- All NFR-1 … NFR-5 constraints

No architectural decision in this document weakens or overrides any rule in the constitution or any behaviour in the specification.

---

**End of Plan**