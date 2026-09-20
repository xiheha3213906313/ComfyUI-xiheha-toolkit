---
name: comfyui-plugin-development
description: Develop, fix, refactor, or review ComfyUI custom-node plugins while keeping Python node contracts, frontend extensions, workflow compatibility, model behavior, documentation, and validation aligned. Use for repository-level ComfyUI plugin work; when the required project profile is absent or declined, route to the dedicated bootstrap procedure before editing.
---

# ComfyUI Plugin Development

Use this skill for ComfyUI custom-node repositories. Keep project facts outside the skill so the guidance stays portable between plugins.

## Skill-maintenance boundary

When the task changes only this skill's instructions, references, helper scripts, assets, metadata, or skill-specific tests, this skill's ComfyUI project workflow does not govern that work. Do not run its project-profile check, model-binding gate, validation-level prompt, plugin preflight, ComfyUI test matrix, or profile synchronization merely because the skill is stored inside a plugin repository. Use the host's skill-authoring instructions and the user's current request instead, then validate the skill as a skill.

Read [references/skill-maintenance.md](references/skill-maintenance.md) before iterating on this skill. That procedure explains how to evaluate usage feedback, reject overfitted or incorrect proposals, organize instructions, update helpers, and validate the package.

This exemption is scope-based, not repository-wide. If one request changes both the skill and plugin behavior or project facts, use the skill-maintenance procedure for the skill portion and apply the normal project gate before the plugin portion. Never let editing the skill silently authorize changes to the plugin, project profile, dependencies, external systems, or user data.

## Start with the project profile

1. Find the plugin root. Obtain both the current model label/identifier and the current coding-agent host name from host UI, product/runtime metadata, system context, or an explicit user statement. Pass them to the checker; the shell script cannot inspect the conversation runtime. Preserve host-provided values exactly, never infer a model from capability, and never infer the coding agent from the model vendor. Then run:

   ```text
   python <skill-dir>/scripts/check_project_profile.py --root <plugin-root> \
     --model <host-model-label-or-id> --agent <coding-agent-name>
   ```

   Omit either optional argument when that value is not trustworthy. The returned `question_tool` is a candidate-resolution hint, not proof that a tool is callable in the current mode.

2. The canonical profile is `<plugin-root>/COMFYUI_PLUGIN_PROJECT.md`.
3. If the result is `ready` or `partial`, read the whole profile before reading implementation files. Treat it as an index, not unquestionable truth: verify every fact in the area being changed against current source.
4. If the result is `missing`, `declined`, `reminder_due`, or `invalid`, read [references/project-profile-bootstrap.md](references/project-profile-bootstrap.md) and follow it exactly before editing. This is the only branch that loads the bootstrap procedure, including safe creation of a minimal root `AGENTS.md` when no project instruction file exists.
5. If the profile contradicts source, source wins for the current change. Correct the profile in the same task when the discrepancy is structural rather than transient.

The validation gate applies before plugin implementation or behavioral changes, including a small edit to an existing node. A profile-only administrative edit does not trigger it when the user has already supplied or confirmed the exact content and the edit only records preferences, notes, validation configuration, formatting, or an obvious documentation correction. Read the current profile and preserve unrelated content, but do not ask for a validation level solely to record that information. If the edit changes a source-backed structural fact, resolves an uncertain contract, or accompanies code/runtime changes, apply the normal gate.

For gated work, follow the returned `validation.action` instead of reconstructing the state from prose:

- `choose_validation_strategy`: explain `simple`, `medium`, and `careful`, ask once, stop, then persist the answer and a trustworthy current model with `scripts/set_validation_strategy.py`.
- `confirm_validation_strategy`: state the configured/current models and saved level, ask which level to use, and stop. Persist the answer with the current model when its identity is trustworthy; never bind a guessed identifier.
- `continue`: on the first project-related turn of a genuinely new conversation, briefly remind the user of the active level and continue without pausing. Later tasks in that conversation continue silently.

A missing or invalid profile has no usable validation action; the bootstrap procedure collects the choice instead. Treat an unknown action as blocking and read [references/validation-strategies.md](references/validation-strategies.md) before proceeding.

A new conversation means no earlier visible turn has discussed or modified this project. A new project task is a distinct requested outcome, not every follow-up message within the same ongoing change. Run the gate once at task start; do not re-run it silently for each message. If the model was unverifiable and the user confirms a level, do not repeat the question within that task. Read [references/validation-strategies.md](references/validation-strategies.md) for the action contract, selection, persistence, overrides, and risk floors.

