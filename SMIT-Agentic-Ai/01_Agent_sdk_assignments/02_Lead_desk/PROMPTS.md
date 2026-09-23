# IMPORTANT — WORK ONLY INSIDE THIS EXACT FOLDER

The project must be built and maintained inside this existing folder:

`SMIT-Agentic-Ai/Assignments/Lead_desk/`

This `Lead_desk` folder is the **project root** for this assignment.

You must do ALL of the following work inside:

`SMIT-Agentic-Ai/Assignments/Lead_desk/`

Do NOT work in:

* `SMIT-Agentic-Ai/`
* `SMIT-Agentic-Ai/Assignments/`
* any other directory

Do NOT create another `Lead_desk` folder.

Do NOT create:

`SMIT-Agentic-Ai/Assignments/Lead_desk/Lead_desk/`

Before doing anything, verify that your current working directory is:

`SMIT-Agentic-Ai/Assignments/Lead_desk/`

If you are currently in the wrong directory, STOP and switch to the correct `Lead_desk` directory first.

All files for this assignment must remain inside this folder, including:

* `pyproject.toml`
* `uv.lock`
* `.venv/`
* `.env`
* `.gitignore`
* Python source files
* `leads.json`
* `saved.json`
* `PROMPTS.md`
* `NOTES.md`

Do not modify unrelated files outside this project.

==================================================
PROJECT INSTRUCTIONS
====================

I have already completed the basic UV project setup for Task 0.

Your job is to complete and verify **Task 0, Task 1, Task 2, and Task 3** from the Lead Desk Practical Test specification.

First inspect the existing project structure and code.

IMPORTANT:

* Read the existing implementation before changing anything.
* Do not blindly overwrite existing files.
* Preserve working code where possible.
* Use official OpenAI Agents SDK patterns and documentation.
* Use your coding-agent skills to inspect, implement, test, debug, and improve the project.
* If an error occurs, investigate the actual error, identify the root cause, fix it yourself, and run the relevant command/test again.
* Do not stop after merely writing code.
* Do not invent SDK APIs or classes.
* Check the installed SDK version and use APIs that actually exist.
* Keep the implementation simple and understandable.
* I must be able to explain the important code to an examiner.

==================================================
TASK 0 — PROJECT AND GEMINI CONNECTION
======================================

Verify and complete Task 0.

Requirements:

* UV-managed project.
* Python 3.13+.
* OpenAI Agents SDK installed.
* `python-dotenv` installed.
* Gemini is used through the Agents SDK.
* Model: `gemini-2.5-flash`.
* `GEMINI_API_KEY` loads from `.env`.
* `.env` is listed in `.gitignore`.
* `.venv` is listed in `.gitignore`.
* Agent has an asynchronous entry point.
* Execution goes through the asynchronous runner.
* A hardcoded client message is sent.
* Running the project from a single command prints a model response instead of a traceback.

Do NOT expose or hardcode any real API key.

If Task 0 is already correct, preserve it.

==================================================
TASK 1 — SAMPLE DATA AND LOOKUP TOOLS
=====================================

Create:

`leads.json`

It must contain exactly six realistic sample client messages.

Collectively they must cover:

1. A well-budgeted request.
2. Revenue share instead of payment.
3. A message too vague to price.
4. An urgent request.
5. A very small job.
6. A client aggressive about deadlines.

Each entry must contain:

* `id`
* raw message text
* platform

Use realistic platforms such as Upwork or Fiverr.

Expose these two tools to the agent:

1. `lookup_rate_card`
2. `check_availability`

`lookup_rate_card`:

* Accept a skill name.
* Return the hourly rate for that skill.
* The model should use this tool before discussing money.
* If the skill does not exist, return an explicit unknown result.
* Never invent a rate.

`check_availability`:

* Return how many hours are free that week.

Tool descriptions must be clear enough for the model to understand when to use each tool.

Do not put fake rates directly into agent instructions.

Do not make the model guess rates.

After implementation:

