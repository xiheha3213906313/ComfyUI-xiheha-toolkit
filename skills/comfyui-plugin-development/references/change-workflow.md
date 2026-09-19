# Safe change workflow

## 1. Establish the change contract

Restate the requested observable behavior in concrete terms: affected node or feature, inputs, outputs, workflow persistence, errors, compatibility, and explicit non-goals. Read the canonical project profile, applicable repository instructions, working-tree status, target code, helpers, tests, docs, and frontend/backend counterpart.

Search before editing:

- node IDs and display names;
- class/function names and registrations;
- input/output internal names, labels, types, and slot indexes;
- custom type names and data fields;
- route paths and payload/state keys;
- widget names and external plugin identifiers;
- tests, examples, docs, version, and changelog references.

Build a small impact list of files that must change and files that must remain unchanged.

Before implementation, read the configured validation level. For `medium` or `careful`, make a compact risk-to-evidence plan with columns such as risk, evidence, and current executability. For `simple`, the model may keep this plan implicit unless a risk floor applies. Identify unavailable UI, GPU, external-plugin, or restart checks now rather than at delivery time.

## 2. Resolve consequential ambiguity

Inspect first. Ask the user when source cannot decide an important product choice, especially:

- changing or preserving node IDs, port order/type, saved workflow state, or old workflows;
- choosing between incompatible UI behaviors or error semantics;
- adding a dependency, remote call, telemetry, migration, or fallback;
- changing model quality, precision, device placement, memory/offload, or performance tradeoffs;
- modifying another plugin or ComfyUI core;
- expanding a focused fix into a refactor.

Give the evidence and the two or three materially different outcomes. Do not make a hidden choice and do not ask questions that a repository search can answer.

## 3. Implement at the owning layer

- Node declaration/execution belongs in the node implementation.
- Reusable parsing and transformations belong in a UI-free core/helper layer.
- LiteGraph/DOM interaction and live previews belong in frontend modules.
- Local HTTP handlers validate at the server boundary and delegate reusable logic.
- Registries map stable public IDs to implementations; they should not contain feature logic.

Use a minimal patch. Preserve local style and public contracts not named by the request. Do not bulk-format, rename, upgrade dependencies, or clean unrelated files.

After a multi-file or multi-hunk patch reports failure, inspect every target before retrying. Do not assume the operation was atomic: earlier hunks may already be present. Retry only the missing hunks so partially applied content is not duplicated or reverted.

For changed behavior, add or update a regression test that would fail before the fix. Do not weaken assertions merely to accept the implementation.

If the feature writes user-owned files, stop here and follow [file-writing.md](file-writing.md) before selecting a serialization or batch-save design.

## 4. Cross-layer completion check

For every changed identifier or shape, search again and reconcile all owners/consumers:

| Change | Common mirrors to inspect |
| --- | --- |
| Node added/renamed | Python/Node registry, display mapping, frontend node ID, module dispatch, docs, tests, examples |
| Input/output changed | declaration, execution signature/return, frontend port labels, graph traversal, slot indexes, tests, saved-state assumptions |
| Custom data changed | every producer/consumer, route schema, frontend payload, fixtures, docs, profile |
| UI state changed | widget declaration, serialization, configure/load hooks, execution payload, refresh logic, tests/manual workflow |
| Route changed | registration, client, validation, response parsing, error display, security tests/docs |
| Model path changed | loader metadata, folder resolver, containment, optional loaders, missing metadata, nested paths |

## 5. Finish with evidence

Run validation from [validation.md](validation.md), review the final diff, and update user docs/changelog/version only when required by the repository policy or user-visible behavior. Update the canonical project profile for structural facts.

Report files changed, observable behavior, exact commands and results, manual checks actually performed, and remaining limitations. Separate `not run` from `failed`.
