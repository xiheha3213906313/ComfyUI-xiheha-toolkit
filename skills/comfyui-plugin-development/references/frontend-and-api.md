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

## State ownership, programmatic changes, and restoration

Before implementing persistence, inventory every user-editable value and define
its intended boundary: current runtime only, explicitly saved workflow, or the
host's unsaved-workflow draft recovery. Assign each durable value one canonical
persistence owner: verified native widget serialization or an explicit custom
state object. Do not split related state between the two based only on an
assumption that a native-looking widget will be tracked automatically.

Programmatically assigning `widget.value` and invoking its callback proves only
that local code ran. It does not prove that workflow serialization contains the
new value, that the graph was marked changed, or that the host's draft tracker
noticed an asynchronous update. For uploads, fetch completions, generated
choices, and other updates that finish after the initiating input event:

- use the current ComfyUI-supported graph/workflow change-notification API when
  one is available, verifying it against the installed frontend source;
- keep widget value, custom serialized state, and visible UI synchronized
  through one update path;
- do not synthesize arbitrary mouse or keyboard events as the default fix;
  when a version-specific fallback is unavoidable, isolate it and test the
  actual draft behavior it is meant to trigger;
- distinguish user/programmatic changes from configuration hydration so loading
  a workflow does not immediately mark it dirty without a semantic change.

During restoration, do not assume a persisted Combo value is already present in
the widget's initial option list. Refresh or extend the valid options before
assigning the restored value, or use another representation that preserves the
contract. Never silently replace a still-valid persisted value with the first
option merely because option discovery has not completed.

Treat creation, configuration, and async refresh as one lifecycle:

- `onNodeCreated` establishes controls and safe defaults;
- `onConfigure` or the repository's equivalent restores serialized state;
- side effects started from defaults must not overwrite later restored state;
- every async completion verifies its request identity, the current selected
  value, and that the owning node/controller still exists before committing;
- restoration and user changes should call the same normalization/rendering
  path, with explicit control over persistence and dirty notification.

For any feature claiming draft or reload persistence, test the exact promised
boundary rather than only the happy path:

- make an async programmatic change and inspect the next serialized workflow
  snapshot;
- if unsaved-refresh recovery is claimed, use an isolated or otherwise safe
  test workflow, complete the update, and refresh without queueing or manually
  saving; never use the user's active unsaved workflow for this check;
- restore a value absent from the initial Combo options;
- delay the default-value request so it completes after restored-state work and
  prove that it cannot overwrite the restored value;
- save/reopen and clone the node when those behaviors are part of the contract.

If the installed ComfyUI version does not expose a reliable draft notification
path, report unsaved-refresh recovery as unsupported or not verified instead of
equating ordinary workflow serialization with host draft persistence.

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
