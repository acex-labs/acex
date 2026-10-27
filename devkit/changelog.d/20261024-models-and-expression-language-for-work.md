---
kind: added
title: Models, checks and the expression language for workflows
audience: developer
---
`acex_devkit.models.workflows` holds the step types, the workflow graph, artifacts and the run views.
`acex_devkit.workflows` parses and evaluates the expressions steps use, such as `success_rate >= 80`,
`regex(...)`, `all(...)` and `{...}` templates. Artifacts are referenced by name, and a step's own result as
`result`. The language refuses anything outside itself and runs patterns with RE2.

`acex_devkit.workflows.check.WorkflowChecker` reports a graph's problems and warnings, and what each step can
read. The devkit now depends on `google-re2`, and `JobState` has `scheduled` and `paused`.
