# Architecture and modularity

Read this reference when a change adds a feature or subsystem, expands a large
controller/route/node file, duplicates an existing workflow, creates or grows a
shared utility, or performs a module split. The goal is not small files; it is
one clear owner for each behavior and a design that can change without editing
unrelated concerns.

## Establish ownership before adding behavior

For the affected feature, identify the owner of each applicable concern:

| Concern | Expected owner |
| --- | --- |
| ComfyUI node contract | Thin node adapter/entry |
| HTTP parsing and response adaptation | Thin route adapter |
| Reusable business workflow | One domain pipeline/service |
| Algorithm or file/media primitive | Focused core module |
| Persisted state and transitions | State module or one explicit controller boundary |
| DOM creation and rendering | View/component layer |
| Remote/local request transport | API client/adapter |
| Timers, listeners, callbacks, observers | One lifecycle owner with deterministic cleanup |
| Styles, defaults, schemas, mappings | One named authoritative source |

An existing repository may use different filenames or fewer layers. Preserve a
cohesive local architecture; do not impose a directory template when the same
ownership boundaries are already clear.

## Responsibility-growth review

File length is a warning, not a design rule. Reassess the boundary before adding
more code when any of these is true:

- one file owns three or more of state, DOM/view, transport, lifecycle, business
  orchestration, algorithm/IO, or public adaptation;
- the file now has more than two independent reasons to change;
- a controller coordinates several independent requests or resource types and
  cleanup is spread across event handlers;
- the same workflow appears in a node, route, CLI, task, or preview path more
  than once;
- a shared file begins importing feature-specific node IDs, state, payloads, or
  UI behavior;
- a second full copy of CSS, defaults, schemas, mappings, or algorithms is being
  introduced;
- a controller or adapter is already roughly 300 lines and the change adds a
  new responsibility rather than extending one cohesive algorithm.

These signals require an ownership decision, not automatic fragmentation. Keep
a long cohesive algorithm together. If correcting the boundary would materially
expand a focused user request, explain the risk and ask before starting a broad
refactor; do not silently redesign the repository.

## Keep entries and adapters thin

Node, route, registry, and frontend extension entries translate framework
contracts into feature calls. They may declare metadata, validate at their
boundary, select an explicit policy, and adapt results. They should not contain
a second implementation of the business workflow.

When several adapters need the same behavior, use this dependency direction:

```text
node / route / task adapter
            |
parameter normalization and explicit policy
            |
single business pipeline
            |
focused algorithm and IO primitives
```

Different callers may pass explicit policies such as cache reuse, preview
detail, or error presentation. Policy differences do not justify copying the
pipeline. Keep framework objects and HTTP response formatting outside the
domain pipeline unless they are genuinely part of its contract.

For a complex frontend feature, a useful decomposition is node patch/installer,
state transitions, view rendering, API transport, and lifecycle/controller
orchestration. This is a responsibility model, not a required folder layout.
State logic should remain free of DOM, application globals, and network access
where practical so it can be tested directly.

## Shared code and authoritative sources

Name shared modules by stable domain responsibility rather than by vagueness.
Prefer concepts such as graph traversal, widgets, layout, workflow state,
payloads, lifecycle, or stylesheets over an ever-growing `utils`, `helpers`, or
`dom` module.

Before moving code to shared scope, require at least one stable responsibility
and a plausible second consumer. Feature-specific behavior belongs with the
feature even if it is technically reusable. Shared modules must not become a
way to hide circular dependencies or mix unrelated concerns.

For styles, defaults, schemas, mappings, and algorithms, name one authoritative
source. If another layer needs a mirror, generate it or verify it with a narrow
contract test. Do not maintain two full copies by hand or write tests that
require the duplication to remain.

## Lifecycle and asynchronous ownership

A controller that creates external resources owns their complete lifetime. Use
one idempotent `dispose()` or cleanup registry for applicable timers, global
listeners, pointer-drag handlers, observers, dynamically created DOM/file
inputs, media handlers, callback wrappers, registrations, and abort handles.
Installing twice must not duplicate resources; disposing twice must be safe.
Restore wrapped callbacks or hooks when ownership ends where the host object may
outlive the controller.

At async boundaries, capture immutable input/state snapshots and define:

- request identity or cancellation;
- whether a completion is still current;
- behavior after controller disposal;
- polling stop, failure, and timeout conditions;
- which exact snapshot may be cleared or committed after success.

Use [frontend-and-api.md](frontend-and-api.md) for persisted frontend state,
programmatic dirty notification, restoration ordering, and stale-response
details. Use [file-writing.md](file-writing.md) for save snapshots, conflicts,
partial failure, and draft retention.

## Internal data, workflow state, and HTTP DTOs

Do not expose an internal execution object directly as an HTTP response or
workflow state merely because its current fields appear safe. Define separate
representations when their trust boundaries differ:

- internal execution objects may contain paths and implementation metadata;
- workflow state contains only durable, portable fields required to restore the
  feature;
- HTTP responses are constructed from an explicit allowlist of fields needed by
  the client.

Prefer allowlist construction over deleting known-sensitive keys. Keep task
status records minimal, redact exception details, and never return absolute
paths unless the product explicitly requires and authorizes them.

Centralize path resolution and containment for a given input contract. Node and
route adapters should call the same resolver instead of maintaining subtly
different checks. The resolver should perform the relevant type/empty checks,
reject unintended absolute or traversal input, resolve through registered
roots, verify containment after resolution including symlink behavior, and
check the required file kind/existence.

## Tests that survive refactoring

Test public contracts, observable behavior, safety boundaries, cleanup, and
race handling. Prefer importing and executing real pure modules or adapters
over duplicating their implementation in the test.

Avoid tests whose main assertion is that a private variable, exact expression,
CSS block, or copied implementation text exists. Source searches are useful for
narrow negative or migration assertions—for example, proving an obsolete import,
duplicate stylesheet source, unsafe event constructor, or retired route no
longer exists—not as primary evidence that the feature works.

For a module split or architectural refactor, verify as applicable:

- each entry still installs/registers once and delegates to the intended owner;
- the shared pipeline produces equivalent results for every adapter policy;
- removed modules and symbols have no remaining import or registration path;
- imports remain acyclic and all affected modules parse/import;
- lifecycle setup/disposal is behaviorally idempotent;
- HTTP DTO tests assert an allowlist and absence of sensitive fields;
- path-contract tests exercise every adapter through the centralized resolver;
- existing public node, workflow, route, and frontend behavior remains stable.

Do not run every architecture search for a local text or style edit. Select the
checks that correspond to the ownership boundaries actually changed.