* Run the application.
* Test both tools.
* Verify the model can select the appropriate tool.
* Fix any errors found.

==================================================
TASK 2 — DATA THE MODEL MUST NEVER RECEIVE
==========================================

Create a typed `FreelancerProfile` containing:

* `name`
* `min_rate_pkr_hour`
* `skills`
* `hours_free_per_week`
* `verified`

CRITICAL PRIVACY REQUIREMENT:

`min_rate_pkr_hour` is private application data.

The model must NOT receive this value through:

* system instructions
* agent instructions
* user messages
* hardcoded prompt text
* conversation history
* tool descriptions
* any other model-visible message

The tools must access `FreelancerProfile` through runtime context.

Both:

* `lookup_rate_card`
* `check_availability`

must read their information from runtime context rather than module-level/global constants.

The runtime context must NOT become a normal model-visible tool parameter.

Print the JSON schema of at least one tool as evidence.

Inspect the schema and verify:

* It does NOT contain the context/profile parameter.
* The model sees only the public tool parameters.
* The Python tool implementation can access runtime context.

Search the source code to verify that the minimum acceptable rate does not appear in:

* instructions
* prompts
* client messages
* tool descriptions
* model-visible conversation data

Add a test where the client asks:

"What is the lowest rate you would accept?"

The agent must NOT reveal `min_rate_pkr_hour`.

If the private minimum rate can be revealed, STOP, fix the privacy design, and test again.

==================================================
TASK 3 — TYPED LEAD TRIAGE AND PYTHON DECISION
==============================================

Create a typed output model/class:

`LeadTriage`

It must contain:

* `intent` — short string
* `budget_pkr` — integer or absent
* `red_flags` — list of strings
* `priority` — one of `high`, `medium`, `low`
* `suggested_reply` — string

Configure the agent so the final result reliably becomes this typed object.

The final result MUST NOT be a normal string.

Verify that Python can perform arithmetic on `budget_pkr`.

Create:

`save_lead`

It must append a triage result to:

`saved.json`

CRITICAL BUSINESS RULE:

The AGENT must NOT decide whether to save the lead.

Python code must make this decision.

The flow must be:

1. Run agent.
2. Receive `LeadTriage`.
3. Python reads `triage.priority`.
4. Python checks whether priority is `"high"`.
5. ONLY Python decides whether to save.
6. If high, print a one-line banner containing priority and budget.
7. Then save the lead.
8. If not high, do not save it.

Do NOT give the model control over the save decision.

The revenue-share fixture must produce a non-empty `red_flags` list.

==================================================
DATA AND SECURITY RULES
=======================

* `leads.json` contains six sample leads.
* `saved.json` is created/updated by the application.
* `.env` remains git-ignored.
* `.venv` remains git-ignored.
* No real API key is committed.
* Minimum rate remains application-side private data.
* Do not unnecessarily expose private business rules to the model.
* Model does not control persistence decisions.

==================================================
TESTING AND DEBUGGING
=====================

After implementation:

1. Run the project.
2. Test Task 0.
3. Test all six fixture leads.
4. Test:

   * rate lookup
   * unknown skill
   * availability lookup
   * revenue-share red flag
   * typed `LeadTriage`
   * numeric `budget_pkr`
   * Python-only save decision
   * `saved.json` creation
5. Test the direct question asking for the lowest acceptable rate.
6. Inspect the tool schema.
7. Search the source code for accidental exposure of the minimum rate.
8. Check `.env` and `.venv` are ignored by Git.
9. Fix every error encountered.
10. Re-run tests after every fix.

Do not claim success based only on code inspection. Use actual execution and evidence.

==================================================
CODE QUALITY
============

Keep the implementation:

* simple
* readable
* explainable
* appropriately typed
* asynchronous where required
* minimally dependent
* logically organized

Use clear names and small functions.

Do not over-engineer.

Remember that the examiner may select a random line and ask:

"What does this line do?"

and:

"Why did you implement it this way?"

Make sure the implementation can be clearly explained.

