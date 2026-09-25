# 🛡️ Code Review Desk

**An AI-powered, concurrent code review pipeline — built on the OpenAI Agents SDK, powered by Google Gemini.**

---

## 📌 What Is This?

**Code Review Desk** is an automated code review system. You give it a **unified diff** (a code change), and instead of one AI reading through it top-to-bottom, **three specialist AI reviewers read it at the same time**, each looking for something different. Their findings are merged into one clean report — and if something serious turns up on the security side, the system automatically brings in a specialist to propose a real fix.

### 🎯 The Problem It Solves

A single generalist AI reviewing a diff sequentially is slow and shallow — it tries to think about security, tests, and style all at once, in one pass, with no real specialization. Code Review Desk solves this by:

- Running reviews **in parallel** instead of one after another — faster results
- Giving each concern its own **specialist agent**, instead of one agent doing everything
- Returning findings as **structured data**, not prose — so they can be deduplicated, sorted, and safety-checked by code, not guessed at
- Refusing to ever show the user a report that accidentally contains a leaked secret
- Making every review fully **traceable and logged**, so nothing about how it behaved is a guess after the fact

---

## ⚙️ How It Works — The Flow

```
📄 A diff comes in
        ↓
✂️  Split into per-file chunks
        ↓
🔐 Security   🧪 Tests   🎨 Style   →  all three reviewers work on it AT THE SAME TIME
        ↓
🧩 Merge specialist deduplicates findings and orders them by severity
        ↓
🛡️  Output guardrail scans the report for leaked secrets/credentials
        ↓
   ┌────────────┴────────────┐
   │                         │
✅ Clean report      🚨 Critical security issue found
   delivered to           → conversation hands off to
   the user                 the Remediation specialist
```

Every reviewer run, the merge step, and any handoff are captured under **one single trace** and logged to a local ledger — so a full review can always be explained and verified after the fact, not just trusted.

---

## 🤖 The Agents — Who Does What

This project is built around **six agents**, each with a clearly defined job. A few of them carry the real weight of the system:

### 🖥️ Desk — The Orchestrator
The Desk is the agent the user is effectively "talking to." It doesn't do the heavy reviewing itself — instead, it's the coordinator: it splits the incoming diff, launches the three specialist reviewers together, calls the Merge specialist as a tool, runs the report through the safety guardrail, and either delivers the final result itself or hands the conversation off to Remediation. It stays in control of the entire interaction from start to finish, except in the one case where it deliberately lets go (the security handoff).

### 🔐 Security Reviewer — The Most Heavily Governed Agent
This is arguably the most important reviewer in the whole system. It's specifically tuned to look for injection risks, exposed secrets, unsafe authentication or deserialization patterns, and dependency risk. Unlike the other two reviewers, it is **forced** to consult the team's ruleset before it can finish — it has no choice in the matter, enforced by configuration rather than just asked nicely in its instructions. It's also the **only** reviewer whose critical findings are allowed to trigger a handoff to Remediation — a critical finding from Tests or Style never does this, by design.

### 🧪 Tests Reviewer — The Deeply Observed Agent
This reviewer checks for missing test coverage and tests broken or skipped by the change. What makes it special isn't what it looks for, but *how closely it's watched* — it's the one reviewer in the system fitted with detailed, agent-level monitoring hooks (in addition to the standard monitoring every reviewer gets), letting the system see its internal steps and tool calls in much finer detail than the other two.

### 🎨 Style Reviewer — The Baseline
This reviewer checks readability, naming, and formatting against team conventions. It's deliberately kept as the "plain" reviewer — no special required tools, no special monitoring — so it acts as a clear point of comparison against Security and Tests, making it easy to see exactly what makes each of the other two different.

### 🧩 Merge Specialist — The Tool
Once all three reviewers finish, Merge steps in — not as a conversational agent taking over, but as a **tool** the Desk calls directly. It takes the three raw sets of findings, removes duplicates and overlapping issues, and orders everything by severity (critical → major → minor), then hands a clean result straight back to the Desk. This is intentional: merging is a bounded, single-answer task, so it doesn't need — and shouldn't get — a full conversational handoff.

### 🩹 Remediation Specialist — The Handoff
Remediation only ever gets involved when the merged findings include at least one **critical security issue**. At that point, control of the conversation genuinely transfers to it — it speaks to the user directly, names exactly which finding triggered it, and proposes a concrete fix. This is deliberately a full handoff rather than a tool call, because proposing and discussing a fix is open-ended and conversational, not something with one tidy answer to hand back.

---

## 🧠 Model & Intelligence

- **Model provider:** Google **Gemini**
  - Primary model: `gemini-3.5-flash`
  - Fallback model: `gemini-2.5-flash` — automatically available if the primary is ever unusable, switchable without touching any agent's code
- Every agent configures its own model explicitly at the agent level — there is no shared, global default model anywhere in the system
- A cheaper "second opinion" pass can also be run for a single call, without ever permanently changing any agent's own configuration

---

## 🛡️ Safety First

- ✅ All secrets (Gemini API key, tracing key) live only in a local `.env` file — never committed, never logged, never shown to the user
- ✅ A dedicated **output guardrail** scans every finished report before delivery — if anything resembling a leaked credential is detected, the system **refuses** to show the report instead of risking exposure
- ✅ Every tool is built to fail gracefully — a broken file or a missing ruleset never crashes a review, it's reported clearly instead
- ✅ Every review runs under a **turn ceiling** — if a reviewer somehow gets stuck, the review is cut off and reported as a clearly labeled **partial review**, rather than running forever

---

## 🖥️ The Interface

The Desk is used through a clean, **Chainlit**-powered web UI with custom styling, where a diff is simply pasted in and the review happens **live**:

- Findings **stream in progressively** as each reviewer finishes — no waiting for one giant block of text at the end
- The same session remembers context, so reviewing a second diff doesn't mean re-answering the same setup questions
- Every outcome — a safety refusal, a partial review, a missing API key — is shown clearly and legibly, never as a blank screen or raw error

---

## 📊 Observability & Tracing

Every review is fully traceable end-to-end. Tracing is exported to a central dashboard even though the reviewers themselves run on Gemini, giving a clean, visual timeline of every run — including every tool call, every handoff, and exactly how long each step took. This is also how the project **proves** its concurrency claim: the reviewer spans can be inspected directly to confirm they genuinely overlapped in time, rather than just looking fast from the outside.

Alongside tracing, every run is also written to a local ledger — a simple, append-only log capturing which agent ran, how long it took, and how many findings it produced — giving a second, independent way to verify what happened in any given review.

---

## ✨ Why This Project Matters

This isn't just "a chatbot that reviews code" — it's a demonstration of several things working correctly together:

- 🚀 **True concurrency** — three agents genuinely running in parallel, not just appearing to
- 📦 **Structured output** — findings as real, typed data, not prose to be parsed
- 🧰 **Two different delegation patterns, used correctly** — a tool call (Merge) where one clean answer is needed, and a handoff (Remediation) where an open conversation is needed
- 🛑 **Guardrails that actually refuse** — safety enforced in code, not just requested in a prompt
- 📈 **Real, measured observability** — every claim about speed or behavior can be checked against a trace or a log, never just trusted

---

## 🧾 Quick Start

1. Clone the project and set up a Python virtual environment
2. Add your keys to a `.env` file (see `.env.example`)
3. Install dependencies
4. Run the Chainlit app and paste in a diff to review

---

*Built with the OpenAI Agents SDK · Powered by Google Gemini · Delivered through Chainlit* 💫