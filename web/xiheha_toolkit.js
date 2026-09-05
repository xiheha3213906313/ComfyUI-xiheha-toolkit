// Entry point for the xiheha-toolkit frontend.
// Only this file calls app.registerExtension. Each toolkit node owns its
// controller and lifecycle hooks in web/nodes/*.js; shared helpers live in web/shared/.
//
// To add a new node: create web/nodes/<name>.js exporting NODE_ID and patch(nodeType),
// then import it below and add it to NODE_MODULES.
import { app } from "../../../scripts/app.js";
import { EASY_USE_STACK_NODE, MODEL_LOADER_SOURCES } from "./shared/constants.js";
import { graphNodes, nodeTypeId } from "./shared/dom.js";
import { installEasyUseStackObserver, installModelLoaderObserver } from "./shared/upstream.js";
import * as stackSource from "./nodes/stack-source.js";
import * as modelSource from "./nodes/model-source.js";
import * as promptSelector from "./nodes/prompt-selector.js";
import * as promptPreview from "./nodes/prompt-preview.js";
import * as promptMerger from "./nodes/prompt-merger.js";

// node ID -> beforeRegisterNodeDef patch. Order is irrelevant.
const NODE_MODULES = [stackSource, modelSource, promptSelector, promptPreview, promptMerger];
const NODE_PATCHES = Object.fromEntries(NODE_MODULES.map((mod) => [mod.NODE_ID, mod.patch]));

app.registerExtension({
    name: "ComfyUI.XihehaToolkit",
    nodeCreated(node) {
        // Observers are attached to EXTERNAL nodes (easy-use / core loaders)
        // so the selector can refresh when their widget or links change.
        if (nodeTypeId(node) === EASY_USE_STACK_NODE) {
            setTimeout(() => installEasyUseStackObserver(node), 0);
        }
        if (MODEL_LOADER_SOURCES[nodeTypeId(node)]) {
            setTimeout(() => installModelLoaderObserver(node), 0);
        }
    },
    afterConfigureGraph() {
        for (const node of graphNodes()) {
            if (nodeTypeId(node) === EASY_USE_STACK_NODE) installEasyUseStackObserver(node);
            if (MODEL_LOADER_SOURCES[nodeTypeId(node)]) installModelLoaderObserver(node);
        }
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        NODE_PATCHES[nodeData.name]?.(nodeType);
    },
});
