# ComfyUI node contracts

ComfyUI APIs evolve. Prefer the repository's established registration style and the installed ComfyUI source over remembered examples. Do not migrate between classic mappings, newer node APIs, lazy registration, or schema versions unless the task requires it.

## Contract audit

For each affected node, verify as one unit:

- stable public node ID and display name;
- category and registration/export location;
- input sections and declared order;
- internal input names matching execution parameters;
- required, optional, hidden, lazy, raw-link, list, and force-input semantics;
- type names, defaults, constraints, tooltips, and localized labels;
- output types, output names, list semantics, and ordering;
- execution method/function name and exact return arity/shape;
- UI payload versus normal result payload;
- validation, cache/change hooks, expansion, and async behavior when present.

Never add placeholder inputs or pass-through outputs just for convenient wiring. Optional inputs must have a valid disconnected behavior. Keep internal identifiers stable even when changing display labels unless workflow breakage is explicitly accepted.

## Hidden execution inputs versus frontend widgets

A Python `INPUT_TYPES["hidden"]` entry defines an execution-input contract. It
does not by itself prove that the installed frontend creates a corresponding
entry in `node.widgets`, exposes it to widget lookup helpers, or serializes it
like an ordinary required/optional widget. ComfyUI versions and input kinds may
differ, so do not make the opposite universal claim either.

Before frontend code reads or writes a Python hidden input through a widget
lookup:

- verify the actual node/widget shape in the installed frontend or an
  equivalent lifecycle harness;
- define behavior when the widget is absent;
- verify whether and where the value is serialized;
- test absence as a normal case rather than relying only on optional chaining;
- do not let parsing an absent value into creation defaults overwrite native
  widgets that ComfyUI has already restored.

If a durable frontend state carrier is required, create or use one through the
repository's supported serialization mechanism instead of assuming the Python
hidden declaration supplies it.

## Data and workflow compatibility

- Treat custom type names and serialized field names as public contracts within saved workflows and connected nodes.
- Normalize third-party shapes once at an adapter boundary.
- Preserve output slot order and types. Adding a slot in the middle or repurposing a slot can silently reconnect workflows incorrectly.
- If a breaking change is requested, document the migration and add tests for the chosen policy. Do not invent backward-compatibility aliases without a requirement.

## Model, latent, device, and memory safety

- Pass through model-like objects by identity unless cloning/patching is the feature.
- Do not reload an already supplied model merely to inspect metadata.
- Do not mutate patches, model options, training state, dtype, device, latent layout, batch shape, or offload behavior as a precaution.
- Avoid unconditional CPU/GPU/float32 conversions and large persistent tensor caches.
- Reuse installed ComfyUI helpers for model management, casting, progress, interruption, paths, previews, and optimized kernels.
- Validate shapes, masks, batches, dtypes, and devices at the boundary relevant to the operation. Preserve them when the contract says pass-through.
- Make unsupported formats or execution paths fail clearly; do not silently substitute a lower-quality algorithm.

## Paths and files

- Treat workflow strings and frontend values as untrusted.
- Use ComfyUI folder registries/resolvers where available.
- For the same path contract, centralize resolution and containment in one
  reusable owner used by node, route, task, and preview adapters; do not copy
  slightly different validation pipelines between entries.
- Reject unexpected absolute paths and traversal components; verify containment after normalization/resolution.
- Include symlink behavior in the containment policy where the platform and
  filesystem can expose it.
- Do not expose absolute user paths in workflow state, browser payloads, or errors unless the product explicitly requires it.
- Bound directory scans and file sizes where user-controlled input can trigger work.

## Tests that should accompany contract changes

Assert the declaration and behavior, not just helper output:

- exact required/optional/hidden names and order;
- exact input/output types and output names;
- return arity and UI/result shape;
- pass-through identity where promised;
- empty, missing, malformed, and boundary inputs;
- list/batch behavior where supported;
- model/path safety cases relevant to the feature;
- registration/import success.
