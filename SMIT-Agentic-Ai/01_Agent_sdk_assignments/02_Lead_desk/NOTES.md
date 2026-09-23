# Lead Desk Notes

## Task 4

The first version had no protection against requests to exaggerate
experience. I added a synchronous input guardrail with `run_in_parallel=False`
so deceptive prompts are refused before any model/API call, while ordinary
leads continue normally.

## Task 5 Option C

The first version had no visibility into tool execution order. I added
`AuditHooks` lifecycle callbacks that print each tool's arguments at
`tool_start` and its result at `tool_end`.

Only Option C was implemented. Routing and conditional tools were intentionally
not added.
