# Phase 3 Real Runtime Validation Readiness Remediation Checklist

Status: Pre-test gate document  
Audience: Nova, Jarvis, Alex  
Purpose: Resolve readiness blockers before starting the real Nova -> Jarvis minimal runtime validation

## Control Statement

Do not start the real Hello World runtime validation yet.

The previous readiness check returned `not ready`. The real validation must remain blocked until Nova and Jarvis complete this checklist with concrete values and proof from the active runtime environment.

This checklist is for readiness remediation only. It is not authorization to execute the runtime case.

Only after Alex reviews the completed checklist and explicitly says `proceed` may Nova send the real command and Jarvis begin execution.

## Operating Rules

- Do not answer with assumptions.
- Do not answer only from file presence.
- Answer from the active runtime environment that will actually be used for the real Nova -> Jarvis validation.
- If an item cannot be proven, mark it as `not proven`.
- Nova must not send the real command yet.
- Jarvis must not self-initiate and must not simulate Nova-start.

## Scope of the Future Runtime Case

This readiness checklist supports a bounded Phase 3 minimal runtime case whose target is:

- Alex issues the command
- Nova is the real initiator
- Jarvis waits for Nova's actual command
- Jarvis generates `hello-world.html`
- Runtime evidence is retained
- Alex manually reviews the result

This checklist does not authorize:

- real human notification
- real review backend
- timeout/retry/DLQ expansion
- Phase 4+ work
- abnormal-path testing

## Checklist

### 1. Broker / NATS

1. Exact NATS server address
- State the exact broker endpoint that will be used.
- Example format: `nats://192.168.31.64:4222`

Required response:
- broker endpoint:
- local or remote:
- default or override:
- both agents confirmed same endpoint: yes / no / not proven

2. Broker reachability
- Verify the chosen endpoint is reachable from the actual runtime environment.

Required response:
- reachable: yes / no
- connection method used:
- result:

3. JetStream
- Verify JetStream is enabled on that exact broker.

Required response:
- jetstream available: yes / no
- proof:
- stream initialization tested: yes / no
- initialization result:

4. Python NATS dependency
- Verify whether `nats-py` is installed in the actual runtime environment that will run the test.

Required response:
- `nats-py` installed in active runtime: yes / no
- version if present:
- proof method:
- if missing, remediation plan:

5. Real adapter readiness
- Verify whether the real NATS adapter can initialize successfully in the actual runtime.

Required response:
- real adapter initialization success: yes / no
- adapter class tested:
- exact result:
- blocker if failed:

### 2. Code / Repository State

6. Exact repository path
- State the exact repo path used by the active runtime.

Required response:
- repo path:

7. Exact branch
- State the exact branch that will be used for the real validation.

Required response:
- branch name:

8. Exact commit
- State the exact commit hash that will be used for the real validation.

Required response:
- commit hash:

9. Branch/commit alignment
- Confirm Nova and Jarvis are running against the same branch and commit.

Required response:
- Nova branch:
- Nova commit:
- Jarvis branch:
- Jarvis commit:
- aligned: yes / no

10. Local change state
- Confirm whether there are local uncommitted changes that affect the runtime path.

Required response:
- local changes present: yes / no
- affected files:
- impact on validation:

### 3. Config / Identity Loading

11. Config source actually loaded
- State which config file is actually loaded into the active runtime.
- Do not answer from repo file presence alone.

Required response:
- loaded config source:
- proof that it is loaded:

12. Nova runtime identity
- Provide the actual active runtime identity values for Nova.

Required response:
- agent_id:
- role:
- runtime_instance_id:
- authority_scopes:
- trusted_subject_prefixes:
- proven in active runtime: yes / no

13. Jarvis runtime identity
- Provide the actual active runtime identity values for Jarvis.

Required response:
- agent_id:
- role:
- runtime_instance_id:
- authority_scopes:
- trusted_subject_prefixes:
- proven in active runtime: yes / no

14. Identity mapping agreement
- Confirm both sides agree how Nova and Jarvis map onto the runtime identities used for this test.

