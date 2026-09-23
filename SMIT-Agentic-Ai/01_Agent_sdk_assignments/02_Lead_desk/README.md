# Lead Desk

Lead Desk is a small Python project that reads messages from potential
freelance clients and prepares a clear lead triage result.

It solves a common freelance problem: client messages can be vague, urgent,
too small, poorly paid, or based on revenue share instead of guaranteed
payment. The project uses Gemini through the OpenAI Agents SDK to identify the
lead's intent, budget, red flags, priority, and a suggested reply.

The project also demonstrates:

- Private freelancer data passed through runtime context.
- Rate and availability lookup tools.
- Structured `LeadTriage` output instead of plain text.
- Python-controlled saving of high-priority leads.
- An honesty guardrail that blocks requests to exaggerate experience.
- An audit trail that logs tool calls and results.

## Project Structure

All project files are inside this `Lead_desk` folder.

| File or folder | Purpose |
| --- | --- |
| `main.py` | Main application. Defines the freelancer profile, typed triage result, tools, Gemini connection, honesty guardrail, audit hooks, asynchronous runner, and Python-side save decision. |
| `leads.json` | Contains exactly six sample client messages covering the required lead types. |
| `saved.json` | Stores high-priority triage results after the application saves them. It is created or updated at runtime. |
| `test_lead_desk.py` | Automated tests for fixtures, tools, privacy, typed output, saving, the honesty guardrail, and audit hooks. |
| `PROMPTS.md` | Records the prompts used to demonstrate Task 4 and Task 5 Option C. |
| `NOTES.md` | Explains what went wrong during the remaining tasks and what was changed. |
| `pyproject.toml` | UV project configuration, Python version requirement, dependencies, and build settings. |
| `uv.lock` | Locks the installed dependency versions for repeatable setup. |
| `.python-version` | Selects Python 3.13 for UV. |
| `.env` | Local secret file containing `GEMINI_API_KEY`. This file is not committed to Git. |
| `.env.example` | Safe template showing the required environment variable without a real key. |
| `.gitignore` | Prevents `.env`, `.venv`, caches, and runtime `saved.json` from being committed. |
| `src/lead_desk/__init__.py` | Python package marker. |
| `src/lead_desk/app.py` | Supporting package module included in the UV project. The runnable application is `main.py`. |
| `.venv/` | Local virtual environment created and managed by UV. |

## How to Run

Open PowerShell and move to the project folder:

```powershell
cd "D:\SMIT-Agentic-Ai\SMIT-Agentic-Ai\Assignments\Lead_desk"
```

### 1. Install or update dependencies

Run:

```powershell
uv sync
```

### 2. Configure Gemini

Create a file named `.env` in the `Lead_desk` folder. Add your own Gemini key:

```env
GEMINI_API_KEY=your_actual_gemini_key
```

Never commit the real key or paste it into source code.

### 3. Run the application

Run:

```powershell
uv run python main.py
```

The program runs asynchronously, sends a normal client message to Gemini,
prints a typed JSON triage result, prints a high-priority banner when needed,
and saves high-priority results to `saved.json`.

If the configured account cannot use `gemini-2.5-flash`, the application
tries the currently available Gemini model. If the Gemini quota is exhausted,
the program prints a clear message and exits without an uncaught traceback.

### 4. Run the tests

Run:

```powershell
uv run python -m unittest -v test_lead_desk.py
```

All tests should pass before submission.

## Important Safety Rules

- The minimum acceptable hourly rate stays in application runtime context.
- It is not included in agent instructions, client messages, or public tool
  parameters.
- The model cannot decide whether a lead is saved.
- Python saves a result only when `triage.priority == "high"`.
- The honesty guardrail blocks requests to fabricate or overstate experience
  before a model call is made.
