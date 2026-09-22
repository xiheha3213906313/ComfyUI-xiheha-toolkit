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

During initial profile creation, ask the user to choose one level through the
three-level structured-choice procedure in
[user-input-tools.md](user-input-tools.md#three-level-validation-choice). Give
the short descriptions below and recommend `medium`, but never persist it
without an explicit answer. Record the exact model label or identifier and
current coding-agent host name exposed by the host, runtime/system context, or
user. A user-visible model selector label such as `Gemini 3.8 Flash` is
sufficient for detecting switches. If either identity is unavailable, record
`unknown`; never infer the coding agent from the selected model.

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
- when behavior changes, add or update a focused regression test that would
  fail before the change and pass after it when practical;
- review the diff and report anything not run.

If no suitable harness exists or an automated regression test would be
disproportionate, run the highest-signal practical alternative and state why
the regression test was not added. Do not treat the absence of an existing
test as evidence that testing is unnecessary.

The full suite, controlled import, and live UI are optional unless the changed risk requires them.

For a visual-only fix, opening and checking the exact affected UI state is usually higher-signal than an unrelated full Python suite. Still run changed-file syntax checks and any focused automated check that exercises the changed styling helper or state logic.

### `medium`

Default for ordinary node development. Guide the model toward relevant coverage without prescribing every command.

In addition to the baseline:

- make a compact risk-to-evidence plan before implementation;
- run targeted tests and the practical repository suite for every affected
  layer, using the selection guidance in
  [validation.md](validation.md#affected-layer-selection-for-medium);
- compile/check all affected Python and frontend modules;
- use controlled plugin import for node registration or route changes when available;
- perform only the conditional manual checks triggered by the change.

### `careful`

For unfamiliar repositories, weaker models, broad cross-layer changes, releases, difficult regressions, or when the user prioritizes confidence over time.

In addition to `medium`:

- follow project commands and environment preflight exactly;
- run the complete configured suite and repository-wide syntax checks;
- perform controlled import when applicable and cover all edge cases directly
  tied to the changed risks, including relevant boundary, compatibility,
  concurrency, and persistence behavior;
- execute the full relevant manual ComfyUI path when safe and available, or
  report it as not run with the concrete blocker;
- explicitly reconcile every cross-layer mirror and report all corrected failed attempts.

`careful` is not permission to run destructive, networked, credentialed,
high-cost GPU, migration, or user-state-disrupting checks without the required
authorization and prerequisites. Broader coverage must remain relevant to the
change.

## Risk floors

The configured level is a default, not permission to skip evidence needed for a concrete hazard. Even under `simple`, increase the task-local checks when changing:

- existing user files, batch writes, destructive operations, or migration behavior;
- public node IDs, port order/types, persisted workflow state, routes, or custom data schemas;
- frontend saved-state, workflow reload, cloning, or unsaved-draft recovery,
  including changes to state carriers or restoration precedence;
- model/tensor dtype, device, shapes, offload, precision, memory, or output quality;
- path containment, network access, authentication, secrets, or external services;
- module splits, shared-pipeline consolidation, or ownership moves that can
  change imports, registration side effects, lifecycle cleanup, or adapter
  behavior;
- concurrency where stale completion could discard newer user edits.

Risk floors are additive and local to the affected hazard. They do not promote
the whole task to `careful` or require unrelated careful-level checks.
Escalating task-local checks does not silently change the saved default. Tell
the user briefly when a risk floor causes extra validation.

## Model changes and conversation reminders

In Codex, every project-actionable user message must pass `--agent Codex` and
the current turn's trustworthy model identity to `check_project_profile.py`
before project-specific planning, inspection, commands, edits, tests, or
validation. This applies to follow-up instructions and “continue” messages in
the same conversation, not only its first task. Never copy `validation_model`
from the profile into `--model`: that would compare the saved value with itself
and make model-switch detection meaningless. If Codex exposes only a model
family, use that exact exposed value without inventing a variant. If no
trustworthy model identity is exposed, pass the literal `unknown`; the checker
treats it as unavailable and requires confirmation.

`check_project_profile.py` returns a machine-readable action inside `validation`:

- `choose_validation_strategy` with `blocking: true`: configuration is absent
  or invalid. Use the native three-level structured choice when available,
  wait for an explicit answer, and persist it.
- `confirm_validation_strategy` with `blocking: true`: models mismatch, the
  configured model is unknown, or the current model is unavailable. State the
  available model IDs and saved level, use the same three-level structured
  choice, and wait. Bind a known current model when persisting; never bind a
  guess.
- `continue` with `blocking: false`: configured and current models match. On the
  first project-related turn of a genuinely new conversation, state both the
  verified current model and saved validation level in one short non-blocking
  sentence and continue. Do not ask for confirmation. On every later
  project-actionable message, perform the check silently and continue without
  repeating the model or level.

Unknown actions or contradictory `action`/`blocking` values are blocking configuration errors; do not infer permission to edit.

It also returns `question_tool`, derived from `--agent` or the stored `validation_agent`. This is only a preferred-name hint. Before asking, follow [user-input-tools.md](user-input-tools.md) and verify the candidate against the tools actually exposed in the current mode.

A new conversation means no earlier visible turn has discussed or modified this
project. A project-actionable message requests a project-specific plan,
repository inspection or diagnosis, implementation or continuation,
node/code/config/documentation changes, commands, tests, or validation. Each
such Codex message requires a new silent check before action. General discussion
or a status-only question with no request to continue work does not. Multiple
tools within one assistant turn do not require repeated checks.

When the user's message answers a pending validation-level/model-binding
question, persist that explicit answer first; rerunning against the old binding
would create a loop. Outside the one new-conversation model-and-level reminder,
report the saved setting only when asking because of missing, mismatched, or
unverifiable identity, or when the user requests it.

Do not judge the new model as stronger or weaker unless product metadata explicitly says so. The user chooses the persistent level; task risk still determines mandatory safety evidence.

Follow the blocking-question protocol in `SKILL.md` and the dedicated
[three-level choice procedure](user-input-tools.md#three-level-validation-choice).
Use the host's native structured choice UI when available. Otherwise put the
single plain-text question in the `final` response and end the turn; do not
place it in commentary or run another command before the user's next message.
