# ComfyUI frontend visual debugging

Use this reference for visual defects involving custom DOM widgets inside Canvas/LiteGraph nodes: theme mismatch, dropdown/popover seams, unexplained node whitespace, clipping, or resize behavior.

## Inspect the rendered state before editing

Identify the exact state named by the user: closed, open, hover, focus, disabled, scrolled, minimum-size, or manually resized. Inspect that state rather than inferring the result from static CSS.

Record the evidence relevant to the defect:

- computed background, border, radius, dimensions, overflow, and positioning;
- resolved values of the CSS variables actually used;
- trigger, popup, scroll-container, DOM-widget, and node-boundary rectangles;
- browser zoom and canvas zoom;
- whether each visible surface is Canvas-rendered or DOM-rendered.

After editing, reopen the same state and verify it directly. For a dropdown defect that appears only while open, a closed-state screenshot or syntax check is not acceptance evidence.

## Canvas and DOM theme matching

ComfyUI may draw the node body on Canvas while custom widgets and popovers are DOM elements. Equal CSS declarations do not guarantee equal visual results: a translucent control blends with the Canvas below it, while a floating translucent popup may reveal unrelated DOM controls.

- Read live computed values; do not select a variable from its name alone.
- Treat menu, input, node, and node-widget variables as different semantic surfaces. For example, `--comfy-menu-bg` describes a menu and is not evidence of the node-body color.
- Prefer the installed frontend's semantic node/widget variables when they match the intended surface, such as `--component-node-background`, `--component-node-widget-background`, and `--component-node-widget-background-hovered` when available.
- If a popup must resemble a translucent widget but remain opaque, derive an opaque color with `color-mix()` or an equivalent theme-aware technique and provide a compatible fallback.
- Verify relevant supported themes; never treat one dark-theme value as a universal constant.

For a trigger and popup intended to read as one connected control, inspect rather than guess the seam. Common techniques are removing the trigger's lower radii while open, removing the popup's top border, retaining only lower popup radii, and overlapping by about one device pixel. These are options, not invariants: confirm that zoom and device scaling do not create a doubled border or gap. Do not change the trigger to an unrelated menu color merely to conceal the seam.

Native `<select>` popup rendering varies by browser and operating system. When the requirement needs reliable popup colors, radii, scrolling, or composition that native controls cannot supply, use an accessible custom button/listbox only if the added complexity is justified. Preserve keyboard navigation, focus behavior, ARIA expanded/selected state, outside-click and Escape closing, and disabled behavior.

## DOM widget sizing and node whitespace

Do not assume `node.size[1]` is the raw height available to a DOM widget. The ComfyUI frontend may already subtract the title, ports, widget spacing, and padding before calling layout callbacks. A second fixed deduction in `getMaxHeight()` can reserve the same space twice and leave a permanent blank region.

When diagnosing whitespace or clipping:

1. Determine whether the blank area is inside the scroll container or between the DOM widget and node boundary.
2. Compare node, widget, scroll, and content rectangles.
3. Inspect `getMinHeight`, `getMaxHeight`, `computeSize`, `setSize`, and `onResize` together, including framework-side deductions.
4. Replace unexplained fixed deductions with a named, caller-configurable reservation when different widgets genuinely need different compatibility space.
5. Preserve existing callers unless they have been visually checked; do not turn a local layout fix into a global sizing change.
6. Verify minimum size and manual resize states, including scroll behavior.

Do not repeatedly reduce the default node height to compensate for a widget-height calculation error. Fix the layer that owns the incorrect reservation.
