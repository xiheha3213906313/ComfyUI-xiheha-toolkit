# Validation strategies and model binding

Validation level controls how much guidance and evidence are required. It does not reduce implementation quality, authorization boundaries, data-safety requirements, or the obligation to report failures honestly.

## Persistent configuration

The project profile frontmatter stores:

```yaml
validation_level: medium
validation_model: "exact-host-model-label-or-id"
validation_agent: "Codex"
validation_configured_at: 2026-01-01T12:00:00+08:00
```

During initial profile creation, ask the user to choose one level. Give the short descriptions below and recommend `medium` when the user has no preference. Record the exact model label or identifier and current coding-agent host name exposed by the host, runtime/system context, or user. A user-visible model selector label such as `Gemini 3.8 Flash` is sufficient for detecting switches. If either identity is unavailable, record `unknown`; never infer the coding agent from the selected model.

Persist a choice or later change with:

```text
python <skill-dir>/scripts/set_validation_strategy.py \
  --root <plugin-root> --level <simple|medium|careful> \
  [--model <host-model-label-or-id>] [--agent <coding-agent-name>]
```

When changing only the level, omit `--model` and `--agent`; the script preserves existing values. Supply both known current values during initialization or an intentional rebind. The agent name selects a question-tool candidate and does not participate in model mismatch decisions.

An explicit “for this task only” override does not edit the profile. Otherwise, a request to change validation strength updates the persistent profile without requiring a repository reparse.

Recording user-confirmed preferences, notes, a validation setting, formatting, or an obvious documentation correction in the profile is administrative maintenance and does not by itself require this gate. A profile edit that decides an uncertain contract, changes structural facts without source evidence, or accompanies implementation work is not administrative.

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

`check_project_profile.py` returns a machine-readable action inside `validation`:

- `choose_validation_strategy` with `blocking: true`: configuration is absent or invalid. Ask the user to select `simple`, `medium`, or `careful`, wait, and persist it.
- `confirm_validation_strategy` with `blocking: true`: models mismatch, the configured model is unknown, or the current model is unavailable. State the available model IDs and saved level, ask which level to use, and wait. Bind a known current model when persisting; never bind a guess.
- `continue` with `blocking: false`: configured and current models match. On the first project-related turn of a genuinely new conversation, remind the user of the saved level in one short non-blocking sentence and continue. Later tasks in that conversation continue silently.

Unknown actions or contradictory `action`/`blocking` values are blocking configuration errors; do not infer permission to edit.

It also returns `question_tool`, derived from `--agent` or the stored `validation_agent`. This is only a preferred-name hint. Before asking, follow [user-input-tools.md](user-input-tools.md) and verify the candidate against the tools actually exposed in the current mode.

A new conversation means no earlier visible turn has discussed or modified this project. A new project task is a distinct requested outcome. Follow-up messages that refine the same in-progress change do not require another check. Outside the one new-conversation reminder, report the saved setting only when asking because of missing, mismatched, or unverifiable identity, or when the user requests it.

Do not judge the new model as stronger or weaker unless product metadata explicitly says so. The user chooses the persistent level; task risk still determines mandatory safety evidence.

Follow the blocking-question protocol in `SKILL.md`: use the host's native structured choice UI when available. Otherwise put the single plain-text question in the `final` response and end the turn; do not place it in commentary or run another command before the user's next message.
