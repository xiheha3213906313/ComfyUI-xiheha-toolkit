# Validation and completion

Validation is proportional to the affected risk, but implementation work always needs at least syntax/import checks and targeted tests when the repository supports them.

## Build the validation set

Use commands from `COMFYUI_PLUGIN_PROJECT.md`, repository configuration, CI, and the current environment. Do not invent a passing command by skipping required setup.

1. Run the narrow regression tests for changed behavior.
2. Run the full plugin test suite.
3. Compile or parse all changed Python files and import the plugin/registry in a ComfyUI-capable environment.
4. Syntax-check or lint every changed frontend file using the project's toolchain.
5. Run static type/lint/build checks configured by the repository when relevant.
6. Review the final diff and search changed identifiers again.

## Risk-specific checks

| Area | Minimum additional evidence |
| --- | --- |
| Node contract | Registry/import plus exact declaration and return-shape tests |
| Model/latent/tensor | Identity or expected mutation, shape/batch, dtype, device, memory/offload path; GPU path if claimed |
| Filesystem/sidecar | allowed roots, nested paths, missing file, malformed file, traversal/absolute path rejection |
| Frontend | syntax plus real node creation, labels, connect/disconnect, state save/reload, execution payload |
| Async preview | rapid successive changes proving stale work cannot win |
| External plugin integration | installed compatible version and real connection path, or explicitly `not run` |
| Route | malformed JSON, wrong types, limits, errors, valid request, no sensitive path leakage |
| Breaking workflow change | migration behavior and representative old/new workflow evidence |

## Manual ComfyUI acceptance

When UI, registration, graph traversal, model loading, or execution behavior changes, restart/reload the plugin as required and verify a minimal workflow in ComfyUI. Check node search/creation, localized labels, connection types, execution, previews, saved workflow reload, upstream changes, errors, and browser console.

If a required runtime, browser, GPU, model, or optional plugin is unavailable, do not simulate success. Report it as not run and explain the missing prerequisite.

## Final report

State:

- completed behavior and files;
- tests/checks with exact commands and pass/fail counts;
- manual ComfyUI checks actually performed;
- profile/docs/version updates;
- remaining limitations or unverified environments.

Never turn “syntax passed” into “feature verified,” and never call a skipped check successful.
