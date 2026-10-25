# Applied lab workbook

Work in a separate branch and keep the synthetic reference path passing. Each lab's detailed instructions are in its module guide. This workbook defines the evidence reviewers should collect.

| Module | Change to make | Evidence to submit |
|---|---|---|
| 1 Harness | Add an onboarding-policy workflow | Typed request, outcome definition and idempotency test |
| 2 Loops | Introduce and fix a non-terminating planner | Failed budget run followed by a terminating run |
| 3 Context | Add competing tenant policies and long memory | Context dump with correct scope and budget |
| 4 Tools | Add read-only release-status lookup | Contract, malformed-input tests and unavailable-data behavior |
| 5 Memory | Exercise two users and two sessions | Visibility/TTL/deletion matrix and tests |
| 6 Orchestration | Add a reliability specialist | Allocation diagram, cancellation proof and changed recommendation |
| 7 Guardrails | Test a two-tenant role matrix | Negative tests for every forbidden action |
| 8 Evals | Add negative and held-out cases | Evaluation card, baseline and intentional regression failure |
| 9 Human review | Review across a service restart | Proposal, rejected/approved traces and duplicate protection |
| 10 Observability | Diagnose timeout and policy failure | Correlated trace/events and an actionable alert proposal |

## Reference solution pointers

The implementation linked from each module is the worked example. For additional acceptance patterns, inspect `tests/test_runtime.py`, `tests/test_context_tools.py`, `tests/test_api_provider.py` and `tests/test_lessons.py`. These test behavior and boundaries, not just function return types.

## Reviewer checklist

Ask the learner to explain the customer need, demonstrate the success path, deliberately break one dependency, identify the correct operational owner and explain the deployment limitation. Request an evidence link for every claim of completion.

Use the capstone rubric for assessment. A lab is not complete if only its happy-path screenshot is available.
