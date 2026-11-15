# Investigation Sweeps V1: release-audit corrections

Date: 2026-11-15. Starting PR #11 head:
`0c7f893e53b6d0040120c46d4a2e4797ce1f505b`.
This supplements the original frozen contract; it does not rewrite prior results.

## Reproduced issues and bounded corrections

1. An otherwise valid JSON integer outside float64 range raised `OverflowError`
   during finite-input checking. It is now rejected as an input error before any
   store mutation, with the same finite-value requirement and CLI exit code 2.
2. A failed fresh baseline produced an empty member list. Each declared value is
   now retained explicitly as `not_run` / `not_attempted`, with no invented result
   or revision reference. No hypotheses execute after a failed baseline.
3. Synthetic omitted or duplicate native comparison rows could yield a completed
   sweep. Completion now requires exactly the requested observation IDs, in order,
   and a recognized native comparison outcome for each. Event states remain
   explicitly separate events, never treated as simultaneous observations.
4. Windows-specific backslashes in captured relative paths prevented inspecting
   those archives on Linux. New paths use forward slashes; the inspector reads
   either historical separator without modifying evidence. Absolute, drive-based,
   traversing or escaping captured paths are refused. Rejected/partial baselines
   are also inspected as evidence, not promoted to successful calculations.

Only `src/emfeeld/sweeps.py` changes in production. No physical law, solver, energy
policy, stored scenario, legacy contract, dependency or numerical tolerance changes.
These are orchestration, input-handling and evidence-portability corrections.

## Regression evidence

The first release-audit run against the unmodified PR head produced **6 failures
and 1 pass**. The missing-baseline-outcome and incomplete-comparison tests inject
synthetic backend failures/results; they do not assert that E1/G1/T1 actually had
those failures. The Windows-path test constructs a new fixture, not a rewrite of
an original Windows run. The oversized-integer case is a direct malformed-input
reproduction.

After correction, **43 targeted tests passed**: the original 26 sweep tests and
17 added release-audit cases, including path-boundary and CLI checks. Unexpected
execution exceptions still leave an incomplete attempt without a summary or final
inventory; those attempts are not called passes.

Commands:

```text
python -m pytest -q -W error tests/test_sweeps.py tests/test_sweep_release_guards.py
python -m pytest -q -W error tests
```

The existing Linux/Windows workflow already includes all tests plus E1/G1/T1 sweep
execution and separate mathematical-reference checks. Fresh results for this
corrected head must be reviewed before release; original-head CI is not a pass for
these changes. T1 remains exposed regression evidence, not a new hidden transfer
case. Same-author verification is not independent review. Teaching evaluation
stays paused. User installations and existing recordings remain unchanged.
