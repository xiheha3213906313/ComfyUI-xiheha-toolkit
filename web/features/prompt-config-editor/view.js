import {
    NEW_CONFIG,
    canDeleteConfig,
    currentConfigs,
    effectiveValue,
    hasLoadedDrafts,
    selectedConfigKey,
    sourceKey,
} from "./state.js";

export function cleanupEditorView(controller) {
    controller.closeDialog();
    controller.cleanupModelMenu?.();
    controller.cleanupModelMenu = null;
}

function renderModelPicker(controller, toolbar) {
    const picker = document.createElement("div");
    picker.className = "xh-editor-model-picker";
    const select = document.createElement("button");
    select.type = "button";
    select.className = "xh-editor-model-select";
    select.setAttribute("aria-haspopup", "listbox");
    select.setAttribute("aria-expanded", "false");
    const selectedInfo = controller.currentInfo();
    const label = document.createElement("span");
    label.className = "xh-editor-model-label";
    label.textContent = selectedInfo?.display_name || selectedInfo?.source_name || "无可用模型";
    const arrow = document.createElement("span");
    arrow.className = "xh-editor-model-arrow";
    arrow.setAttribute("aria-hidden", "true");
    select.append(label, arrow);

    const menu = document.createElement("div");
    menu.className = "xh-editor-model-menu";
    menu.setAttribute("role", "listbox");
    menu.hidden = true;
    for (const info of controller.infos) {
        const key = sourceKey(info);
        const option = document.createElement("button");
        option.type = "button";
        option.className = "xh-editor-model-option";
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", String(key === controller.state.selectedSource));
        option.textContent = info.display_name || info.source_name;
        option.onclick = () => {
            setOpen(false);
            controller.selectSource(key);
        };
        menu.appendChild(option);
    }
    select.disabled = !controller.infos.length || controller.saving;

    const onOutsidePointer = (event) => {
        const NodeCtor = document.defaultView?.Node;
        if (!event.target || (NodeCtor && !(event.target instanceof NodeCtor)) || !picker.contains(event.target)) {
            setOpen(false);
        }
    };
    const onOutsideKey = (event) => {
        if (event.key !== "Escape") return;
        event.preventDefault();
        setOpen(false);
        select.focus();
    };
    const setOpen = (open) => {
        if (select.disabled) return;
        const next = Boolean(open);
        if (menu.hidden === !next) return;
        menu.hidden = !next;
        select.classList.toggle("open", next);
        select.setAttribute("aria-expanded", String(next));
        if (next) {
            document.addEventListener("pointerdown", onOutsidePointer, true);
            document.addEventListener("keydown", onOutsideKey, true);
            controller.cleanupModelMenu = () => {
                document.removeEventListener("pointerdown", onOutsidePointer, true);
                document.removeEventListener("keydown", onOutsideKey, true);
            };
        } else {
            controller.cleanupModelMenu?.();
            controller.cleanupModelMenu = null;
        }
    };
    select.onclick = () => setOpen(menu.hidden);
    select.onkeydown = (event) => {
        if (event.key === "Escape") setOpen(false);
        if (!["ArrowDown", "Enter", " "].includes(event.key)) return;
        event.preventDefault();
        setOpen(true);
        (menu.querySelector('[aria-selected="true"]') || menu.firstElementChild)?.focus();
    };
    menu.onkeydown = (event) => {
        const options = [...menu.children];
        const current = options.indexOf(document.activeElement);
        if (event.key === "Escape") {
            event.preventDefault();
            setOpen(false);
            select.focus();
            return;
        }
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        let next = current;
        if (event.key === "ArrowDown") next = Math.min(options.length - 1, current + 1);
        if (event.key === "ArrowUp") next = Math.max(0, current - 1);
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = options.length - 1;
        options[next]?.focus();
    };
    picker.onfocusout = (event) => {
        if (!picker.contains(event.relatedTarget)) setOpen(false);
    };
    picker.append(select, menu);
    toolbar.appendChild(picker);
}

