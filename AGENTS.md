# Agent Instructions

The main goal is to help the developer understand the system.

## Behaviour

- Be concise and direct.
- Explain the purpose of a change before writing code.
- Work on one small task at a time.
- Do not create several files in one step.
- Do not generate large files without explicit approval.
- Keep new code under about 50 lines unless asked otherwise.
- Stop after each meaningful change so the developer can review it.
- Do not continue into the next phase automatically.

## Simplicity rules

- Prefer plain functions and simple data structures.
- Avoid classes unless they clearly improve state management.
- Avoid abstractions created for possible future needs.
- Do not add dependency injection, repositories, factories, plugins, queues, caching, or microservices without discussion.
- Do not handle extremely unlikely edge cases.
- Handle only realistic failures relevant to the current task.
- Do not optimize before there is a measured problem.
- Do not refactor unrelated code.
- Do not introduce a library when the standard library is sufficient.
- Do not write duplicate historical and live feature logic.

## Before coding

State briefly:

1. The problem being solved.
2. The input and output.
3. Where it fits in the system.
4. Why the proposed design is the simplest reasonable choice.

## After coding

State briefly:

1. What changed.
2. How to run it.
3. How to verify it.
4. What the next small step would be.

Do not write the next step unless explicitly asked.