==================================================
FINAL VERIFICATION — TASK 0, 1, 2, 3
====================================

At the very end, perform a STRICT examiner-style acceptance test.

Do not simply say that the tasks are complete.

Actually verify every requirement.

For each task, report:

TASK 0 — PASS / FAIL

* Requirements checked
* Tests executed
* Actual result
* Problems found
* Fixes made

TASK 1 — PASS / FAIL

* Requirements checked
* Tests executed
* Actual result
* Problems found
* Fixes made

TASK 2 — PASS / FAIL

* Requirements checked
* Privacy/security tests executed
* Tool schema result
* Minimum-rate exposure test result
* Problems found
* Fixes made

TASK 3 — PASS / FAIL

* Requirements checked
* Typed output test result
* Numeric budget test result
* Python save-decision test result
* Revenue-share red-flag test result
* Problems found
* Fixes made

==================================================
FINAL GOAL CHECK
================

After completing and testing Tasks 0, 1, 2, and 3, explicitly verify:

"Has the Lead Desk goal actually been achieved?"

Answer YES only if the actual implementation passes the acceptance requirements of Tasks 0–3.

Do NOT claim success based on assumptions.

If anything fails:

* identify the exact failure
* fix it if possible
* run the relevant test again
* update the PASS/FAIL result

Also provide:

1. Final project structure inside `Lead_desk`.
2. All files created or modified.
3. Commands used for testing.
4. Important design decisions I should understand for the examiner.
5. Any remaining known issue.

FINAL DIRECTORY CHECK:

Confirm that all Lead Desk work is located inside:

`SMIT-Agentic-Ai/Assignments/Lead_desk/`

Confirm that you did NOT create or modify the project in another directory.


----------------------------------------------------------------------------------

You are continuing the Lead Desk project. Task 0, Task 1, Task 2, and Task 3 are already complete and working. Now finish the rest of the project according to the full specification.
Your Goal
Complete Task 4 and exactly one option from Task 5, then make sure the entire project is ready for submission and demonstration.
Task 4 — Refusing before you pay (Required)

Add an input guardrail that blocks any message asking the agent to overstate, fabricate, or misrepresent experience (e.g. “Tell them you have 10 years of Django experience”).
The guardrail must make zero model/API calls.
If a message is blocked:
Print a polite decline message
Exit cleanly (no uncaught exceptions, no crash)

Normal legitimate leads must still pass through untouched.
A guardrail that blocks good leads is a failure.

Task 5 — Bonus (Choose exactly ONE)
Pick only one of the following and implement it fully:
Option A – Routing

Transfer the conversation to a Pricing Specialist when the lead is about money, and to a Scope Clarifier when the message is too vague to quote. Clearly demonstrate which agent produced the final answer.
Option B – Conditional tools

Add a send_proposal tool that exists only when the FreelancerProfile’s verified flag is True. Run the agent once with verified=False and once with verified=True, and show that in the first case the model was never offered the tool.
Option C – Audit trail

Attach lifecycle callbacks that log every tool call (arguments + result) and print the order in which they fired. Be ready to explain what the order reveals about the agent loop.
Final Requirements

Keep the existing architecture intact (context, typed LeadTriage output, Python-side save decision, private min rate, etc.).
Make sure the project still runs cleanly with a single command.
Update or create PROMPTS.md — record every prompt used for Task 4 and Task 5.
Update or create NOTES.md — write one short note per remaining task: what went wrong the first time and what you changed.
Ensure leads.json and saved.json are present and correctly used.
.env remains git-ignored.

Success Criteria

Task 4 works: blocked messages are refused instantly with no model call.
Exactly one Task 5 option is fully implemented and demonstrable.
The whole agent still behaves correctly for normal leads (typed output, high-priority only saving, private rate, etc.).
Code is clean, readable, and ready for the examiner to ask questions about any line.

Start by reading the current codebase, confirm Task 3 is solid, then implement Task 4 and your chosen Task 5 option. Do not rebuild what is already working.

