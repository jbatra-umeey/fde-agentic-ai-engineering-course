# The FDE engagement playbook

An FDE carries a customer problem through discovery, integration, implementation and adoption. The customer buys an outcome, so the engineering explanation must connect each design decision to that outcome.

## 1. Discover before coding

Observe the current workflow with its actual operators. Capture trigger, inputs, manual decisions, systems, exceptions, output, volume and owner. Ask what happens when the task is wrong, slow or incomplete. Separate the buyer's goal from the end user's daily work.

Example: an engineering team wants faster regression triage. A useful initial scope is “assemble evidence and propose a ticket for a reviewer,” not “autonomously fix production.” Agree on a baseline triage-time sample, quality rubric and maximum acceptable false escalation rate. Record these as proposed metrics until measured.

## 2. Negotiate a narrow first delivery

Choose one workflow, one customer group and one operational environment. List explicit non-goals. Confirm who can approve data access, provide integration credentials, review proposed actions and own the pilot. Keep a dependency/risk register with an accountable owner and date.

Deliver the thinnest complete slice: input → evidence → decision → reviewed action → observable result. This slice must include failure behavior. Use synthetic data until the customer grants access to real data.

## 3. Integrate at business boundaries

Ask for API contracts, service limits, error semantics, authentication and data classification. Map identities and permissions; do not make the model infer them. Verify whether the downstream service supports idempotency, optimistic concurrency and audit references.

If a write can time out after succeeding, define a reconciliation strategy before enabling retries. For a payment or ticket service, use an outbox and a stable business operation key. Record the external operation ID in the durable ledger.

## 4. Make delivery observable

Demonstrate one successful run and one failed run at every milestone. Show the evidence used, tools invoked, reviewer decision and final effect. Pair metrics with examples: an aggregate pass rate cannot explain a costly failure.

Log the question you were trying to answer and the evidence you collected. Share small decision records with the customer so they can challenge assumptions before those assumptions become architecture.

## 5. Validate adoption, not only model quality

Ask operators to complete representative tasks in a pilot. Measure time to reviewed completion, accepted proposal rate, correction effort and false escalations. Include the time spent supervising the agent. Compare against the measured baseline with the same task mix.

Identify operational bottlenecks: reviewer queues, unavailable documents, permissions, integration latency and unclear escalation ownership may matter more than changing models.

## 6. Handover deliberately

Give the customer a runbook, access matrix, deployment record, rollback procedure, evaluation report and known limitations. Test restart, restore, failed integration and expired approval scenarios with their operators. Agree on support hours, incident severity, ownership and change approval.

A handover is complete when the receiving team can run and diagnose the workflow without its original author. Avoid promises such as “production ready” unless the deployment-specific acceptance evidence supports them.

## Portfolio demonstration: 7 minutes

1. 0:00–1:00: customer problem, baseline and scope.
2. 1:00–2:00: diagram and trust boundaries.
3. 2:00–4:00: end-to-end workflow and human review.
4. 4:00–5:00: intentional failure and recovery.
5. 5:00–6:00: evaluation report and operating signals.
6. 6:00–7:00: tradeoffs, deployment evidence, remaining gaps and next milestone.
