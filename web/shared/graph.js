// Graph lookup and connection helpers shared by frontend controllers.
import { app } from "../../../scripts/app.js";

export const graphNodes = () => app.graph?._nodes || app.graph?.nodes || [];
export const nodeTypeId = (node) => node?.comfyClass || node?.type;

export function connectedNode(node, inputName) {
    const input = node.inputs?.find((item) => item.name === inputName);
    if (!input || input.link == null) return null;
    const link = node.graph?.links?.[input.link] || app.graph?.links?.[input.link];
    if (!link) return null;
    return node.graph?.getNodeById?.(link.origin_id) || app.graph?.getNodeById?.(link.origin_id) || null;
}

export function connectedOutput(node, inputName) {
    const input = node.inputs?.find((item) => item.name === inputName);
    if (!input || input.link == null) return null;
    const link = node.graph?.links?.[input.link] || app.graph?.links?.[input.link];
    if (!link) return null;
    const origin = node.graph?.getNodeById?.(link.origin_id) || app.graph?.getNodeById?.(link.origin_id) || null;
    return origin ? { node: origin, slot: Number(link.origin_slot) || 0 } : null;
}

export function isConnected(node, inputName) {
    return Boolean(node.inputs?.find((item) => item.name === inputName)?.link != null);
}
