# Concept-to-code traceability

The supplied screenshots define this course's ten-module backbone. Each module preserves its named flow and feedback loop. Additional infrastructure is separated into the implementation architecture. Screenshots are reference material; the course contains newly written explanations, illustrated PNG/SVG guides and Mermaid diagrams, not copies of the social-media artwork. The screenshots visibly credit @aiwithanuj; review attribution and redistribution rights before public course publication.

| Photo | Exact topic | Matching guide | Runnable lesson | Implementation |
|---|---|---|---|---|
| 1 | Harness Engineering | [Module 1](modules/01-harness-engineering.md) | `jev lesson 1` | `packages/core/src/jev_core/runtime.py` |
| 2 | Loop Engineering | [Module 2](modules/02-loop-engineering.md) | `jev lesson 2` | `packages/core/src/jev_core/runtime.py` |
| 3 | Context Engineering | [Module 3](modules/03-context-engineering.md) | `jev lesson 3` | `packages/core/src/jev_core/context.py` |
| 4 | Tool Design | [Module 4](modules/04-tool-design.md) | `jev lesson 4` | `packages/tools/src/jev_tools/registry.py` |
| 5 | Memory Architecture | [Module 5](modules/05-memory-architecture.md) | `jev lesson 5` | `packages/core/src/jev_core/store.py` |
| 6 | Orchestration Patterns | [Module 6](modules/06-orchestration-patterns.md) | `jev lesson 6` | `packages/workflows/src/jev_workflows/patterns.py` |
| 7 | Guardrails & Permissions | [Module 7](modules/07-guardrails-and-permissions.md) | `jev lesson 7` | `apps/api/src/jev_api/security.py` |
| 8 | Evals for Agents | [Module 8](modules/08-evals-for-agents.md) | `jev lesson 8` | `packages/evals/src/jev_evals/runner.py` |
| 9 | Human-in-the-Loop Design | [Module 9](modules/09-human-in-the-loop-design.md) | `jev lesson 9` | `packages/core/src/jev_core/store.py` |
| 10 | Observability & Tracing | [Module 10](modules/10-observability-and-tracing.md) | `jev lesson 10` | `packages/core/src/jev_core/telemetry.py` |

## Deliberate clarifications

- “Learn and improve” means observed feedback, reviewed policy/prompt changes and repeated evaluation. This course does not claim automatic model-weight learning.
- Human review follows the agent's proposed output. For consequential writes, committing the effect happens after review; this makes the pictured loop operationally safe.
- The orchestration example preserves research, coding, analysis and planning roles. The workers are deterministic examples; the optional live model drives the shared planner.
- The memory architecture distinguishes session memory, user-scoped long-term summaries and externally maintained knowledge.
- Guardrails do not guarantee semantic safety. Deterministic authorization is enforced separately from model instructions.
- Feedback arrows involving changing business goals or policies are human processes, supported by reports and templates. They are not silently automated.

