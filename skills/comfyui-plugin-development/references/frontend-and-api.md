# Frontend and local API integration

Follow the plugin's existing frontend architecture and the installed ComfyUI frontend APIs. Verify APIs from current source when version-sensitive; do not rely on old LiteGraph/ComfyUI snippets from memory.

## Frontend contract checks

- Match Python node IDs, internal port names, output slot indexes, custom types, and payload keys exactly.
- Keep display labels separate from internal names. Renaming a visible label must not accidentally rename the workflow contract.
- Preserve original lifecycle hooks by calling or composing with them. Install wrappers/widgets once with an instance marker.
- Keep module dependencies acyclic and side effects in the repository's designated entry point.
- Use the existing workflow serialization mechanism for durable state. DOM state alone disappears on reload.
- Prevent programmatic preview refreshes from queuing unintended executions unless that is explicit behavior.
- Guard async refreshes with cancellation, request identity, or monotonic sequence so stale responses cannot overwrite newer state.
- Traverse graph links defensively: missing links, deleted nodes, cycles, and optional upstream plugins are normal conditions.
- Preserve external node IDs, input names, widget names, and slot semantics verbatim; they are owned by the other plugin.
- Clean up DOM elements, listeners, observers, and timers on node removal when the current architecture requires it.

When a frontend mirror exists, adding/changing a node commonly requires updating constants, port labels, a node module/controller, entry-point dispatch, styles, state parsing, and manual workflow checks. Use the project profile to identify the actual mirrors.

## Local routes and trust boundaries

- Keep route registration idempotent if imports/reloads can occur.
- Validate JSON container types, required keys, scalar types, enum values, lengths/counts, and path safety before work.
- Return concise actionable errors without stack traces, secrets, absolute paths, or model internals.
- Put reusable parsing in a core layer; the route should adapt HTTP to that logic.
- Keep local preview APIs local. Do not add internet calls, analytics, update checks, crash reporting, or remote configuration without explicit user authorization.
- Bound scans and response sizes. Handle malformed files as user-visible per-item errors where one bad file should not terminate ComfyUI.

## Cross-layer payload audit

For each request, response, or execution UI payload, record and test:

- producer and consumer;
- exact key and JSON shape;
- empty/malformed behavior;
- serialization encoding;
- ordering and slot assumptions;
- stale-response handling;
- whether it persists in a workflow or exists only for the current execution.

JavaScript syntax checking is necessary but does not validate browser APIs, DOM layout, graph serialization, or live refresh. Those require a real ComfyUI/browser workflow check.
