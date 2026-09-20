# Validation tooling

Read this reference only when the selected evidence needs environment
diagnosis, the portable unittest wrapper, explicit frontend ESM parsing, or a
controlled plugin import. Project-specific commands in
`COMFYUI_PLUGIN_PROJECT.md` remain authoritative.

## Environment preflight and unittest wrapper

Before the first formal validation attempt, copy the interpreter, working
directory, environment variables, and command from the project profile. Do not
improvise a replacement when a recorded command is usable.

When paths or imports are uncertain, run:

```text
python <skill-dir>/scripts/validate_environment.py \
  --root <plugin-root> [--comfy-root <comfy-root>]
```

For a standard `<ComfyUI>/custom_nodes/<plugin>` layout, omit `--comfy-root`;
the helper resolves it upward. Pass it for a nonstandard layout or deliberate
override. `--plugin-root` remains a compatibility alias for `--root`.

Verify the actual Python executable and roots, that `folder_paths` came from the
selected ComfyUI root, and that the recorded working directory and environment
match the command that will run.

For a standard-library `unittest` suite, the optional wrapper avoids
shell-specific `PYTHONPATH` syntax:

```text
python <skill-dir>/scripts/run_plugin_tests.py \
  --root <plugin-root> [--comfy-root <comfy-root>]
```

It adds the resolved ComfyUI and plugin roots to the child process only. Do not
replace a profile-specified `pytest`, tox, package-manager, or custom runner
with this wrapper. Report any failed formal invocation even if a corrected
command later passes.

## Explicit frontend module parsing

ComfyUI frontend extensions are native ES modules. Parse affected modules
explicitly as ESM:

```text
python <skill-dir>/scripts/check_frontend_syntax.py \
  --root <plugin-root> [web/path/to/changed.js ...]
```

With no paths, the helper scans `web/**/*.js` and `web/**/*.mjs`. It catches
parse-time failures such as duplicate declarations or exports and malformed
module syntax. It does not resolve imports or prove browser APIs, DOM mounting,
styling, serialization, or execution.

After moving frontend symbols, establish one declaration owner and intentional
imports/re-exports, parse source/destination/entry modules, and prefer
behavioral or parser evidence over string-presence assertions. A text assertion
that remains useful should check expected count and ownership, not mere
presence.

## Controlled plugin import

Run:

```text
python <skill-dir>/scripts/check_plugin_import.py \
  --root <plugin-root> [--comfy-root <comfy-root>]
```

The helper imports the plugin with a controlled `PromptServer.instance`, so it
executes the plugin's top-level Python code. Use it only for a trusted local
repository; it is not a sandbox and does not suppress arbitrary import side
effects.

Interpret its result by scope:

- `passed` with `evidence_scope: classic-registration-structure` checks classic
  mapping key/value structure, display mappings, a declared `WEB_DIRECTORY`,
  collected routes, and whether re-executing the plugin root changed those
  routes.
- `partial` with `evidence_scope: registration-surface-only` means a
  `NODE_LIST` or `comfy_entrypoint` surface exists, but its contents or
  registration behavior were not executed. A real compatible ComfyUI runtime
  check is still required.
- `error` may identify an implementation failure, an incompatible controlled
  stub, or an environment/import failure. Classify it before changing plugin
  code.

Root re-execution is not the same as a normal cached second import, a framework
reload, or a real ComfyUI restart. Never describe
`repeat_execution_route_stable` as proof of universal import idempotence.

Label every result **controlled import** or **partial controlled-import
evidence**, never real ComfyUI startup.
