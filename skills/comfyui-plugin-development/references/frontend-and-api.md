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
- For a DOM popover that must close on clicks over the LiteGraph canvas, first test normal focus/bubble behavior. If Canvas interception prevents bubbling, listen for `pointerdown` on `document` in the capture phase, reject events contained by the trigger/popover, and remove the same handler with the same capture option on close, redraw/rebuild, and node removal.
- Treat Canvas node sizing as a lifecycle contract across `computeSize`, creation, workflow configuration, and manual resize. A long rendered title may inflate LiteGraph's native minimum width even when the body is empty; read [frontend-visual-debugging.md](frontend-visual-debugging.md) before overriding that behavior.
- Treat visible status as one state, not an append-only log. Loading, success, failure, stale/dirty, and new-input states should replace one another according to an explicit transition model unless the product intentionally presents history.

Move meaningful non-DOM state transitions into pure functions when practical, especially persisted-state parsing, dirty/clean comparison, model/config switching, index allocation, save-payload construction, partial-success reconciliation, and stale-response rejection. Test those functions with the project's JavaScript test tooling; when no tooling exists, a small dependency-free Node test is preferable to leaving all state logic for manual UI testing.

Classify frontend state:

- Persist only user choices and drafts that must survive workflow save/reload.
- Keep loading flags, errors, request sequence IDs, DOM references, timers, and transient server responses runtime-only.

For large hidden state, evaluate serialized workflow size, clone behavior, and input frequency. Use an appropriate debounce when every keystroke would repeatedly serialize long prompts or mark the graph dirty; do not delay state so long that a workflow save can miss recent edits.

## Module refactors and lifecycle smoke checks

When moving shared behavior into another ES module, identify the single declaration owner, every importer/re-exporter, and the entry point that activates it. Explicitly parse all affected files as ESM; a test that only finds a symbol name can pass with duplicate declarations or dead wiring.

Where practical, add a lightweight JavaScript harness around the actual exported functions with minimal DOM/LiteGraph stubs. Assert observable lifecycle invariants such as:

- the extension entry dispatches the intended node patch;
- repeated setup mounts or registers once per node instance;
- creation/configuration restores required state without duplicate controls;
- removal clears DOM, timers, observers, and global listeners;
- disabling an optional UI feature takes an intentional fallback path rather than masking a module-load failure.

Do not simulate a complete browser merely to obtain a green test. Browser module loading and a real ComfyUI node creation remain the evidence for actual frontend integration.

When a frontend mirror exists, adding/changing a node commonly requires updating constants, port labels, a node module/controller, entry-point dispatch, styles, state parsing, and manual workflow checks. Use the project profile to identify the actual mirrors.

## Local routes and trust boundaries

- Keep route registration idempotent if imports/reloads can occur.
- Validate JSON container types, required keys, scalar types, enum values, lengths/counts, and path safety before work.
- Return concise actionable errors without stack traces, secrets, absolute paths, or model internals.
- Put reusable parsing in a core layer; the route should adapt HTTP to that logic.
- Keep local preview APIs local. Do not add internet calls, analytics, update checks, crash reporting, or remote configuration without explicit user authorization.
- Bound scans and response sizes. Handle malformed files as user-visible per-item errors where one bad file should not terminate ComfyUI.

For async saves as well as previews:

- send an immutable snapshot;
- prevent duplicate in-flight submissions;
- do not let an older success clear edits made after its snapshot;
- reconcile per-item success/failure according to the declared batch contract;
- retain failed or newer drafts;
- use mtime/hash/version conflict detection when external writers are plausible.

Global listeners must be scoped by registered node/element ownership and removed deterministically. Use `passive: true` only when the handler never needs `preventDefault()`; passive mode is a performance/behavior declaration, not proof that other nodes are isolated.

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
