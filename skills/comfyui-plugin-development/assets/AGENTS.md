# ComfyUI plugin development entry

Before changing this repository:

1. Use the `$comfyui-plugin-development` skill.
2. Read `COMFYUI_PLUGIN_PROJECT.md` in full. If it is missing, declined, or invalid, follow the skill's project-profile bootstrap procedure before editing.
3. Recheck every affected node, port, type, route, state key, frontend mirror, test, and call site in current source. Source code wins when the profile is stale; correct stable profile facts in the same task.
4. Check the working tree and preserve existing edits and untracked files.

Keep changes minimal and verified. Do not make consequential compatibility, dependency, model-quality, precision, device, memory, workflow-schema, or public-contract decisions without user direction when source cannot resolve them.

Update `COMFYUI_PLUGIN_PROJECT.md` in the same task whenever stable project structure, node contracts, custom data, persisted state, frontend integration, routes, model behavior, or validation requirements change. Report only tests and manual checks actually performed.