Required response:
- Nova identity mapping:
- Jarvis identity mapping:
- agreement confirmed: yes / no

### 4. Routing / Subjects

15. Routing model
- State which routing model will be used in the real test.
- Choose one only.

Required response:
- routing model:
  - `gov.collab.*`
  - or `agent.{id}.inbox / agent.{id}.callbacks`
- reason for chosen model:

16. Publish subject
- State the exact subject Nova will publish to.

Required response:
- publish subject:

17. Consume subject
- State the exact subject Jarvis will consume from.

Required response:
- consume subject:

18. Callback/reply subject
- State the exact callback or reply subject if used.

Required response:
- callback/reply subject:

19. Trust-rule alignment
- Confirm the chosen subjects are permitted by the active trust rules.

Required response:
- trust-rule alignment: yes / no
- proof:

20. Active subscription proof
- Prove that the receiving runtime is actually subscribed to the intended consume subject.

Required response:
- receiver subscribed: yes / no
- proof:

### 5. Runtime Process State

21. Nova sender/runtime process
- Confirm whether a real Nova sender/runtime process is active.

Required response:
- Nova runtime active: yes / no
- how started:
- how verified:

22. Jarvis receiver/runtime process
- Confirm whether a real Jarvis receiver/runtime process is active.

Required response:
- Jarvis runtime active: yes / no
- how started:
- how verified:

23. Listener/runtime readiness
- Confirm the Jarvis receiver is not just present in code, but operationally ready.

Required response:
- listener active: yes / no
- attached broker:
- active consume subject:
- ready to prove actual receipt: yes / no

24. Synthetic-vs-real protection
- Explain how this run will distinguish actual broker-delivered receipt from local synthetic execution.

Required response:
- actual-receipt proof method:

### 6. Test Contract

25. Command contract
- State the exact command type/message family to be used.

Required response:
- command family/type:
- minimum required fields:
- sender identity fields:
- target identity fields:

26. Artifact output
- State the exact artifact path to be used for `hello-world.html`.

Required response:
- artifact output path:
- writable: yes / no
- reviewable by Alex afterward: yes / no

27. Required evidence
- Confirm the exact evidence items that will be returned.

Required response:
- proof of Nova initiation:
- proof of Jarvis receipt:
- command/dispatch evidence:
- `active_wait_record`:
- `review_task_publication_record`:
- artifact reference:
- any additional evidence:

28. Pass/fail rule
- State the exact pass/fail rule for this real validation.

Required response:
- pass condition:
- fail condition:

### 7. Scope and Start Conditions

29. Scope boundary confirmation
- Confirm this run will remain within bounded Phase 3 scope only.

Required response:
- bounded Phase 3 only: yes / no
- no real human notification: yes / no
- no real review backend: yes / no
- no timeout/retry/DLQ expansion: yes / no
- no Phase 4+ work: yes / no
- no abnormal-path testing: yes / no

30. Start condition confirmation
- Confirm the exact start rule for this validation.

Required response:
- Nova is the real initiator: yes / no
- Jarvis will not self-initiate: yes / no
- Jarvis will execute only after actual Nova command receipt: yes / no
- Jarvis will return blocked if no real Nova command is received: yes / no

### 8. Final Readiness Decision

31. Overall readiness
- Give one final readiness verdict.

Required response:
- overall readiness: `ready` / `not ready`

32. Remaining blockers
- List every remaining blocker, if any.

Required response:
- blockers:

33. Remediation status
- If not ready, state exactly what must still be fixed before Alex can authorize the runtime test.

Required response:
- required remediation steps:

## Required Return Format

Nova and Jarvis must return the completed checklist to Alex in one structured response containing:

- overall readiness
- broker endpoint
- NATS connectivity result
- JetStream result
- adapter mode
- loaded config source
- Nova identity summary
- Jarvis identity summary
- subject routing summary
- message contract summary
- push/pull readiness
- Jarvis listener/runtime readiness
- artifact output path
- evidence readiness summary
- scope confirmation
- start condition confirmation
- blockers, if any

## Execution Rule

Do not start the actual runtime validation until Alex reviews the checklist response and explicitly says to proceed.

