# Validation and completion

Read [validation-strategies.md](validation-strategies.md) first and apply its configured level plus any task risk floors. Validation should buy confidence, not consume time mechanically.

## Plan before implementation

For `medium` and `careful`, make a compact internal plan before editing:

| Risk | Evidence | Executable now? |
| --- | --- | --- |
| Example: node registration | controlled import | yes |
| Example: persisted UI state | pure-function test plus save/reload | automated yes; live UI blocked if restart unsafe |

For `simple`, let the model select high-signal checks without producing the table unless a risk floor applies.

Choose evidence for the claims that matter. Prefer one direct, high-signal
check over several low-signal checks that prove the same fact. Add overlapping
checks only when a risk, regression history, or the `careful` level makes the
independent evidence valuable.

When validation requires environment diagnosis, a portable unittest wrapper, explicit ESM parsing, or controlled plugin import, read [validation-tooling.md](validation-tooling.md). Do not load that tool reference for a documentation-only change or a simple check whose exact project command is already known.

## Automated evidence by level

Always review current source, working-tree status, changed identifiers, and the final diff.

### Simple

- changed-file Python compilation or explicit-ESM frontend syntax checks;
- for changed behavior, a focused regression test that fails before the change
  and passes after it when practical;
- `git diff --check` or equivalent;
- risk-floor checks only where the change demands them.

When a suitable automated harness is unavailable or disproportionate, use the
highest-signal practical alternative and state why no regression test was
added. The model may skip the full suite, controlled import, repository-wide
syntax scan, and manual UI for a low-risk task. List only omitted checks that
would have been plausible evidence for the changed surface; do not produce an
inventory of every validation that could exist.

### Medium

- targeted tests;
- practical full plugin suite for affected layers;
- all affected Python/frontend syntax checks;
- controlled import for node registration, root imports, or route changes;
- conditional manual checks triggered below.

#### Affected-layer selection for medium

Use the changed surface to select coverage rather than running every available
check:

| Changed surface | Minimum medium evidence |
| --- | --- |
| Python logic only | Focused regression test, affected Python compile, and the practical related Python suite |
| Frontend logic only | Explicit ESM parse, relevant state/helper test when practical, and the affected live UI path when available |
| Node registration or local route | Relevant Python tests, affected syntax, controlled import, and route/contract checks |
| Frontend and backend contract | Targeted evidence on both sides plus request/response or state-shape compatibility |
| Visual-only styling | Explicit ESM parse and the exact affected visual state; do not run unrelated Python suites |

Add risk-floor evidence only for hazards present in the change. This table is a
minimum selection guide, not a reason to omit a more direct project-specific
check recorded in the profile.

### Careful

- complete configured test suite and repository-wide syntax checks;
- controlled import when applicable;
- all boundary, malformed-input, compatibility, concurrency, and persistence
  cases directly relevant to the changed risks;
- full applicable manual path when safe and available, otherwise reported as
  not run with the concrete prerequisite or blocker.

Do not run destructive, networked, credentialed, migration, high-cost GPU, or
user-state-disrupting checks merely because the level is `careful`. Apply the
normal authorization and restart-safety rules.

## Failure classification and retry

When a formal validation attempt fails, classify it before retrying:

- implementation failure — fix the implementation, then rerun the same
  relevant evidence;
- environment or invocation failure — correct the identified interpreter,
  working directory, environment, or command once, then rerun;
- unavailable prerequisite or unsafe execution — stop and report the check as
  not run rather than improvising around the boundary.

Do not cycle through commands speculatively. Retry after a concrete correction;
if the same cause remains, preserve the failure evidence and report it. Every
material failed formal attempt remains part of the final report even if a
later corrected command passes.

## Risk-specific evidence

| Area | Evidence floor |
| --- | --- |
| Node contract | Exact declaration/return tests; controlled import for registration changes |
| Model/latent/tensor | Identity or intended mutation, shape/batch, dtype, device, precision, memory/offload path; GPU path only if claimed |
| Existing/batch files | Chosen preservation and transaction policies, unknown-content round trip, failure after a partial write, retry/conflict behavior |
| Filesystem/sidecar | Allowed roots, nested/missing/malformed files, traversal and absolute-path rejection |
| Frontend state | Pure-function tests for persistence/dirty/save transitions where practical; verify programmatic updates reach serialization, restored values survive incomplete initial options, and stale creation-time requests cannot overwrite configured state; syntax alone is insufficient |
| Frontend module split | Explicit ESM parse, moved-symbol ownership search, entry-point import/patch smoke check |
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
- **Partial evidence** — the check succeeded within a named limited scope, but the registration/runtime path was not fully exercised.
- **Failed: implementation** — still failing because of the code.
- **Failed then corrected: environment/invocation** — include every material formal command that failed before a later pass and explain why.
- **Not run** — check and missing prerequisite/blocker.

Do not hide an earlier formal failure merely because a corrected command passed. Distinguish these claims:

- “implementation completed” — code and static/automated work are done;
- “automated tests passed” — only named tests passed;
- “controlled import passed” — not a real startup;
- “live ComfyUI UI passed” — only after actual UI operation;
- “fully verified” — all relevant automated and live paths passed.

State the active validation level and any task-local risk-floor escalation.
Risk-floor evidence is local to the affected hazard and does not automatically
activate every `careful` check. Never call skipped work successful.
