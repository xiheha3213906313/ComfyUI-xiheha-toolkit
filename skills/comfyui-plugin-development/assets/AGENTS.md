# ComfyUI plugin development entry

Before changing this repository:

1. Use the `$comfyui-plugin-development` skill.
2. Resolve the current model identity and coding-agent host from this
   conversation, then run the skill's profile checker with both `--model` and
   `--agent`. In Codex, do this silently at the start of every user message that
   requests a project plan, inspection, implementation/continuation, edit,
   command, test, or validation, including follow-ups in the same conversation.
   Do not run it for ordinary conversation or status-only questions that ask no
   work to continue. Never reuse the saved profile model as the current value.
   If Codex exposes no trustworthy model identity, pass `unknown` explicitly
   and follow the resulting confirmation flow instead of guessing.
3. Read `COMFYUI_PLUGIN_PROJECT.md` in full. If it is missing, declined, or invalid, follow the skill's project-profile bootstrap procedure before editing.
4. Recheck every affected node, port, type, route, state key, frontend mirror, test, and call site in current source. Source code wins when the profile is stale; correct stable profile facts in the same task.
5. Check the working tree and preserve existing edits and untracked files.

Keep changes minimal and verified. Do not make consequential compatibility, dependency, model-quality, precision, device, memory, workflow-schema, or public-contract decisions without user direction when source cannot resolve them.

Update `COMFYUI_PLUGIN_PROJECT.md` in the same task whenever stable project structure, node contracts, custom data, persisted state, frontend integration, routes, model behavior, or validation requirements change. Report only tests and manual checks actually performed.