function renderToolbar(controller) {
    const toolbar = document.createElement("div");
    toolbar.className = "xh-editor-toolbar";
    renderModelPicker(controller, toolbar);
    const info = controller.currentInfo();
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "xh-button xh-editor-delete";
    deleteButton.textContent = "删除";
    deleteButton.disabled = !canDeleteConfig(controller.state, info, controller.saving);
    deleteButton.onclick = () => controller.requestDelete(info);
    controller.deleteButton = deleteButton;
    const saveButton = document.createElement("button");
    saveButton.type = "button";
    saveButton.className = "xh-button xh-editor-save";
    saveButton.textContent = controller.saving ? "保存中…" : "保存";
    saveButton.disabled = controller.saving || !hasLoadedDrafts(controller.state, controller.infos);
    saveButton.onclick = () => controller.saveAll();
    controller.saveButton = saveButton;
    toolbar.append(deleteButton, saveButton);
    return toolbar;
}

function renderConfigFields(controller, info) {
    const key = sourceKey(info);
    const selected = selectedConfigKey(controller.state, info);
    const buttons = document.createElement("div");
    buttons.className = "xh-buttons xh-editor-configs";
    const options = currentConfigs(controller.state, info).map((config) => ({
        key: String(Number(config.index)), label: `配置${Number(config.index)}`,
    }));
    options.push({ key: NEW_CONFIG, label: "添加" });
    for (const option of options) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "xh-button xh-editor-config";
        button.classList.toggle("selected", selected === option.key);
        button.classList.toggle("dirty", Boolean(controller.state.drafts[key]?.[option.key]));
        button.textContent = option.label;
        button.onclick = () => controller.selectConfig(info, option.key);
        buttons.appendChild(button);
        controller.configButtons.set(option.key, button);
    }
    controller.scroll.appendChild(buttons);
    const values = effectiveValue(controller.state, info, selected);
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
        textarea.disabled = controller.saving;
        textarea.oninput = () => controller.updateDraft(info, selected, textareas.positive.value, textareas.negative.value);
        textareas[side] = textarea;
        field.append(title, textarea);
        fields.appendChild(field);
    }
    controller.scroll.appendChild(fields);
}

export function renderEditorView(controller) {
    cleanupEditorView(controller);
    controller.scroll.textContent = "";
    controller.configButtons.clear();
    controller.scroll.appendChild(renderToolbar(controller));
    if (controller.error) {
        const error = document.createElement("div");
        error.className = "xh-error";
        error.textContent = controller.error;
        controller.scroll.appendChild(error);
    }
    const info = controller.currentInfo();
    if (!info) {
        const empty = document.createElement("div");
        empty.className = "xh-muted";
        empty.textContent = "请连接模型列表获取节点";
        controller.scroll.appendChild(empty);
        return;
    }
    if (info.error) {
        const error = document.createElement("div");
        error.className = "xh-error";
        error.textContent = info.error;
        controller.scroll.appendChild(error);
        return;
    }
    renderConfigFields(controller, info);
}

export function showConfirmDialog(controller, { title = "提示", message, onConfirm }) {
    controller.closeDialog();
    const overlay = document.createElement("div");
    overlay.className = "xh-dialog-overlay";
    overlay.onclick = (event) => { if (event.target === overlay) controller.closeDialog(); };
    overlay.onkeydown = (event) => {
        if (event.key === "Escape") { event.stopPropagation(); controller.closeDialog(); }
    };
    const dialog = document.createElement("div");
    dialog.className = "xh-dialog";
    const titleElement = document.createElement("div");
    titleElement.className = "xh-dialog-title";
    titleElement.textContent = title;
    const messageElement = document.createElement("div");
    messageElement.className = "xh-dialog-message";
    messageElement.textContent = message;
    const actions = document.createElement("div");
    actions.className = "xh-dialog-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "xh-button xh-dialog-btn";
    cancel.textContent = "取消";
    cancel.onclick = () => controller.closeDialog();
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "xh-button xh-dialog-btn xh-dialog-btn-danger";
    confirm.textContent = "确定";
    confirm.onclick = () => { controller.closeDialog(); onConfirm?.(); };
    actions.append(cancel, confirm);
    dialog.append(titleElement, messageElement, actions);
    overlay.appendChild(dialog);
    controller.root.appendChild(overlay);
    controller.currentDialog = overlay;
    confirm.focus();
}
