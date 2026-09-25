# Viva rehearsal — Code Review Desk

1. **Why split before model execution?**  
   `split_unified_diff` creates one chunk per changed file before any `Runner`
   call, keeping each reviewer focused and making malformed input a clear
   intake error.
2. **How is local context kept out of the prompt/tool schema?**  
   `ReviewContext` is passed to `Runner.run`; `lookup_ruleset` reads it from
   the SDK context wrapper and exposes an empty model-visible schema.
3. **Why typed output?**  
   Reviewers use `output_type=list[Finding]`, so severity ordering,
   deduplication, counting, and guardrail inspection operate on Pydantic
   objects rather than prose.
4. **Why concurrency?**  
   `run_reviewers_concurrently` creates all three coroutine calls before
   awaiting `asyncio.gather`; `test_concurrency_benchmark.py` demonstrates the
   concurrent wall-clock advantage over sequential execution.
5. **Why is Merge a tool but Remediation a handoff?**  
   Merge returns control to the Desk after deduplication, so it is an
   `Agent.as_tool` call. Remediation must take over the conversation after a
   critical security finding, so it is an SDK typed `handoff`.
6. **When does the guardrail run and what does it cost?**  
   It scans the fully rendered report after reviewer and merge work; a tripwire
   produces a refusal rather than silently editing the report, so prior model
   work has already incurred cost.
7. **How are metrics and ledger entries produced?**  
   `ReviewRunHooks` reads SDK `ModelResponse.usage` and lifecycle timing. The
   single `register_ledger` setting controls central JSONL recording without
   coupling agent definitions to the ledger.
8. **How is runaway execution bounded?**  
   Every reviewer and Desk run receives `max_turns=settings.turn_ceiling`,
   defaulting to 8. `MaxTurnsExceeded` becomes a clearly labeled partial
   result and UI status rather than a crash.
