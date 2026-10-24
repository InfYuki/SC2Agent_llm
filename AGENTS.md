# Task completion

- Before finishing each task, remove temporary files created for that task and safe generated caches. Prefer the repository cleanup tool when available; inspect its dry run first.
- Keep deletion within the resolved repository path. Never treat the entire `artifacts/` directory as temporary.
- Preserve training data, model weights, checkpoints, replays, raw match records, learning memories, evidence and formal reports, dependency environments, useful tools, and private configuration.
- Do not repeatedly run broad test suites just to clean up. Run checks appropriate to the changes, then clean their temporary output.
