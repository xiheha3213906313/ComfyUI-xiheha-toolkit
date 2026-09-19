# Validation and completion

Read [validation-strategies.md](validation-strategies.md) first and apply its configured level plus any task risk floors. Validation should buy confidence, not consume time mechanically.

## Plan before implementation

For `medium` and `careful`, make a compact internal plan before editing:

| Risk | Evidence | Executable now? |
| --- | --- | --- |
| Example: node registration | controlled import | yes |
| Example: persisted UI state | pure-function test plus save/reload | automated yes; live UI blocked if restart unsafe |

For `simple`, let the model select high-signal checks without producing the table unless a risk floor applies.

## Execution preflight

Before the first formal validation attempt, copy the interpreter, working directory, environment variables, and commands from `COMFYUI_PLUGIN_PROJECT.md` exactly. Do not improvise a command and correct it later when the profile already supplies one.

When paths or imports are uncertain, run:

```text
python <skill-dir>/scripts/validate_environment.py \
  --root <plugin-root> [--comfy-root <comfy-root>]
```

For a standard `<ComfyUI>/custom_nodes/<plugin>` layout, omit `--comfy-root`; the helper resolves it upward. Pass it only for a nonstandard layout or to override detection. `--plugin-root` remains a compatibility alias for `--root`.

Verify:

- the actual Python executable;
- plugin and ComfyUI roots;
- `folder_paths` resolves from the intended ComfyUI root rather than a conflicting local module;
- the plugin parent and test working directory are correct;
- the recommended test environment/command is recorded before execution.

Use the project-specific command even when the helper suggests a generic fallback. If a formal command fails because the preflight was ignored or incomplete, report that failed attempt later.

## Automated evidence by level

Always review current source, working-tree status, changed identifiers, and the final diff.

### Simple

- changed-file Python compilation or frontend syntax checks;
- directly relevant focused regression tests when present;
- `git diff --check` or equivalent;
- risk-floor checks only where the change demands them.

The model may skip the full suite, controlled import, repository-wide syntax scan, and manual UI for a low-risk task, but must list them as not run when they would normally be relevant.

### Medium

- targeted tests;
- practical full plugin suite for affected layers;
- all affected Python/frontend syntax checks;
- controlled import for node registration, root imports, or route changes;
- conditional manual checks triggered below.

### Careful

- complete configured test suite and repository-wide syntax checks;
- controlled import when applicable;
- all relevant boundary, malformed-input, compatibility, concurrency, and persistence cases;
- full applicable manual path when safe and available.

For a controlled import, use:

```text
python <skill-dir>/scripts/check_plugin_import.py \
  --root <plugin-root> [--comfy-root <comfy-root>]
```

It verifies mappings, display mappings, `WEB_DIRECTORY`, route registration, and repeated import behavior with a controlled `PromptServer.instance`. Label it **controlled import**, never real ComfyUI startup.

## Risk-specific evidence

| Area | Evidence floor |
| --- | --- |
| Node contract | Exact declaration/return tests; controlled import for registration changes |
| Model/latent/tensor | Identity or intended mutation, shape/batch, dtype, device, precision, memory/offload path; GPU path only if claimed |
| Existing/batch files | Chosen preservation and transaction policies, unknown-content round trip, failure after a partial write, retry/conflict behavior |
| Filesystem/sidecar | Allowed roots, nested/missing/malformed files, traversal and absolute-path rejection |
| Frontend state | Pure-function tests for persistence/dirty/save transitions where practical; syntax alone is insufficient |
| Async preview/save | Rapid changes proving stale completion cannot win or clear newer edits |
| External plugin | Installed compatible version and real connection, or explicitly not run |
| Route | Malformed JSON, wrong types, limits, valid request, per-item errors, no sensitive-path leakage |
| Breaking workflow change | User-approved migration plus representative old/new workflow evidence |

## Manual ComfyUI acceptance

Run only the portions triggered by the change.

Required for affected live UI/node behavior:

- node can be searched and created;
- port types/labels and core interaction work;
- browser console has no new error.

Add save/reopen only for persisted state. Add real external-plugin wiring only for that integration. Add temporary model/sidecar create/edit/failure recovery only for file-writing features.

Before restarting or refreshing ComfyUI, check for an unsaved workflow, active queue, unsaved editor state, and other user work. Never restart, refresh, clear, or overwrite that state without explicit authorization. Safe alternatives are user-approved save/restart, an independent test instance/port, or a frontend-only reload when the change truly requires no Python re-registration. If none is safe, mark live acceptance `not run` and state the blocker.

## Final report

Use these categories:

- **Passed** — exact command/check and result.
- **Failed: implementation** — still failing because of the code.
- **Failed then corrected: environment/invocation** — include every material formal command that failed before a later pass and explain why.
- **Not run** — check and missing prerequisite/blocker.

Do not hide an earlier formal failure merely because a corrected command passed. Distinguish these claims:

- “implementation completed” — code and static/automated work are done;
- “automated tests passed” — only named tests passed;
- “controlled import passed” — not a real startup;
- “live ComfyUI UI passed” — only after actual UI operation;
- “fully verified” — all relevant automated and live paths passed.

State the active validation level and any task-local risk-floor escalation. Never call skipped work successful.
