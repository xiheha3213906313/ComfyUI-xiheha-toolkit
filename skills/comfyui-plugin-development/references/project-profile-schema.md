# Canonical project profile schema

The file name is exactly `COMFYUI_PLUGIN_PROJECT.md` and it lives at the plugin root. It is a maintained engineering index for AI and human contributors, not a replacement for source or user documentation.

## Required frontmatter

```yaml
---
profile_schema: comfyui-plugin-project/v1
profile_status: complete
project_name: example-plugin
analyzed_at: 2026-01-01T12:00:00+08:00
declined_at: null
remind_after: null
analysis_scope: full-static
validation_level: medium
validation_model: exact-host-model-label-or-id
validation_configured_at: 2026-01-01T12:00:00+08:00
---
```

Allowed `profile_status` values:

- `complete`: all known public nodes and integration surfaces were statically inventoried.
- `partial`: useful inventory exists but named areas remain unread or unresolved.
- `declined`: the user declined the initial parse; no inventory is implied.

Dates must be ISO-8601 with timezone. Use YAML `null`, not empty strings, for inapplicable values.

`validation_level` must be `simple`, `medium`, or `careful`. `validation_model` is the exact model label or identifier exposed by the current host/runtime/system context or explicitly supplied by the user when the level was chosen; a user-visible model selector label is valid. Use `unknown` only when no trustworthy value exists. During initialization, explain all three levels and ask the user before setting them. See `validation-strategies.md`.

## Required sections for complete or partial profiles

Use these headings and omit a table only when the plugin truly lacks that surface.

1. `## Purpose and boundaries`
   - What the plugin does and does not do.
   - Supported registration style and ComfyUI assumptions.
2. `## Authoritative files`
   - Path, responsibility, and cross-layer synchronization requirements.
3. `## Node registry and contracts`
   - One row per public node: stable ID, class/function, display name, category, source file.
   - Inputs in declared order: internal name, display label, type, required/optional/hidden, defaults and material options.
   - Outputs in order: type and display name.
   - Execution return shape, UI payload keys, list semantics, cache/change hooks, and pass-through identity where relevant.
4. `## Custom data and persisted state`
   - Exact field names, types, examples, optionality, producer/consumer, validation, and workflow serialization.
5. `## Frontend integration`
   - Entry point, node-to-module mapping, widget/state keys, port-label mirrors, external node/widget/port names, lifecycle hooks, and styling source.
6. `## Routes and trust boundaries`
   - Method/path, request and response shapes, limits, validation, filesystem containment, and whether calls are local-only.
7. `## Model, latent, device, and memory behavior`
   - Loading, cloning, mutation, dtype/device/layout, offload, caching, and known unsupported paths. Say `not applicable` when true.
8. `## Compatibility invariants`
   - Stable IDs, port order/types, external contracts, migration policy, and explicit non-goals.
9. `## Validation map`
   - Exact runnable commands discovered from the repository/environment.
   - Targeted tests by feature, syntax/import checks, and manual ComfyUI workflows.
10. `## Documentation and release bookkeeping`
    - User docs, changelog, version sources, examples, and when each must change.
11. `## Unknowns and unverified items`
    - Runtime, browser, GPU, optional dependency, or platform checks not actually performed.
12. `## Profile maintenance rules`
    - Which structural changes require updating this file.

## Quality rules

- Prefer compact tables and exact identifiers over narrative.
- Record internal port names separately from localized labels.
- Distinguish required, optional, hidden, and frontend-hidden widgets.
- Distinguish Python execution outputs from UI-only payloads.
- Record external plugin names verbatim; never normalize identifiers owned elsewhere.
- Do not store secrets, absolute user paths, tokens, machine identifiers, model weights, or transient git status.
- Do not claim compatibility or runtime behavior solely from comments or README text; cross-check implementation and tests.
