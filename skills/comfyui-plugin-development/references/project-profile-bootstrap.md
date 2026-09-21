# Project profile bootstrap

Read this file only when `check_project_profile.py` reports `missing`, `declined`, `reminder_due`, or `invalid`, or when the user explicitly asks to create/refresh the project profile.

## Ensure a minimal project entry

During project initialization, ensure the plugin root has an instruction entry after the user has either approved the full parse or declined it. An explicit request to initialize or parse the project already authorizes this step.

Run:

```text
python <skill-dir>/scripts/ensure_project_agents.py --root <plugin-root>
```

Handle the JSON `status` exactly:

- `created`: read the newly created root `AGENTS.md`, then continue the profile flow.
- `existing`: read the existing root `AGENTS.md` in full. Never replace, append to, normalize, or merge it automatically.
- `skipped_alternative`: an `AGENTS.override.md` or common alternative project-instruction file already exists. Read that file and do not create a competing `AGENTS.md`. If it does not route to this skill, continue because the skill is already active; do not edit it without a separate user request.
- `error`: stop initialization and report the actionable error. Do not work around it by overwriting or choosing another root.

The created file is copied from `assets/AGENTS.md`. Keep that template generic: project inventory belongs in `COMFYUI_PLUGIN_PROJECT.md`, not in the entry file. Create the entry even when the user declines the full parse, because it is what routes a later project task back to the declined-profile reminder policy.

## Conversation and reminder rules

The canonical file is `COMFYUI_PLUGIN_PROJECT.md` at the plugin root.

### Choose validation strategy

During initial profile creation, use the
[three-level structured-choice procedure](user-input-tools.md#three-level-validation-choice)
to ask the user to choose `simple`, `medium`, or `careful`, using the
descriptions in [validation-strategies.md](validation-strategies.md). Recommend
`medium`, but do not select or persist it without an explicit answer. When the
native UI supports multiple independent fields, this choice may accompany the
parse-consent question to avoid an extra round trip; keep it as a separate
field so one answer is never inferred from the other.

Record the selection, exact current model label or identifier, current coding-agent host name, and current local timestamp in the profile frontmatter. Pass the model and agent to `set_validation_strategy.py` with `--model` and `--agent`. If either identity is unavailable, record `unknown`; an unknown model disables automatic model-mismatch detection, while an unknown agent forces live tool discovery. A declined profile still records this configuration.

### Missing or invalid profile

Do not begin a broad parse without notifying the user unless the current request explicitly asks for project parsing or profile creation.

Use product-provided model metadata when available; never guess a tier from a model name:

- If the current model is explicitly described as flagship, premium, high-capability, or high-cost, explain that a full repository parse is recommended and suggest switching to a capable value/cost-efficient coding model for this one-time indexing task. Ask whether to parse now with the current model or defer.
- If the current model is explicitly described as value/cost-efficient, say that the full project parse is recommended and ready to begin, then ask whether to proceed now. Make clear that the user may decline, and wait for the answer.
- If no reliable tier metadata is available, do not claim a tier. Say the parse is recommended and ask whether to proceed.

If the user explicitly requested profile creation in the current request, that is consent: parse now without asking again.

### Declined profile

A declined profile is valid only when its frontmatter contains `profile_status: declined`, `declined_at`, and `remind_after`.

- Before `remind_after`, do not repeat the reminder. Perform only the focused inspection needed for the current task.
- On or after `remind_after`, remind the user only on the first project-related turn of a genuinely new conversation. A new conversation means no earlier turn in the visible conversation has already discussed or modified this project. Never interrupt an ongoing conversation with the reminder.
- Ask once. If the user declines again, update `declined_at` to the current local ISO-8601 timestamp and `remind_after` to exactly three days later in the same local timezone.
- If you cannot determine whether the conversation is new, do not remind automatically.

### Recording a refusal

Create the canonical file even when parsing is declined. Use the schema reference, but keep it minimal:

```yaml
---
profile_schema: comfyui-plugin-project/v1
profile_status: declined
project_name: unknown
analyzed_at: null
declined_at: 2026-01-01T12:00:00+08:00
remind_after: 2026-01-04T12:00:00+08:00
analysis_scope: none
validation_level: medium
validation_model: "exact-host-model-label-or-id"
validation_agent: "Codex"
validation_configured_at: 2026-01-01T12:00:00+08:00
---
```

Below the frontmatter, record a concise paraphrase of the refusal and state that no repository inventory has been completed. Do not copy sensitive text unnecessarily. Do not fabricate project facts.

## Full parsing procedure

Read [project-profile-schema.md](project-profile-schema.md) before creating the file.

1. Complete “Ensure a minimal project entry,” then read every applicable `AGENTS.md` or equivalent instruction file and check the working-tree status. Existing edits are user work.
2. Identify the actual plugin root and ComfyUI integration style. Do not assume every plugin uses legacy class mappings; inspect for classic mappings, node-list APIs, lazy registration, web-only extensions, or mixed approaches.
3. Inventory files with fast search, excluding generated caches, dependencies, environments, model weights, build output, and VCS internals.
4. Read the root registration/entry files, package metadata, every node implementation, shared helpers used by nodes, server routes, frontend entry/modules, tests, user docs, and release/version files. For a large repository, read all registries and summarize feature modules, then deeply inspect the modules needed to establish each public contract.
5. Search globally for every node ID, class, input/output name, custom type, route, payload key, widget name, serialized state key, and external node identifier before recording it.
6. Record facts using the canonical schema. Mark uncertain, environment-dependent, and unverified behavior explicitly.
7. Run safe, repository-supported inventory or contract checks when available. A successful static parse is not a successful ComfyUI runtime check.
8. Set `profile_status: complete` only when all public node registrations and integration surfaces have been inventoried. Otherwise use `partial` and list exactly what remains.
9. Set `analyzed_at` to the actual local ISO-8601 timestamp and `analysis_scope` to a truthful summary such as `full-static` or `partial-static`.

After creating the profile, continue the user's original task. Do not treat profile creation as permission to change plugin behavior.
