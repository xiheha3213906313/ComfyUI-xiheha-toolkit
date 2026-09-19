# Validation strategies and model binding

Validation level controls how much guidance and evidence are required. It does not reduce implementation quality, authorization boundaries, data-safety requirements, or the obligation to report failures honestly.

## Persistent configuration

The project profile frontmatter stores:

```yaml
validation_level: medium
validation_model: exact-host-model-label-or-id
validation_configured_at: 2026-01-01T12:00:00+08:00
```

During initial profile creation, ask the user to choose one level. Give the short descriptions below and recommend `medium` when the user has no preference. Record the exact model label or identifier exposed by the host, runtime/system context, or user; a user-visible selector label such as `Gemini 3.8 Flash` is sufficient for detecting switches. If none is trustworthy, record `unknown` and say model matching cannot be enforced.

Persist a choice or later change with:

```text
python <skill-dir>/scripts/set_validation_strategy.py \
  --root <plugin-root> --level <simple|medium|careful> [--model <host-model-label-or-id>]
```

When changing only the level, omit `--model`; the script preserves the existing binding. Supply `--model` when creating the validation configuration or intentionally rebinding it. Never make the caller repeat or guess a model identifier merely to change the level.

An explicit “for this task only” override does not edit the profile. Otherwise, a request to change validation strength updates the persistent profile without requiring a repository reparse.

## Levels

### `simple`

For strong models, low-risk fixes, text/style changes, and tightly scoped edits. Let the model choose the smallest high-signal evidence.

Required baseline:

- read the profile, current target, call sites, and working-tree status;
- search changed identifiers;
- run changed-file syntax/compile checks;
- run an existing focused regression test when one is directly relevant;
- review the diff and report anything not run.

The full suite, controlled import, and live UI are optional unless the changed risk requires them.

For a visual-only fix, opening and checking the exact affected UI state is usually higher-signal than an unrelated full Python suite. Still run changed-file syntax checks and any focused automated check that exercises the changed styling helper or state logic.

### `medium`

Default for ordinary node development. Guide the model toward relevant coverage without prescribing every command.

In addition to the baseline:

- make a compact risk-to-evidence plan before implementation;
- run targeted tests and the practical repository suite for affected layers;
- compile/check all affected Python and frontend modules;
- use controlled plugin import for node registration or route changes when available;
- perform only the conditional manual checks triggered by the change.

### `careful`

For unfamiliar repositories, weaker models, broad cross-layer changes, releases, difficult regressions, or when the user prioritizes confidence over time.

In addition to `medium`:

- follow project commands and environment preflight exactly;
- run the complete configured suite and repository-wide syntax checks;
- perform controlled import plus all applicable risk-specific edge cases;
- execute the full relevant manual ComfyUI path when safe and available;
- explicitly reconcile every cross-layer mirror and report all corrected failed attempts.

## Risk floors

The configured level is a default, not permission to skip evidence needed for a concrete hazard. Even under `simple`, increase the task-local checks when changing:

- existing user files, batch writes, destructive operations, or migration behavior;
- public node IDs, port order/types, persisted workflow state, routes, or custom data schemas;
- model/tensor dtype, device, shapes, offload, precision, memory, or output quality;
- path containment, network access, authentication, secrets, or external services;
- concurrency where stale completion could discard newer user edits.

Escalating task-local checks does not silently change the saved default. Tell the user briefly when a risk floor causes extra validation.

## Model changes and conversation reminders

- Exact configured/current model match: on the first project-related turn of a genuinely new conversation, remind the user of the saved level in one short non-blocking sentence and continue. Later tasks in that conversation continue silently.
- Mismatch: before any mutation, state both model IDs and the saved level, then ask the user to select `simple`, `medium`, or `careful`. Wait for the answer and persist it with the current model.
- Unknown current model: do not claim a match. At the start of a new project task, state that the host did not expose the identifier, show the saved model/level, and ask which level to use. Wait before editing. If the user supplies a trustworthy model label/ID, persist it; otherwise retain the existing binding and do not repeat the question within that task.
- Unknown configured model with a known current model: ask once to bind the existing or newly selected level to the known model, then persist it.

A new conversation means no earlier visible turn has discussed or modified this project. A new project task is a distinct requested outcome. Follow-up messages that refine the same in-progress change do not require another check. Outside the one new-conversation reminder, report the saved setting only when asking because of missing, mismatched, or unverifiable identity, or when the user requests it.

Do not judge the new model as stronger or weaker unless product metadata explicitly says so. The user chooses the persistent level; task risk still determines mandatory safety evidence.

Use the host's native structured choice UI when available. Once a blocking question has been sent, no project command or edit may run until the user response is returned. With a plain-text question, end the turn immediately.
