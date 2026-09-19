---
name: comfyui-plugin-development
description: Develop, fix, refactor, or review ComfyUI custom-node plugins while keeping Python node contracts, frontend extensions, workflow compatibility, model behavior, documentation, and validation aligned. Use for repository-level ComfyUI plugin work; when the required project profile is absent or declined, route to the dedicated bootstrap procedure before editing.
---

# ComfyUI Plugin Development

Use this skill for ComfyUI custom-node repositories. Keep project facts outside the skill so the guidance stays portable between plugins.

## Start with the project profile

1. Find the plugin root, then run:

   ```text
   python <skill-dir>/scripts/check_project_profile.py --root <plugin-root>
   ```

2. The canonical profile is `<plugin-root>/COMFYUI_PLUGIN_PROJECT.md`.
3. If the result is `ready` or `partial`, read the whole profile before reading implementation files. Treat it as an index, not unquestionable truth: verify every fact in the area being changed against current source.
4. If the result is `missing`, `declined`, `reminder_due`, or `invalid`, read [references/project-profile-bootstrap.md](references/project-profile-bootstrap.md) and follow it exactly before editing. This is the only branch that loads the bootstrap procedure, including safe creation of a minimal root `AGENTS.md` when no project instruction file exists.
5. If the profile contradicts source, source wins for the current change. Correct the profile in the same task when the discrepancy is structural rather than transient.

Do not silently substitute README files, `AGENTS.md`, memory, or guesses for the canonical profile. Read repository instruction files as well; they can add project-specific constraints.

## Route the task

- For any code change or review, read [references/change-workflow.md](references/change-workflow.md).
- When adding or changing nodes, inputs, outputs, custom types, list nodes, lazy nodes, execution return values, model/latent data, or registrations, also read [references/node-contracts.md](references/node-contracts.md).
- When changing JavaScript, TypeScript, widgets, DOM UI, LiteGraph hooks, routes, serialization, previews, or browser/backend payloads, also read [references/frontend-and-api.md](references/frontend-and-api.md).
- Before claiming completion, read and execute [references/validation.md](references/validation.md).
- When creating or repairing the canonical profile, use [references/project-profile-schema.md](references/project-profile-schema.md) as its schema.

Load only the references that match the task, except that validation is always required for implementation work.

## Decision discipline

- Search current source, call sites, registrations, tests, workflows, and frontend references before editing.
- Make the smallest coherent change. Preserve unrelated working-tree changes and untracked files.
- Do not invent compatibility behavior, silently migrate workflow schemas, reorder ports, change public node IDs, add dependencies, alter model/device/dtype/offload behavior, or choose among materially different user-visible behaviors without authority.
- When a consequential ambiguity remains after inspection, stop and ask one focused question. State what the code proves, what remains undecidable, and which outcomes differ.
- Do not ask about facts that repository inspection can answer.
- Never claim a test, ComfyUI startup, browser interaction, GPU path, or workflow check was performed unless it actually was.

## Keep the profile current

Update `COMFYUI_PLUGIN_PROJECT.md` in the same change when the task alters stable project facts such as:

- file/directory responsibilities;
- node IDs, display names, classes, categories, inputs, outputs, hidden fields, or execution payloads;
- custom data structures or serialized state;
- frontend module mappings, external-node assumptions, routes, or payload keys;
- supported model/device/dtype behavior;
- test commands or required manual acceptance paths.

Do not update its analysis timestamp for a narrow edit unless the documented inventory was actually rechecked. Record unverified areas explicitly.
