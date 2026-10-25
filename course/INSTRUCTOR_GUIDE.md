# Teaching and publication guide

## Course positioning

Use the title “Jev FDE Agent Engineering: From Customer Problem to Reliable Agent Workflow.” Describe it as a practical reference course, not an official certification or a guarantee of production readiness. The ten supplied diagrams are its learning backbone; customer discovery and delivery practices connect those diagrams to FDE work.

## Session format

Suggested 90-minute workshop: 10 minutes customer brief, 15 minutes diagram walkthrough, 20 minutes code trace, 25 minutes lab, 10 minutes failure demonstration and 10 minutes teach-back. Ask learners to explain tradeoffs before showing the reference implementation.

Use `jev lesson N` for a focused concept and `jev demo --simulate-review` for the integrated story. Explicitly call out the simulated reviewer, synthetic metrics, local ledger and trusted code template. Show the authenticated API review with separate credentials for the human-review session.

## Facilitator prompts

- Which customer assumption would invalidate this design?
- Which decision is made by the model, and which is enforced by code?
- What happens if the process stops between these two arrows?
- Who owns an exception that needs human intervention?
- What evidence would justify enabling this in a pilot?

## Publishing checklist

1. Review the README, all ten diagrams and the photo-to-code map for fidelity.
2. Add a publisher-selected license and a clear contribution policy. No license has been selected on the user's behalf.
3. Review attribution and rights for source inspirations. The supplied screenshots visibly credit @aiwithanuj; the original images are intentionally excluded from the archive. Seek permission if you intend to redistribute them or reproduce the original artwork commercially.
4. Replace example contact/ownership fields in templates with course-specific details.
5. Run the documented verification commands in a clean environment and retain their outputs.
6. Run hosted CI and container smoke tests in the publication environment. Label any unverified integration.
7. Tag a version and publish a release ZIP with a changelog, prerequisites and known limitations.
8. Pilot the course with two learners; track setup friction, unclear instructions and time to first successful run.

## Suggested GitHub release structure

Keep README as the landing page, `course/SYLLABUS.md` as the learning path and `docs/modules` as lessons. Use issues for learner questions and pull requests for labs. Keep solutions in the reference packages; learner work should be submitted in separate branches. Do not commit learner tokens or customer datasets.

This deliverable prepares the repository content. It does not publish a GitHub repository, hosted learning site or commercial course automatically.
