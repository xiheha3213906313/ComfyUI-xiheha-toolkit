// Public tooltip facade. Parsing stays pure; browser/runtime behavior stays isolated.
export { parseTooltipString, renderTooltipContent, resolveTooltipData } from "./tooltip/data.js";
export {
    ensureGlobalListeners,
    ensureTooltipElement,
    findRegisteredWidgetUnderPointer,
    getWidgetAtPos,
    hideTooltip,
    registerCustomTooltip,
    showTooltip,
    unregisterCustomTooltip,
    updateTooltipMutualExclusion,
} from "./tooltip/runtime.js";
export { ensureTooltipStylesheet } from "./stylesheets.js";
