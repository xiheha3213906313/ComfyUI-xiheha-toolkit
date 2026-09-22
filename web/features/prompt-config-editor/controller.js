import { MODEL_SOURCE_NODE, SELECTOR_NODE, STACK_NODE } from "../../shared/constants.js";
import { inspectSources, saveSourceConfigs } from "../../shared/api.js";
import { connectedNode, graphNodes, nodeTypeId } from "../../shared/graph.js";
import { configureScrollableWidget, createRoot, scrollWidgetOptions } from "../../shared/layout.js";
import { collectSourceEntries } from "../../shared/upstream.js";
import { hideWidget, widgetByName, widgetValue } from "../../shared/widgets.js";
import { markDirty } from "../../shared/workflow.js";
import {
    NEW_CONFIG, applySaveResults, buildSavePayload, canDeleteConfig, cleanEditorState,
    clearNewDraft, ensureSelections, hasLoadedDrafts, selectedConfigKey, setDraft,
    sourceKey, stageConfigDeletion,
} from "./state.js";
import { cleanupEditorView, renderEditorView, showConfirmDialog } from "./view.js";

function notifySelectors() {
    for (const target of graphNodes()) {
        if (nodeTypeId(target) === SELECTOR_NODE) target.__xhSelector?.refreshFromSource();
    }
}

export function createPromptConfigEditorController(node) {
    if (node.__xhPromptConfigEditor) return node.__xhPromptConfigEditor;
    const root = createRoot("xh-config-editor");
    const scroll = document.createElement("div");
    scroll.className = "xh-scroll";
    root.appendChild(scroll);
    node.addDOMWidget("config_editor_ui", "xh_config_editor_ui", root, scrollWidgetOptions(node, 280, 12));
    configureScrollableWidget(node, root, scroll, { width: 520, height: 370 });
    hideWidget(widgetByName(node, "editor_state"));
    const controller = {
        node, root, scroll, infos: [],
        state: cleanEditorState(widgetValue(node, "editor_state", "{}")),
        refreshSequence: 0, error: null, saving: false, disposed: false,
        configButtons: new Map(), saveButton: null, deleteButton: null,
        currentDialog: null, cleanupModelMenu: null,
        cleanup() { this.disposed = true; this.refreshSequence += 1; cleanupEditorView(this); },
        closeDialog() { this.currentDialog?.remove(); this.currentDialog = null; },
        restoreFromWidgets() {
            this.refreshSequence += 1;
            this.state = cleanEditorState(widgetValue(node, "editor_state", "{}"));
            ensureSelections(this.state, this.infos);
            this.render();
        },
        saveState({ notify = true } = {}) {
            const widget = widgetByName(node, "editor_state");
            if (widget) {
                const value = JSON.stringify(this.state);
                widget.value = value;
                if (widget.inputEl) widget.inputEl.value = value;
            }
            if (notify) markDirty(node);
        },
        currentInfo() { return this.infos.find((info) => sourceKey(info) === this.state.selectedSource) || null; },
        selectSource(key) {
            if (key === this.state.selectedSource) return;
            this.state.selectedSource = key; this.saveState(); this.render();
        },
        selectConfig(info, configKey) {
            this.state.selections[sourceKey(info)] = configKey; this.saveState(); this.render();
        },
        updateDraft(info, configKey, positive, negative) {
            const dirty = setDraft(this.state, info, configKey, { positive, negative });
            this.configButtons.get(configKey)?.classList.toggle("dirty", dirty);
            if (this.saveButton) this.saveButton.disabled = this.saving || !hasLoadedDrafts(this.state, this.infos);
            if (this.deleteButton) this.deleteButton.disabled = !canDeleteConfig(this.state, info, this.saving);
            this.saveState();
        },
        requestDelete(info) {
            if (!canDeleteConfig(this.state, info, this.saving)) return;
            const selected = selectedConfigKey(this.state, info);
            if (selected === NEW_CONFIG) {
                showConfirmDialog(this, {
                    title: "确认清空", message: "确定要清空正在添加的提示词草稿吗？",
                    onConfirm: () => { clearNewDraft(this.state, info); this.saveState(); this.render(); },
                });
                return;
            }
            showConfirmDialog(this, {
                title: "确认删除", message: `确定要删除「配置${selected}」吗？`,
                onConfirm: () => this.deleteSelectedConfig(info, selected),
            });
        },
        async deleteSelectedConfig(info, selected) {
            stageConfigDeletion(this.state, info, selected); this.saveState(); await this.saveAll();
        },
        async saveAll() {
            if (this.saving || this.disposed) return;
            const request = buildSavePayload(this.state, this.infos);
            if (!request.sources.length) return;
            this.saving = true; this.error = null; this.render();
            try {
                const savedInfos = await saveSourceConfigs(request.sources);
                if (this.disposed) return;
                this.infos = applySaveResults(this.state, this.infos, request, savedInfos);
                this.saveState();
                notifySelectors();
            } catch (error) {
                if (!this.disposed) this.error = error.message || String(error);
            } finally {
                if (!this.disposed) {
                    this.saving = false; ensureSelections(this.state, this.infos); this.render();
                }
            }
        },
        render() { if (!this.disposed) renderEditorView(this); },
        async refreshFromSource() {
            const sequence = ++this.refreshSequence;
            const source = connectedNode(node, "source");
            const sources = source && [STACK_NODE, MODEL_SOURCE_NODE].includes(nodeTypeId(source))
                ? collectSourceEntries(source) : [];
            if (!sources.length) {
                this.infos = []; this.error = null; ensureSelections(this.state, this.infos); this.render(); return;
            }
            try {
                const infos = await inspectSources(sources);
                if (sequence !== this.refreshSequence || this.disposed) return;
                const stateBeforeNormalization = JSON.stringify(this.state);
                this.infos = infos; this.error = null; ensureSelections(this.state, this.infos);
                this.saveState({ notify: JSON.stringify(this.state) !== stateBeforeNormalization });
                this.render();
            } catch (error) {
                if (sequence !== this.refreshSequence || this.disposed) return;
                this.infos = []; this.error = error.message || String(error);
                ensureSelections(this.state, this.infos); this.render();
            }
        },
    };
    node.__xhPromptConfigEditor = controller;
    ensureSelections(controller.state, controller.infos);
    controller.render();
    return controller;
}
