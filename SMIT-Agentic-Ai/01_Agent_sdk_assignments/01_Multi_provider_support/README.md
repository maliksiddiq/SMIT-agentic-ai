# OpenAI Agents SDK — Agent + Runner + Multi-Provider (OpenAI & Gemini)

![Python 3.14](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)
![UV](https://img.shields.io/badge/package_manager-uv-green)
![openai-agents](https://img.shields.io/badge/openai--agents-0.20.0-orange)

A small, beginner-friendly CLI project that proves **one single `Agent` definition can run on two different LLM providers — OpenAI and Gemini — by changing one value in a `.env` file**.

---

## 1. Project Overview

This project uses the official `openai-agents` SDK to build a conversational **Agent**, then demonstrates the different ways to attach a **model** to that agent, the different **Runner** execution styles, and finally **multi-provider support**.

The most important takeaway:

> The `Agent` code never changes between providers. The provider (OpenAI or Gemini) is chosen through the `MODEL_PROVIDER` environment variable in `.env`. Provider-specific details (API key, base URL, model name) are configured *outside* the Agent definition.

## 2. Problem This Project Solves

In real life, teams often build an agent against a single provider and then get locked in to that provider — its API, its pricing, its rate limits, its outages.

The client here originally had an OpenAI-only agent and asked: *"Make the same agent run on Gemini without rewriting it."* This project solves exactly that:

- The **Agent definition is provider-agnostic**.
- The **provider is a configuration value**, not code.
- Switching Gemini ↔ OpenAI is a one-line change in `.env` — no code edits.

This is useful in production for cost control, availability (one provider can take over when another is down), testing (Gemini free tier for development, OpenAI for production), and avoiding vendor lock-in.

## 3. Key Features

- One `Agent` definition works on **both Gemini and OpenAI** (see `main.py`).
- Provider selected via `MODEL_PROVIDER` in `.env` — no code changes.
- Three ways to bind a model to an agent:
  - **Agent level** — `Agent(..., model=model)`
  - **Run level** — `Runner.run_sync(..., run_config=RunConfig(model=model))`
  - **Global level** — `set_default_openai_client(client)`
- Three **Runner** execution styles: synchronous, asynchronous, and streaming.
- **Multi-turn chat** with real conversation memory via `result.to_input_list()`.
- Clean separation of secrets (`.env` git-ignored) from code.

## 4. How It Works

In simple terms:

1. The program reads configuration from `.env` (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `MODEL_PROVIDER`, `GEMINI_MODEL`).
2. A provider-specific HTTP client is created — for Gemini it is just an OpenAI-compatible client pointed at Google's endpoint:
   `https://generativelanguage.googleapis.com/v1beta/openai/`
3. That client is wrapped by `OpenAIChatCompletionsModel`, which translates the agent's request into a standard chat-completions call.
4. The `Agent` object (a name + instructions + the model) stays **identical** for both providers.
5. `Runner.run_sync(agent, user_input)` runs the loop: it passes the input (plus history) to the model, gets a response, and returns a `RunResult` whose `final_output` is the answer.

Because Gemini exposes an OpenAI-compatible endpoint, the **same `openai` client abstraction** works for both — with `make_token` in mind, the only real difference is the `base_url` and the model name.

## 5. Project Architecture

```text
                 ┌──────────────────────────────┐
                 │         .env file            │
                 │  MODEL_PROVIDER=gemini|openai │
                 └──────────────┬───────────────┘
                                │ os.getenv()
                                ▼
   ┌──────────────────────────────────────────────────────┐
   │                Provider setup (outside Agent)        │
   │  gemini: AsyncOpenAI(api_key=GEMINI_API_KEY,         │
   │           base_url=...generativelanguage...)         │
   │  openai: AsyncOpenAI(api_key=OPENAI_API_KEY)         │
   └────────────────────────┬─────────────────────────────┘
                            │
                            ▼
              OpenAIChatCompletionsModel(model=..., client=...)
                            │
                            ▼
            ┌──────────────────────────────┐
            │  Agent (SAME for both)       │
            │  name + instructions + model │
            └──────────────┬───────────────┘
                           │  Runner.run_sync()
                           ▼
                 ┌──────────────────┐
                 │   LLM Provider   │  (Gemini or OpenAI)
                 └────────┬─────────┘
                          ▼
        RunResult → result.final_output  → printed answer
```

## 6. Project Structure

| File | Purpose |
|---|---|
| `main.py` | **The multi-provider demo.** One Agent, picks Gemini or OpenAI from `MODEL_PROVIDER`. |
| `hello_agent.py` | Tiny "first run" demo — a Gemini agent that replies in one short sentence. |
| `config_agent_level.py` | Shows attaching the model **to the Agent** (`Agent(..., model=model)`). |
| `config_run_level.py` | Shows attaching the model **per run** via `RunConfig(model=model)`. |
| `config_global_level.py` | Shows attaching the client **globally** via `set_default_openai_client()`. |
| `runner_lab.py` | Demonstrates the three Runner styles: sync, async, streamed. |
| `chat_loop.py` | Interactive **multi-turn** chat with memory (`to_input_list`). |
| `pyproject.toml` | UV project manifest (dependencies, Python version). |
| `uv.lock` | Locked, reproducible dependency versions. |
| `.env.example` | Template for `.env` — **placeholders only, no real keys**. |
| `.env` | Your local secrets — **git-ignored, do not commit**. |
| `.gitignore` | Ignores `.env`, `.venv`, caches. |
| `.python-version` | Pins Python 3.14 for uv. |
| `src/assignment_01/` | Default uv package scaffold (not used by the demos). |

## 7. Requirements

- **Python 3.11+** (project is pinned to **3.14** in `.python-version`).
- **uv** as the only package manager ([install uv](https://docs.astral.sh/uv/)).
- `openai` **v2.x** (2.54.0 verified).
- `openai-agents` **0.20.0** verified.
- `python-dotenv`.
- Internet access to `api.openai.com` and/or `generativelanguage.googleapis.com`.
- At least one valid API key (Gemini and/or OpenAI).

## 8. Installation

```bash
# 1. Clone or copy the project folder into place
# 2. Create the virtual environment and install dependencies
uv sync

# 3. Create your local environment file from the template
#    macOS / Linux / Git Bash
cp .env.example .env
#    Windows PowerShell
Copy-Item .env.example .env
```

`uv sync` reads `pyproject.toml` + `uv.lock` and creates the `.venv` automatically. The versions verified in this project:

```bash
python 3.14.5
openai          2.54.0
openai-agents   0.20.0
python-dotenv   (installed)
```

You can check them with:

```bash
uv run python -c "import openai, agents, sys; print(openai.__version__, agents.__version__, sys.version)"
```

## 9. Environment Configuration

Edit `.env` and fill in your real keys:

```dotenv
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
MODEL_PROVIDER=gemini
GEMINI_MODEL=gemini-3.6-flash
```

- Get a **Gemini** key at [Google AI Studio](https://aistudio.google.com/apikey).
- Get an **OpenAI** key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
- `MODEL_PROVIDER` must be either `gemini` or `openai`.
- `GEMINI_MODEL` is only used by the Gemini branch (e.g. `gemini-3.6-flash`).

> Keep `.env` private. It is listed in `.gitignore`, so it will not be committed.

## 10. Running the Project

Every script is standalone and run from the project root:

```bash
uv run hello_agent.py
uv run config_agent_level.py
uv run config_run_level.py
uv run config_global_level.py
uv run main.py
uv run runner_lab.py
uv run chat_loop.py
```

Expected outputs (verified against Gemini):

```text
uv run hello_agent.py
# -> a real one-sentence reply about agentic AI

uv run config_agent_level.py   # What is 2+2?  -> 4
uv run config_run_level.py     # What is 2+2?  -> 4
uv run config_global_level.py  # What is 2+2?  -> 4

uv run main.py                 # capital of France -> Paris
```

## 11. Switching Between Gemini and OpenAI

Only `main.py` is fully provider-agnostic. To switch providers:

1. Open `.env`.
2. Change `MODEL_PROVIDER`:

```dotenv
# Gemini
MODEL_PROVIDER=gemini

# OpenAI
MODEL_PROVIDER=openai
```

3. Run the same script, unchanged:

```bash
uv run main.py
```

`main.py` decides the client and model name based on the variable:

```python
if provider == "gemini":
    client = AsyncOpenAI(api_key=os.getenv("GEMINI_API_KEY"),
                         base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
else:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model_name = "gpt-4o-mini"

model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)

# This Agent is byte-for-byte identical for both providers:
agent = Agent(name="Assistant", instructions="You are a helpful, concise assistant.", model=model)
```

**Verification status:** the `gemini` branch was run and produced correct answers. The `openai` branch is implemented identically, but a runtime test currently returns **401 `invalid_api_key`** — so confirm `OPENAI_API_KEY` is a valid key before relying on the OpenAI path.

## 12. Understanding the Different Scripts

| Script | What it teaches |
|---|---|
| `hello_agent.py` | Minimal setup: client → model → agent → `Runner.run_sync`. |
| `config_agent_level.py` | Model is baked into the **Agent** itself. |
| `config_run_level.py` | Model is passed **per run** via `RunConfig` — the Agent stays model-less. |
| `config_global_level.py` | Client registered once with `set_default_openai_client`; tracing disabled. |
| `main.py` | **Multi-provider** — single Agent, provider decided by `MODEL_PROVIDER`. |
| `runner_lab.py` | All three Runner styles in one file (sync / async / streamed). |
| `chat_loop.py` | Interactive chat that remembers the conversation. |

## 13. Multi-Turn Chat

`chat_loop.py` is an interactive REPL:

```text
Chat shuru — 'exit' likh ke band karo.     # "Chat is starting — type 'exit' to stop."
You: My name is Ali.
Agent: Nice to meet you, Ali!
You: What is my name?
Agent: Your name is Ali.                    # memory works
You: exit
```

How the memory works — each turn:

1. The previous conversation is kept in `history`.
2. The new user message is appended: `history + [{"role": "user", "content": user_input}]`.
3. The run returns a `RunResult`, and the full conversation is re-read from it:
   `history = result.to_input_list()`.
4. Next turn, that history is passed back, so the agent "remembers" what was said.

## 14. Runner Methods

`runner_lab.py` shows the three ways to run an agent:

| Method | Style | Example |
|---|---|---|
| `Runner.run_sync(...)` | Synchronous, blocking | `result = Runner.run_sync(agent, "Tell me a fact about Mars.")` |
| `await Runner.run(...)` | Asynchronous (async/await) | `result = await Runner.run(agent, "Tell me a fact about the Moon.")` |
| `Runner.run_streamed(...)` | Streaming tokens as they arrive | `for event in result.stream_events(): print(event.data.delta)` |

Notes on this implementation:

- `Runner.run_streamed(...)` in `openai-agents` 0.20.0 returns a `RunResultStreaming` directly — it is **not** `await`-ed.
- The script runs the async and streamed demos first and the sync demo last. This ordering matters: `run_sync` opens a short-lived event loop internally; calling your own `asyncio.run(...)` after it against the same client can deadlock (HTTP hang) — avoiding that order keeps the script clean and reliable.

## 15. Security

- **Never commit `.env`.** It is already ignored by `.gitignore`.
- **`.env.example` contains placeholders only** — copy it to `.env` and fill in real keys locally.
- **Never hard-code API keys in source files**, READMEs, logs, or evidence files.
- Treat keys as secrets: rotate them if ever exposed, limit their scope if the provider allows it.
- The code only ever reads keys via `os.getenv(...)` — the `.env` file is never printed or logged.

## 16. Troubleshooting

| Symptom | Almost certainly | What to do |
|---|---|---|
| `AuthenticationError: 401 ... Incorrect API key` | Wrong/placeholder key in `.env` | Replace the key in `.env` with a valid one (Gemini or OpenAI depending on provider). |
| `RateLimitError: 429 ... You exceeded your current quota` | Free-tier quota / rate limit on the provider | Wait for the retry window (seconds–minutes) or upgrade plan. Gemini `generativelanguage` free tier is limited (e.g. 20 requests/day per model per project). |
| `[non-fatal] Tracing client error 401` appearing in output | Harmless telemetry: the SDK's tracing backend is not configured | Ignore it — the agent answer is still produced. |
| `uv run` not found | uv not installed | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` (see [docs.astral.sh/uv](https://docs.astral.sh/uv/)). |
| Gemini never answers back / no output | Quota exhausted or key invalid | Swap `MODEL_PROVIDER` to the provider whose key you trust, or wait and retry. |

**Rule of thumb:** a `401` means the key itself is wrong; a `429` means the key is fine but rate/billing limited — do not try to fix `429`s by swapping random keys.

## 17. Learning Outcomes

After working through this project you will understand:

- How the `openai-agents` SDK wires together `Agent`, `Runner`, and a `Model`.
- Why a provider can be swapped **without changing agent code** (configuration over code).
- The three model-binding levels: agent, run (`RunConfig`), and global (`set_default_openai_client`).
- The three Runner execution styles: synchronous, asynchronous, and streaming.
- How conversation memory is maintained with `result.to_input_list()`.
- How to manage secrets safely with `python-dotenv`, `.env`, and `.gitignore`.
- How the OpenAI-compatible endpoint of Gemini lets one SDK talk to both providers.

---

*Built with :heart: for the "OpenAI Agents SDK — Agent + Runner + Multi-Provider" assignment.*