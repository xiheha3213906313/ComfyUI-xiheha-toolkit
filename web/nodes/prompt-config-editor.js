// XH_PromptConfigEditor — edit and save model/LoRA prompt sidecars.
import {
    CONFIG_EDITOR_NODE,
    STACK_NODE,
    MODEL_SOURCE_NODE,
    SELECTOR_NODE,
} from "../shared/constants.js";
import {
    createRoot,
    configureScrollableWidget,
    scrollWidgetOptions,
    hideWidget,
    widgetByName,
    widgetValue,
    markDirty,
    connectedNode,
    graphNodes,
    nodeTypeId,
    applyPortLabels,
} from "../shared/dom.js";
import { inspectSources, saveSourceConfigs } from "../shared/api.js";
import { collectSourceEntries } from "../shared/upstream.js";

export const NODE_ID = CONFIG_EDITOR_NODE;

const NEW_CONFIG = "new";

function sourceKey(source) {
    return JSON.stringify([String(source?.folder_name || "loras"), String(source?.source_name || "")]);
}

function cleanState(value) {
    try {
        const parsed = JSON.parse(String(value || "{}"));
        const selections = {};
        if (parsed?.selections && typeof parsed.selections === "object" && !Array.isArray(parsed.selections)) {
            for (const [key, selection] of Object.entries(parsed.selections)) {
                if (selection === NEW_CONFIG || Number.isInteger(Number(selection))) selections[key] = String(selection);
            }
        }
        const drafts = {};
        if (parsed?.drafts && typeof parsed.drafts === "object" && !Array.isArray(parsed.drafts)) {
            for (const [key, sourceDrafts] of Object.entries(parsed.drafts)) {
                if (!sourceDrafts || typeof sourceDrafts !== "object" || Array.isArray(sourceDrafts)) continue;
                const cleaned = {};
                for (const [configKey, draft] of Object.entries(sourceDrafts)) {
                    if (configKey !== NEW_CONFIG && !/^\d+$/.test(configKey)) continue;
                    if (!draft || typeof draft !== "object" || Array.isArray(draft)) continue;
                    cleaned[configKey] = {
                        positive: typeof draft.positive === "string" ? draft.positive : "",
                        negative: typeof draft.negative === "string" ? draft.negative : "",
                    };
                }
                if (Object.keys(cleaned).length) drafts[key] = cleaned;
            }
        }
        return {
            selectedSource: typeof parsed?.selectedSource === "string" ? parsed.selectedSource : null,
            selections,
            drafts,
        };
    } catch {
        return { selectedSource: null, selections: {}, drafts: {} };
    }
}

function configValue(config) {
    return {
        positive: String(config?.positive || ""),
        negative: String(config?.negative || ""),
    };
}

function configIndexSet(info) {
    return new Set((info?.configs || []).map((config) => String(Number(config.index))));
}