Do not silently substitute README files, `AGENTS.md`, memory, or guesses for the canonical profile. Read repository instruction files as well; they can add project-specific constraints.

## Route the task

- For any code change or review, read [references/change-workflow.md](references/change-workflow.md).
- When adding or changing nodes, inputs, outputs, custom types, list nodes, lazy nodes, execution return values, model/latent data, or registrations, also read [references/node-contracts.md](references/node-contracts.md).
- When changing JavaScript, TypeScript, widgets, DOM UI, LiteGraph hooks, routes, serialization, previews, or browser/backend payloads, also read [references/frontend-and-api.md](references/frontend-and-api.md).
- When diagnosing ComfyUI theme colors, popup seams, DOM-over-canvas appearance, node whitespace, or DOM widget sizing, also read [references/frontend-visual-debugging.md](references/frontend-visual-debugging.md).
- Before claiming completion, read and execute [references/validation.md](references/validation.md).
- When a task reads, rewrites, saves, creates, or batch-updates user-owned files, also read [references/file-writing.md](references/file-writing.md).
- When creating or repairing the canonical profile, use [references/project-profile-schema.md](references/project-profile-schema.md) as its schema.

Load only the references that match the task, except that validation is always required for implementation work.

## Decision discipline

- Search current source, call sites, registrations, tests, workflows, and frontend references before editing.
- Make the smallest coherent change. Preserve unrelated working-tree changes and untracked files.
- Do not invent compatibility behavior, silently migrate workflow schemas, reorder ports, change public node IDs, add dependencies, alter model/device/dtype/offload behavior, or choose among materially different user-visible behaviors without authority.
- When a consequential ambiguity remains after inspection, stop and ask one focused question. State what the code proves, what remains undecidable, and which outcomes differ.
- Do not ask about facts that repository inspection can answer.
- Never claim a test, ComfyUI startup, browser interaction, GPU path, or workflow check was performed unless it actually was.

### Blocking question protocol

Any question whose answer can change the implementation, scope, compatibility, validation choice, or user-visible behavior is blocking.

Before asking, read [references/user-input-tools.md](references/user-input-tools.md) and resolve the actual user-input tool from the current tool inventory. A configured or mapped tool name never overrides its live availability, mode restrictions, or permission-specific approval mechanisms.

1. If the coding host exposes a native structured question/choice UI in the current mode, use it. Do not substitute a normal chat question merely because it is easier. Continue only when the tool returns an explicit user answer.
2. If a native wait times out but the question is still visible, pending, or its closure state is unknown, do not send a duplicate chat question. Make no command or edit, end the turn with at most a brief waiting-status statement, and accept the answer through the still-active UI or a later user message.
3. If the native tool explicitly reports cancellation, closure, expiration with no pending prompt, or an empty result that cannot still be answered, fall back once to the same decision as one concise plain-text question in the `final` response, then end the turn. A timeout alone is not proof that the UI prompt expired.
4. If no native question UI is available or it failed before displaying the question, use the same plain-text fallback. Necessary evidence and consequences may precede the question in that response, but the question must be the last thing sent.
5. A plain-text blocking question must not be sent in `commentary`, because commentary does not end the turn. After deciding to send it, make no further tool calls, commands, edits, or implementation assumptions. The host waits for the user's next message; resume only in that later turn.
6. Use multiple question rounds when one round cannot resolve every material decision or when a later question depends on an earlier answer. With a native UI, ask the next dependent question only after the previous answer returns. With plain text, ask one focused question per turn, end the turn, then ask the next question after the user's reply. Do not begin implementation until all blocking decisions are resolved.
7. If a reply is partial or ambiguous, ask one narrower follow-up and stop again. Never treat a partial answer as authorization for the remaining choices or select an answer on the user's behalf.
8. Use a dedicated approval mechanism for permission or privilege escalation when the host provides one; do not replace it with the normal question UI.

## Keep the profile current

Update `COMFYUI_PLUGIN_PROJECT.md` in the same change when the task alters stable project facts such as:

- file/directory responsibilities;
- node IDs, display names, classes, categories, inputs, outputs, hidden fields, or execution payloads;
- custom data structures or serialized state;
- frontend module mappings, external-node assumptions, routes, or payload keys;
- supported model/device/dtype behavior;
- test commands or required manual acceptance paths.

Do not update its analysis timestamp for a narrow edit unless the documented inventory was actually rechecked. Record unverified areas explicitly.
