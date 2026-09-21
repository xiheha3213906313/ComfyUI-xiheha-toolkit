# Confirmed user preferences

These are cross-project defaults explicitly confirmed by the user for work
performed with this skill. Apply them to user-facing UI and presentation unless
the current request gives different instructions.

Precedence:

1. explicit requirements in the current user request;
2. confirmed project-specific requirements or compatibility constraints;
3. the defaults in this file.

If a higher-priority requirement conflicts with a default below, follow the
higher-priority requirement without treating the default as a blocker. Ask only
when the conflict leaves a material user-visible choice unresolved.

## User-facing UI defaults

- Do not use Emoji in buttons, labels, status messages, or decorative icons.
- Use natural, understandable Chinese for user-visible text when the meaning
  remains accurate. Keep highly technical terms in their original language
  when no reliable Chinese equivalent exists or translation would mislead; do
  not force full localization.
- Give labels, options, controls, and dynamic content enough layout space. After
  adding or changing controls, check different option counts, conditional
  visibility, expanded and collapsed states, node resizing, and historical
  workflow loading. Do not leave text, options, buttons, inputs, or borders
  overlapping, obscured, or collapsed.

Do not infer additional personal preferences from a single task, implementation,
or another model's report. Add or change defaults here only after the user
explicitly confirms them.
