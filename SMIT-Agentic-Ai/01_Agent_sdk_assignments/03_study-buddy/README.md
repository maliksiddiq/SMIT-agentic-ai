# Study Buddy — an OpenAI Agents SDK tutor

A small multi-agent tutoring app built on the **OpenAI Agents SDK** (wired to
Gemini via the OpenAI-compatible endpoint). A `Study Buddy` tutor delegates work
to two specialist sub-agents — a `Question Writer` and a `Grader` — and tracks a
per-student `StudentProfile` across sessions.

## Setup

Requirements: Python 3.10+, [`uv`](https://docs.astral.sh/uv/) (or any venv).

```bash
# from this folder
uv venv && uv pip install -r requirements.txt     # or: pip install -r requirements.txt
cp .env.example .env                                # then edit .env
```

Set these in `.env`:

```
GEMINI_API_KEY=your-gemini-key        # required: the model the agents run on
OPENAI_API_KEY=your-openai-key        # optional: enables trace export to platform.openai.com/traces
```

Run the interactive CLI:

```bash
python main.py
```

> Tracing note: `set_tracing_disabled` is intentionally removed. If `OPENAI_API_KEY`
> is set, each quiz cycle is exported as one trace named **"Study session"**. With
> only a Gemini key, traces are still recorded locally (and captured by our offline
> verifier) but not uploaded to OpenAI.

## What it does

- **Per-turn difficulty (M3):** the system prompt is built from the profile — it
  names the student, pushes `weak_topics`, and demands harder questions once a
  topic's accuracy passes 70% (the decision is made in Python, not by the model).
- **Two specialists (M4):** `question_writer` and `grader` are `Agent`s wrapped as
  tools; the tutor keeps the conversation and calls them in order.
- **Tuned settings (M5):** `question_writer` runs at `temperature=0.9` (varied
  questions), `grader` at `temperature=0.1, max_tokens=120` (short, repeatable
  verdicts); the recording turn forces `tool_choice="required"`.
- **Reusable variants (M6):** a `Gentle` and a `Strict` tutor are created with
  `tutor.clone(...)` (they share the model wiring; overriding `model_settings`
  drops fields you don't restate).
- **Observability (M7):** one quiz cycle = one trace, with spans for the task,
  each agent run, each model turn, and each tool call.
- **Persistence + CLI (M8):** pick a topic (or let the tutor pick a weak one),
  answer in the terminal, see the verdict, quit with an accuracy summary. The
  profile is saved to `student_profile.json` between runs.

## Example run

```
$ python main.py
Welcome back, Alex (beginner). Weak topics: ['handoffs', 'guardrails']

1) Pick a topic   2) Let tutor pick a weak topic   q) Quit
> 2
Tutor picks: handoffs

QUESTION: In a multi-agent system, what is a handoff and what happens to the
conversation history when control is transferred to another agent?

Your answer: A handoff transfers control to another agent while keeping the conversation history.
VERDICT: CORRECT - Your answer correctly states a handoff preserves conversation history.

running tally: {'handoffs': {'correct': 1, 'total': 1}}

> q

=== Session summary ===
  handoffs: 1/1 correct (100%)
[profile saved to student_profile.json]
```

Re-running later reloads `student_profile.json`, so your accuracy history survives
a restart.

## Files

- `main.py` — agents, tools, the CLI loop, and tracing setup.
- `topics.json` — the 14 course topics (id, title, summary, key facts).
- `verify_offline.py` — drives the M4 orchestration with a fake model (no API key).
- `verify_m5_m6.py` — exercises M5/M6 offline (settings, clones, shared-list trap).
- `verify_m7_m8.py` — exercises M7/M8 offline (trace capture, persistence).

## What it does badly (read this)

This is the part people actually care about:

1. **An extra model call every turn.** The tutor never writes the question
   itself — it calls `question_writer`, which is another agent run. So each quiz
   turn burns at least two generations (tutor + specialist) plus the grader. The
   tutor's final "Well done!" message after `record_answer` is a **wasted
   generation** you could drop; we keep it only for friendliness.
2. **Grading is shallow.** The grader sees one concatenated string
   (`QUESTION / ANSWER / KEY FACTS`) and returns a one-line verdict capped at
   `max_tokens=120`. Partial, technically-correct-but-misses-the-point answers get
   a blunt CORRECT/PARTIAL/INCORRECT with no structured reasoning, because it has
   no view of the student's prior mistakes or the conversation state.
3. **Adaptivity is post-hoc and thin.** Difficulty only changes *after* a topic
   has at least one recorded answer; a brand-new topic always gets a generic
   question, and "harder" just means a prompt nudge, not curated harder material.
4. **No guardrails.** Nothing stops a student from pasting the question back and
   asking the tutor to answer it for them, or from jailbreaking the grader into
   always returning CORRECT. `input_guardrails`/`output_guardrails` are unused.
5. **Profile storage is naive.** `student_profile.json` is written wholesale with
   no file locking — two simultaneous runs (or a crash mid-write) can clobber or
   corrupt it. There is no schema migration if the profile shape changes.
6. **Tracing needs a second key.** Because the model runs on Gemini, the nice
   OpenAI trace dashboard only lights up if you also supply `OPENAI_API_KEY`; with
   Gemini alone the spans are local-only.
7. **Topic content depends entirely on the model.** `question_writer` invents
   questions from the topic's notes; `temperature=0.9` adds variety but also the
   occasional off-target or duplicate question, with no validation that the
   question actually matches the stated key facts.
