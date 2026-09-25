# Tracing manual verification checklist

Run the Chainlit app with `uv run chainlit run chainlit_app/app.py`, submit
`demo/clean.diff`, and open the exported trace for the resulting request.

- [ ] Exactly one trace exists for the review request.
- [ ] The trace contains SecurityReviewer, TestsReviewer, StyleReviewer, Desk,
      and MergeSpecialist spans.
- [ ] The three reviewer spans overlap in time.
- [ ] The slowest reviewer name and duration were recorded below.
- [ ] A critical-security run contains the RemediationSpecialist handoff span.

Recorded live verification:

- Trace request ID: pending live run
- Slowest reviewer: pending live run
- Reviewer overlap: pending live run
