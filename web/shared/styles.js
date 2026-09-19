// Single source of truth for the runtime-injected stylesheet.
// toolkit.css at the web root is kept as the readable, non-injected reference.
export const TOOLKIT_STYLES = `
    .xh-root { box-sizing: border-box; width: 100%; max-width: 100%; min-width: 0; overflow: hidden; color: var(--fg-color, #ddd); font: 12px sans-serif; }
    .xh-scroll { box-sizing: border-box; width: 100%; max-width: 100%; height: 100%; min-height: 0; max-height: 100%; overflow-y: auto; overflow-x: hidden; padding: 4px; }
    .xh-row, .xh-preview-row, .xh-merge-row { box-sizing: border-box; min-width: 0; max-width: 100%; }
    .xh-row { border-bottom: 1px solid rgba(255,255,255,.12); padding: 5px 2px 6px; }
    .xh-row:last-child { border-bottom: 0; }
    .xh-model { display: block; font-weight: 600; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .xh-buttons { display: flex; flex-wrap: wrap; align-items: center; gap: 3px; }
    .xh-button { box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; height: 22px; min-height: 22px; line-height: normal; border: 1px solid rgba(255,255,255,.25); border-radius: 5px; padding: 0 7px; background: rgba(255,255,255,.08); color: inherit; cursor: pointer; font-size: 11px; }
    .xh-button:hover { background: rgba(100,170,255,.28); }
    .xh-button.selected { background: #3577a8; border-color: #83c7ff; color: white; }
    .xh-muted { color: #999; padding: 8px 3px; }
    .xh-buttons .xh-muted { box-sizing: border-box; display: inline-flex; align-items: center; height: 22px; min-height: 22px; padding: 2px 4px; line-height: 16px; }
    .xh-error { color: #ff9b9b; padding: 8px 3px; white-space: normal; }
    .xh-preview-row { border-bottom: 1px solid rgba(255,255,255,.2); padding: 6px 2px; }
    .xh-preview-row:last-child { border-bottom: 0; }
    .xh-section-label { color: #aaa; font-size: 10px; margin: 4px 0 2px; }
    .xh-chip-strip { display: flex; flex-wrap: nowrap; gap: 4px; overflow-x: auto; overflow-y: hidden; white-space: nowrap; padding: 2px 0 4px; }
    .xh-chip { flex: 0 0 auto; border: 1px solid rgba(130,190,235,.55); border-radius: 6px; padding: 2px 6px; background: rgba(60,120,165,.24); color: #e4f4ff; cursor: pointer; user-select: none; }
    .xh-chip.disabled { border-color: rgba(150,150,150,.35); background: rgba(100,100,100,.2); color: #777; }
    .xh-merge-row { padding: 4px 2px; }
    .xh-merge-label { display: block; color: #aaa; font-size: 10px; margin-bottom: 2px; }
    .xh-merge-text { box-sizing: border-box; display: block; width: 100%; max-width: 100%; min-width: 0; min-height: 34px; resize: vertical; color: inherit; background: rgba(0,0,0,.25); border: 1px solid rgba(255,255,255,.18); border-radius: 4px; padding: 4px; font: 11px sans-serif; }
    .xh-display-row { padding: 4px 2px; }
    .xh-display-label { display: block; color: #aaa; font-size: 10px; margin-bottom: 2px; }
    .xh-display-text { box-sizing: border-box; display: block; width: 100%; max-width: 100%; min-width: 0; min-height: 92px; resize: vertical; color: inherit; background: rgba(0,0,0,.25); border: 1px solid rgba(255,255,255,.18); border-radius: 4px; padding: 6px; font: 11px monospace; line-height: 1.4; }
    .xh-editor-toolbar { display: flex; align-items: center; gap: 8px; padding: 4px 2px 8px; }
    .xh-editor-model-picker { position: relative; flex: 0 1 auto; min-width: 0; max-width: calc(100% - 70px); }
    .xh-editor-model-select { box-sizing: border-box; display: flex; align-items: center; width: 100%; min-width: 0; height: 26px; border: 1px solid rgba(255,255,255,.22); border-radius: 5px; padding: 0 7px; color: inherit; background: rgba(255,255,255,.08); font: 600 12px sans-serif; cursor: pointer; }
    .xh-editor-model-select.open { position: relative; z-index: 3; border-radius: 5px 5px 0 0; }
    .xh-editor-model-label { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .xh-editor-model-arrow { flex: 0 0 auto; width: 7px; height: 7px; margin: -3px 3px 0 10px; border-right: 2px solid currentColor; border-bottom: 2px solid currentColor; transform: rotate(45deg); }
    .xh-editor-model-select.open .xh-editor-model-arrow { margin-top: 3px; transform: rotate(225deg); }
    .xh-editor-model-menu { box-sizing: border-box; position: absolute; z-index: 2; top: calc(100% - 1px); left: 0; width: 100%; max-height: 190px; overflow-y: auto; border: 1px solid rgba(255,255,255,.22); border-top: 0; border-radius: 0 0 6px 6px; padding: 2px 0 3px; color: var(--fg-color, #ddd); color-scheme: dark; background: color-mix(in srgb, var(--component-node-background, #262729) 92%, white 8%); box-shadow: 0 6px 14px rgba(0,0,0,.38); scrollbar-color: rgba(255,255,255,.32) rgba(0,0,0,.16); }
    .xh-editor-model-menu[hidden] { display: none; }
    .xh-editor-model-option { box-sizing: border-box; display: block; width: 100%; border: 0; padding: 5px 7px; color: inherit; background: transparent; font: 12px sans-serif; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
    .xh-editor-model-option:hover, .xh-editor-model-option:focus { outline: 0; background: rgba(100,170,255,.28); }
    .xh-editor-model-option[aria-selected="true"] { background: #3577a8; color: white; }
    .xh-editor-save { flex: 0 0 auto; height: 26px; min-height: 26px; margin-left: auto; }
    .xh-editor-save:disabled, .xh-editor-model-select:disabled { cursor: default; opacity: .5; }
    .xh-editor-configs { padding: 4px 2px 8px; }
    .xh-editor-config { position: relative; overflow: visible; }
    .xh-editor-config.dirty::after { content: "*"; position: absolute; top: 0; right: 0; transform: translate(50%, -50%); z-index: 1; padding: 0 1px; color: #ffd166; background: var(--comfy-menu-bg, #353535); font-size: 12px; font-weight: 700; line-height: 1; pointer-events: none; }
    .xh-editor-fields { display: grid; gap: 8px; padding: 0 2px 4px; }
    .xh-editor-field { display: block; min-width: 0; }
    .xh-editor-label { display: block; color: #aaa; font-size: 10px; margin-bottom: 3px; }
    .xh-editor-text { box-sizing: border-box; display: block; width: 100%; max-width: 100%; min-width: 0; min-height: 96px; resize: vertical; color: inherit; background: rgba(0,0,0,.25); border: 1px solid rgba(255,255,255,.18); border-radius: 4px; padding: 6px; font: 11px monospace; line-height: 1.4; }
`;
