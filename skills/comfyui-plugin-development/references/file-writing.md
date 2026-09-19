# Editing and saving user-owned files

Read this reference when a feature edits existing sidecars, configs, workflows, metadata, or other user-owned files, especially in batches.

## Choose the preservation policy first

Before implementation, establish one explicit policy:

1. **Lossless in-place update:** preserve unknown fields, structure, unmodified content, and relevant formatting/encoding details.
2. **Canonical rewrite:** replace content with only the supported canonical representation.
3. **Side-by-side output:** write a new file and leave the source untouched.

“Edit/save the original file” does not authorize dropping unknown JSON keys, nested objects, text lines, comments, metadata, BOM, newline style, key order, trailing newline, or original label language. If the user has not chosen and the source cannot establish the contract, ask before implementing.

Tests must include unknown content and assert whether it survives according to the selected policy. For a claimed lossless path, also test the format details the implementation promises to preserve; do not use “lossless” when only recognized semantic fields survive.

## Define batch semantics

Choose and document one behavior:

- all succeed or all roll back;
- validate all, then write sequentially with possible partial success;
- independent per-item results.

Test a failure after at least one successful item. Verify files changed, files untouched, response details, drafts cleared, drafts retained, and retry behavior. Never let the frontend clear every draft after a partial failure unless the backend contract proves every item committed.

For ordinary sidecar editors, independent per-item results with failed drafts retained is often the clearest choice, but it is not a universal default.

## Atomicity and conflicts

- Use same-directory temporary files plus atomic replacement for single-file writes when supported.
- Capture an immutable request snapshot at save start.
- Edits made while a save is in flight become a later draft and must not be cleared by the older response.
- Define duplicate-click behavior and disable or deduplicate identical in-flight saves.
- When external modification is plausible, compare an observed mtime/hash/version before replacement and surface a conflict instead of silently overwriting.
- Define behavior when two nodes edit the same file.

Keep filesystem containment, extension allowlists, size/count limits, and error redaction at the server boundary.
