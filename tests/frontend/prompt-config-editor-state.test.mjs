import test from "node:test";
import assert from "node:assert/strict";
import {
    NEW_CONFIG,
    applySaveResults,
    buildSavePayload,
    cleanEditorState,
    setDraft,
    sourceKey,
    stageConfigDeletion,
} from "../../web/features/prompt-config-editor/state.js";

const info = {
    source_name: "model.safetensors",
    folder_name: "loras",
    configs: [
        { index: 1, positive: "base", negative: "bad" },
        { index: 2, positive: "second", negative: "" },
    ],
};

test("editor state cleans malformed persisted values", () => {
    const state = cleanEditorState(JSON.stringify({
        selectedSource: sourceKey(info),
        selections: { valid: 1, empty: "", invalid: "oops", add: NEW_CONFIG },
        drafts: { bad: [], [sourceKey(info)]: { 1: { positive: "x", negative: 5 } } },
    }));
    assert.deepEqual(state.selections, { valid: "1", add: NEW_CONFIG });
    assert.deepEqual(state.drafts[sourceKey(info)]["1"], { positive: "x", negative: "" });
});

test("save payload is an immutable request snapshot", () => {
    const state = cleanEditorState("{}");
    setDraft(state, info, "1", { positive: "submitted", negative: "bad" });
    const request = buildSavePayload(state, [info]);
    setDraft(state, info, "1", { positive: "newer edit", negative: "bad" });
    assert.equal(request.sources[0].configs[0].positive, "submitted");
    const saved = { ...info, configs: [{ index: 1, positive: "submitted", negative: "bad" }, info.configs[1]] };
    const nextInfos = applySaveResults(state, [info], request, [saved]);
    assert.equal(nextInfos[0].configs[0].positive, "submitted");
    assert.equal(state.drafts[sourceKey(info)]["1"].positive, "newer edit");
});

test("new draft edits made after submission migrate to the saved index", () => {
    const state = cleanEditorState("{}");
    setDraft(state, info, NEW_CONFIG, { positive: "submitted", negative: "" });
    const request = buildSavePayload(state, [info]);
    setDraft(state, info, NEW_CONFIG, { positive: "newer", negative: "" });
    const saved = { ...info, configs: [...info.configs, { index: 3, positive: "submitted", negative: "" }] };
    applySaveResults(state, [info], request, [saved]);
    assert.equal(state.drafts[sourceKey(info)]["3"].positive, "newer");
    assert.equal(state.drafts[sourceKey(info)][NEW_CONFIG], undefined);
    assert.equal(state.selections[sourceKey(info)], "3");
});

test("staged deletion reindexes remaining configs", () => {
    const state = cleanEditorState("{}");
    stageConfigDeletion(state, info, "1");
    assert.deepEqual(state.drafts[sourceKey(info)].configs, [
        { index: 1, positive: "second", negative: "" },
    ]);
});