function editorController(node) {
    if (node.__xhPromptConfigEditor) return node.__xhPromptConfigEditor;
    const root = createRoot("xh-config-editor");
    const scroll = document.createElement("div");
    scroll.className = "xh-scroll";
    root.appendChild(scroll);
    node.addDOMWidget("config_editor_ui", "xh_config_editor_ui", root, scrollWidgetOptions(node, 280, 12));
    configureScrollableWidget(node, root, scroll, { width: 520, height: 370 });
    hideWidget(widgetByName(node, "editor_state"));

    const controller = {
        node,
        scroll,
        infos: [],
        state: cleanState(widgetValue(node, "editor_state", "{}")),
        refreshSequence: 0,
        error: null,
        saving: false,
        configButtons: new Map(),
        saveButton: null,
        saveState() {
            const widget = widgetByName(node, "editor_state");
            if (widget) {
                const value = JSON.stringify(this.state);
                widget.value = value;
                if (widget.inputEl) widget.inputEl.value = value;
            }
            markDirty(node);
        },
        currentInfo() {
            return this.infos.find((info) => sourceKey(info) === this.state.selectedSource) || null;
        },
        ensureSelections() {
            const available = new Set(this.infos.map(sourceKey));
            if (!this.state.selectedSource || !available.has(this.state.selectedSource)) {
                this.state.selectedSource = this.infos.length ? sourceKey(this.infos[0]) : null;
            }
            for (const info of this.infos) {
                const key = sourceKey(info);
                const indexes = configIndexSet(info);
                const selected = String(this.state.selections[key] ?? "");
                if (selected === NEW_CONFIG || indexes.has(selected)) continue;
                this.state.selections[key] = info.configs?.length ? String(Number(info.configs[0].index)) : NEW_CONFIG;
            }
        },
        selectedConfigKey(info) {
            return String(this.state.selections[sourceKey(info)] ?? NEW_CONFIG);
        },
        baseline(info, configKey) {
            if (configKey === NEW_CONFIG) return { positive: "", negative: "" };
            const config = info.configs?.find((item) => Number(item.index) === Number(configKey));
            return configValue(config);
        },
        effectiveValue(info, configKey) {
            const key = sourceKey(info);
            return configValue(this.state.drafts[key]?.[configKey] || this.baseline(info, configKey));
        },
        setDraft(info, configKey, positive, negative) {
            const key = sourceKey(info);
            const next = { positive: String(positive || ""), negative: String(negative || "") };
            const baseline = this.baseline(info, configKey);
            const dirty = next.positive !== baseline.positive || next.negative !== baseline.negative;
            if (dirty) {
                this.state.drafts[key] ||= {};
                this.state.drafts[key][configKey] = next;
            } else if (this.state.drafts[key]) {
                delete this.state.drafts[key][configKey];
                if (!Object.keys(this.state.drafts[key]).length) delete this.state.drafts[key];
            }
            this.configButtons.get(configKey)?.classList.toggle("dirty", dirty);
            if (this.saveButton) this.saveButton.disabled = this.saving || !this.hasLoadedDrafts();
            this.saveState();
        },
        hasLoadedDrafts() {
            return this.infos.some((info) => Object.keys(this.state.drafts[sourceKey(info)] || {}).length > 0);
        },
        buildSavePayload() {
            const sources = [];
            const addedIndexes = {};
            for (const info of this.infos) {
                const key = sourceKey(info);
                const drafts = this.state.drafts[key];
                if (!drafts || !Object.keys(drafts).length || info.error) continue;
                const configs = (info.configs || []).map((config) => ({
                    index: Number(config.index),
                    ...configValue(config),
                }));
                for (const [configKey, draft] of Object.entries(drafts)) {
                    if (configKey === NEW_CONFIG) continue;
                    const existing = configs.find((config) => config.index === Number(configKey));
                    if (existing) Object.assign(existing, configValue(draft));
                }
                if (drafts[NEW_CONFIG]) {
                    const nextIndex = Math.max(0, ...configs.map((config) => config.index)) + 1;
                    configs.push({ index: nextIndex, ...configValue(drafts[NEW_CONFIG]) });
                    addedIndexes[key] = nextIndex;
                }
                configs.sort((left, right) => left.index - right.index);
                sources.push({
                    source_name: info.source_name,
                    folder_name: info.folder_name || "loras",
                    configs,
                });
            }
            return { sources, addedIndexes };
        },
        async saveAll() {
            if (this.saving) return;
            const { sources, addedIndexes } = this.buildSavePayload();
            if (!sources.length) return;
            this.saving = true;
            this.error = null;
            this.render();
            try {
                const savedInfos = await saveSourceConfigs(sources);
                const savedByKey = new Map(savedInfos.map((info) => [sourceKey(info), info]));
                for (const source of sources) {
                    const key = sourceKey(source);
                    const saved = savedByKey.get(key);
                    if (!saved || saved.error) throw new Error(saved?.error || "保存结果不完整");
                    const index = this.infos.findIndex((info) => sourceKey(info) === key);
                    if (index >= 0) this.infos[index] = saved;
                    delete this.state.drafts[key];
                    if (addedIndexes[key] != null) this.state.selections[key] = String(addedIndexes[key]);
                }
                this.saveState();
                for (const target of graphNodes()) {
                    if (nodeTypeId(target) === SELECTOR_NODE) target.__xhSelector?.refreshFromSource();
                }
            } catch (error) {
                this.error = error.message || String(error);
            } finally {
                this.saving = false;
                this.ensureSelections();
                this.render();
            }
        },
        render() {
            scroll.textContent = "";
            this.configButtons.clear();

            const toolbar = document.createElement("div");
            toolbar.className = "xh-editor-toolbar";
            const modelPicker = document.createElement("div");
            modelPicker.className = "xh-editor-model-picker";
            const modelSelect = document.createElement("button");
            modelSelect.type = "button";
            modelSelect.className = "xh-editor-model-select";
            modelSelect.setAttribute("aria-haspopup", "listbox");
            modelSelect.setAttribute("aria-expanded", "false");
            const selectedInfo = this.currentInfo();
            const modelLabel = document.createElement("span");
            modelLabel.className = "xh-editor-model-label";
            modelLabel.textContent = selectedInfo?.display_name || selectedInfo?.source_name || "无可用模型";
            const modelArrow = document.createElement("span");
            modelArrow.className = "xh-editor-model-arrow";
            modelArrow.setAttribute("aria-hidden", "true");
            modelSelect.append(modelLabel, modelArrow);

            const modelMenu = document.createElement("div");
            modelMenu.className = "xh-editor-model-menu";
            modelMenu.setAttribute("role", "listbox");
            modelMenu.hidden = true;
            for (const info of this.infos) {
                const optionKey = sourceKey(info);
                const option = document.createElement("button");
                option.type = "button";
                option.className = "xh-editor-model-option";
                option.setAttribute("role", "option");
                option.setAttribute("aria-selected", String(optionKey === this.state.selectedSource));
                option.textContent = info.display_name || info.source_name;
                option.onclick = () => {
                    if (optionKey === this.state.selectedSource) {
                        modelMenu.hidden = true;
                        modelSelect.classList.remove("open");
                        modelSelect.setAttribute("aria-expanded", "false");
                        return;
                    }
                    this.state.selectedSource = optionKey;
                    this.saveState();
                    this.render();
                };
                modelMenu.appendChild(option);
            }
            modelSelect.disabled = !this.infos.length || this.saving;
            const setModelMenuOpen = (open) => {
                if (modelSelect.disabled) return;
                modelMenu.hidden = !open;
                modelSelect.classList.toggle("open", open);
                modelSelect.setAttribute("aria-expanded", String(open));
            };
            modelSelect.onclick = () => setModelMenuOpen(modelMenu.hidden);
            modelSelect.onkeydown = (event) => {
                if (event.key === "Escape") {
                    setModelMenuOpen(false);
                } else if (["ArrowDown", "Enter", " "].includes(event.key)) {
                    event.preventDefault();
                    setModelMenuOpen(true);
                    const selectedOption = modelMenu.querySelector('[aria-selected="true"]');
                    (selectedOption || modelMenu.firstElementChild)?.focus();
                }
            };
            modelMenu.onkeydown = (event) => {
                const options = [...modelMenu.children];
                const current = options.indexOf(document.activeElement);
                if (event.key === "Escape") {
                    event.preventDefault();
                    setModelMenuOpen(false);
                    modelSelect.focus();
                } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
                    event.preventDefault();
                    let next = current;
                    if (event.key === "ArrowDown") next = Math.min(options.length - 1, current + 1);
                    if (event.key === "ArrowUp") next = Math.max(0, current - 1);
                    if (event.key === "Home") next = 0;
                    if (event.key === "End") next = options.length - 1;
                    options[next]?.focus();
                }
            };
            modelPicker.onfocusout = (event) => {
                if (!modelPicker.contains(event.relatedTarget)) setModelMenuOpen(false);
            };
            modelPicker.append(modelSelect, modelMenu);
            const saveButton = document.createElement("button");
            saveButton.type = "button";
            saveButton.className = "xh-button xh-editor-save";
            saveButton.textContent = this.saving ? "保存中…" : "保存";
            saveButton.disabled = this.saving || !this.hasLoadedDrafts();
            saveButton.onclick = () => this.saveAll();
            this.saveButton = saveButton;
            toolbar.append(modelPicker, saveButton);
            scroll.appendChild(toolbar);

            if (this.error) {
                const error = document.createElement("div");
                error.className = "xh-error";
                error.textContent = this.error;
                scroll.appendChild(error);
            }
            const info = this.currentInfo();
            if (!info) {
                const empty = document.createElement("div");
                empty.className = "xh-muted";
                empty.textContent = "请连接模型列表获取节点";
                scroll.appendChild(empty);
                return;
            }
            if (info.error) {
                const error = document.createElement("div");
                error.className = "xh-error";
                error.textContent = info.error;
                scroll.appendChild(error);
                return;
            }

            const key = sourceKey(info);
            const selected = this.selectedConfigKey(info);
            const configs = document.createElement("div");
            configs.className = "xh-buttons xh-editor-configs";
            const options = (info.configs || []).map((config) => ({
                key: String(Number(config.index)),
                label: `配置${Number(config.index)}`,
            }));
            options.push({ key: NEW_CONFIG, label: "添加" });
            for (const option of options) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "xh-button xh-editor-config";
                button.classList.toggle("selected", selected === option.key);
                button.classList.toggle("dirty", Boolean(this.state.drafts[key]?.[option.key]));
                button.textContent = option.label;
                button.onclick = () => {
                    this.state.selections[key] = option.key;
                    this.saveState();
                    this.render();
                };
                configs.appendChild(button);
                this.configButtons.set(option.key, button);
            }
            scroll.appendChild(configs);

            const values = this.effectiveValue(info, selected);
            const fields = document.createElement("div");
            fields.className = "xh-editor-fields";
            const textareas = {};
            for (const [side, label] of [["positive", "正向提示词"], ["negative", "负向提示词"]]) {
                const field = document.createElement("label");
                field.className = "xh-editor-field";
                const title = document.createElement("span");
                title.className = "xh-editor-label";
                title.textContent = label;
                const textarea = document.createElement("textarea");
                textarea.className = "xh-editor-text";
                textarea.value = values[side];
                textarea.disabled = this.saving;
                textarea.oninput = () => this.setDraft(
                    info,
                    selected,
                    textareas.positive.value,
                    textareas.negative.value,
                );
                textareas[side] = textarea;
                field.append(title, textarea);
                fields.appendChild(field);
            }
            scroll.appendChild(fields);
        },
        async refreshFromSource() {
            const sequence = ++this.refreshSequence;
            const source = connectedNode(node, "source");
            if (!source || ![STACK_NODE, MODEL_SOURCE_NODE].includes(nodeTypeId(source))) {
                this.infos = [];
                this.error = null;
                this.ensureSelections();
                this.render();
                return;
            }
            const sources = collectSourceEntries(source);
            if (!sources.length) {
                this.infos = [];
                this.error = null;
                this.ensureSelections();
                this.render();
                return;
            }
            try {
                const infos = await inspectSources(sources);
                if (sequence !== this.refreshSequence) return;
                this.infos = infos;
                this.error = null;
                this.ensureSelections();
                this.saveState();
                this.render();
            } catch (error) {
                if (sequence !== this.refreshSequence) return;
                this.infos = [];
                this.error = error.message || String(error);
                this.ensureSelections();
                this.render();
            }
        },
    };
    node.__xhPromptConfigEditor = controller;
    controller.ensureSelections();
    controller.render();
    return controller;
}

export function patch(nodeType) {
    const originalCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
        originalCreated?.apply(this, arguments);
        applyPortLabels(this);
        editorController(this);
        setTimeout(() => this.__xhPromptConfigEditor.refreshFromSource(), 0);
    };
    const originalConnections = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        setTimeout(() => this.__xhPromptConfigEditor?.refreshFromSource(), 0);
        return result;
    };
}
