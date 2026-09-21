// Pure persisted-state and save-payload logic for the prompt config editor.
export const NEW_CONFIG = "new";

export function sourceKey(source) {
    return JSON.stringify([String(source?.folder_name || "loras"), String(source?.source_name || "")]);
}

export function configValue(config) {
    return {
        positive: String(config?.positive || ""),
        negative: String(config?.negative || ""),
    };
}

function persistedConfigValue(config) {
    return {
        positive: typeof config?.positive === "string" ? config.positive : "",
        negative: typeof config?.negative === "string" ? config.negative : "",
    };
}

export function cleanEditorState(value) {
    try {
        const parsed = JSON.parse(String(value || "{}"));
        const selections = {};
        if (parsed?.selections && typeof parsed.selections === "object" && !Array.isArray(parsed.selections)) {
            for (const [key, selection] of Object.entries(parsed.selections)) {
                const numeric = Number(selection);
                if (selection === NEW_CONFIG || (Number.isInteger(numeric) && numeric > 0 && String(selection).trim() !== "")) {
                    selections[key] = String(selection);
                }
            }
        }
        const drafts = {};
        if (parsed?.drafts && typeof parsed.drafts === "object" && !Array.isArray(parsed.drafts)) {
            for (const [key, sourceDrafts] of Object.entries(parsed.drafts)) {
                if (!sourceDrafts || typeof sourceDrafts !== "object" || Array.isArray(sourceDrafts)) continue;
                const cleaned = {};
                if (Array.isArray(sourceDrafts.configs)) {
                    cleaned.configs = sourceDrafts.configs
                        .filter((item) => item && typeof item === "object")
                        .map((item, index) => ({ index: index + 1, ...persistedConfigValue(item) }));
                }
                for (const [configKey, draft] of Object.entries(sourceDrafts)) {
                    if (configKey === "configs") continue;
                    if (configKey !== NEW_CONFIG && !/^\d+$/.test(configKey)) continue;
                    if (!draft || typeof draft !== "object" || Array.isArray(draft)) continue;
                    cleaned[configKey] = persistedConfigValue(draft);
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

export function currentConfigs(state, info) {
    return state.drafts[sourceKey(info)]?.configs || info?.configs || [];
}

export function ensureSelections(state, infos) {
    const available = new Set(infos.map(sourceKey));
    if (!state.selectedSource || !available.has(state.selectedSource)) {
        state.selectedSource = infos.length ? sourceKey(infos[0]) : null;
    }
    for (const info of infos) {
        const key = sourceKey(info);
        const configs = currentConfigs(state, info);
        const indexes = new Set(configs.map((config) => String(Number(config.index))));
        const selected = String(state.selections[key] ?? "");
        if (selected === NEW_CONFIG || indexes.has(selected)) continue;
        state.selections[key] = configs.length ? String(Number(configs[0].index)) : NEW_CONFIG;
    }
    return state;
}

export function selectedConfigKey(state, info) {
    return String(state.selections[sourceKey(info)] ?? NEW_CONFIG);
}

export function baselineValue(state, info, configKey) {
    if (configKey === NEW_CONFIG) return { positive: "", negative: "" };
    const config = currentConfigs(state, info).find((item) => Number(item.index) === Number(configKey));
    return configValue(config);
}

export function effectiveValue(state, info, configKey) {
    return configValue(state.drafts[sourceKey(info)]?.[configKey] || baselineValue(state, info, configKey));
}

export function setDraft(state, info, configKey, value) {
    const key = sourceKey(info);
    const next = configValue(value);
    const baseline = baselineValue(state, info, configKey);
    const dirty = next.positive !== baseline.positive || next.negative !== baseline.negative;
    if (dirty) {
        state.drafts[key] ||= {};
        state.drafts[key][configKey] = next;
    } else if (state.drafts[key]) {
        delete state.drafts[key][configKey];
        if (!Object.keys(state.drafts[key]).length) delete state.drafts[key];
    }
    return dirty;
}

export function hasLoadedDrafts(state, infos) {
    return infos.some((info) => Object.keys(state.drafts[sourceKey(info)] || {}).length > 0);
}

export function canDeleteConfig(state, info, saving = false) {
    if (!info || info.error || saving) return false;
    const selected = selectedConfigKey(state, info);
    const key = sourceKey(info);
    if (selected === NEW_CONFIG) {
        const draft = state.drafts[key]?.[NEW_CONFIG];
        return Boolean(draft && (draft.positive || draft.negative));
    }
    return currentConfigs(state, info).some((config) => String(Number(config.index)) === selected);
}

export function clearNewDraft(state, info) {
    const key = sourceKey(info);
    if (!state.drafts[key]) return;
    delete state.drafts[key][NEW_CONFIG];
    if (!Object.keys(state.drafts[key]).length) delete state.drafts[key];
}

export function stageConfigDeletion(state, info, selected) {
    const key = sourceKey(info);
    const remaining = currentConfigs(state, info)
        .filter((config) => String(Number(config.index)) !== String(Number(selected)))
        .map((config, index) => ({
            index: index + 1,
            ...effectiveValue(state, info, String(Number(config.index))),
        }));
    state.drafts[key] ||= {};
    state.drafts[key].configs = remaining;
    for (const configKey of Object.keys(state.drafts[key])) {
        if (configKey !== "configs" && configKey !== NEW_CONFIG) delete state.drafts[key][configKey];
    }
    state.selections[key] = remaining.length
        ? String(Math.min(Number(selected), remaining.length))
        : NEW_CONFIG;
}

export function buildSavePayload(state, infos) {
    const sources = [];
    const addedIndexes = {};
    const draftSnapshots = {};
    for (const info of infos) {
        const key = sourceKey(info);
        const drafts = state.drafts[key];
        if (!drafts || !Object.keys(drafts).length || info.error) continue;
        const configs = (drafts.configs || info.configs || []).map((config) => ({
            index: Number(config.index),
            ...configValue(config),
        }));
        for (const [configKey, draft] of Object.entries(drafts)) {
            if (configKey === NEW_CONFIG || configKey === "configs") continue;
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
        draftSnapshots[key] = JSON.stringify(drafts);
    }
    return { sources, addedIndexes, draftSnapshots };
}

export function applySaveResults(state, infos, request, savedInfos) {
    const nextInfos = [...infos];
    const savedByKey = new Map(savedInfos.map((info) => [sourceKey(info), info]));
    for (const source of request.sources) {
        const key = sourceKey(source);
        const saved = savedByKey.get(key);
        if (!saved || saved.error) throw new Error(saved?.error || "保存结果不完整");
        const index = nextInfos.findIndex((info) => sourceKey(info) === key);
        if (index >= 0) nextInfos[index] = saved;
        if (JSON.stringify(state.drafts[key]) === request.draftSnapshots[key]) {
            delete state.drafts[key];
            if (request.addedIndexes[key] != null) state.selections[key] = String(request.addedIndexes[key]);
        } else if (request.addedIndexes[key] != null && state.drafts[key]?.[NEW_CONFIG]) {
            const addedIndex = String(request.addedIndexes[key]);
            state.drafts[key][addedIndex] = state.drafts[key][NEW_CONFIG];
            delete state.drafts[key][NEW_CONFIG];
            state.selections[key] = addedIndex;
        }
    }
    return nextInfos;
}
