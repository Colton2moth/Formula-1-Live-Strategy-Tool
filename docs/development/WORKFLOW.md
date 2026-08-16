# Development Workflow

How changes should be developed, separate from how the project is installed or
started (see [SETUP.md](./SETUP.md)).

## For every task

1. Discuss the purpose.
2. Define the input and output.
3. Choose the simplest design.
4. Implement one small piece.
5. Run it.
6. Inspect the result.
7. Commit the change.
8. Continue only when the current piece is understood.

## Prompt format

Use prompts like:

```text
Explain the next smallest step for implementing the historical downloader.
Do not write code yet.
Keep the answer concise.
```

Then:

```text
Implement only the first function we discussed.
Do not modify other files.
Keep it under 50 lines.
Explain how I can test it.
```

## Commit size

Each commit should represent one understandable change.

Examples:

```text
add OpenF1 sessions request
save sessions response to JSON
add request delay
skip completed downloads
```

Avoid commits such as:

```text
build complete ingestion pipeline
```

## Complexity check

Before accepting a solution, ask:

- Is every function necessary now?
- Is there a simpler version?
- Is this handling a real failure?
- Do I understand the data flow?
- Can I test this piece independently?

If not, simplify it.
