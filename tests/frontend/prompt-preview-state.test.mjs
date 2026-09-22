import test from "node:test";
import assert from "node:assert/strict";
import {
    PREVIEW_CONTEXTS_KEY,
    isPreviewTokenEnabled,
    previewTokenKey,
    rowToPreviewRow,
    syncPreviewTokenState,
} from "../../web/features/prompt-preview/state.js";

function row(configIndex) {
    return rowToPreviewRow({
        source_name: "models/example.safetensors",
        display_name: "模型A",
        config_index: configIndex,
        positive: "face, hair",
        negative: "blur",
    });
}

test("prompt token switches are isolated by selected config", () => {
    const config1 = row(1);
    const config2 = row(2);
    let state = syncPreviewTokenState({}, [config1]);
    state[previewTokenKey(config1, "positive", 0)] = false;
    state[previewTokenKey(config1, "positive", 1)] = false;
    assert.equal(
        previewTokenKey(config1, "positive", 0),
        '["[\\"models/example.safetensors\\",1]","positive",0]',
    );
    assert.equal(
        previewTokenKey(config1, "positive", 0),
        '["[\\"models/example.safetensors\\",1]","positive",0]',
    );

    state = syncPreviewTokenState(state, [config2]);
    assert.equal(isPreviewTokenEnabled(state, config2, "positive", 0), true);
    assert.equal(isPreviewTokenEnabled(state, config2, "positive", 1), true);

    state = syncPreviewTokenState(state, [config1]);
    assert.equal(isPreviewTokenEnabled(state, config1, "positive", 0), false);
    assert.equal(isPreviewTokenEnabled(state, config1, "positive", 1), false);
    assert.notEqual(previewTokenKey(config1, "positive", 0), previewTokenKey(config2, "positive", 0));
});

test("legacy model-level switches migrate only to the current config", () => {
    const config1 = row(1);
    const config2 = row(2);
    const state = syncPreviewTokenState({ "模型A|positive|0": false }, [config1]);

    assert.equal(state["模型A|positive|0"], undefined);
    assert.equal(isPreviewTokenEnabled(state, config1, "positive", 0), false);
    assert.equal(isPreviewTokenEnabled(state, config2, "positive", 0), true);
    assert.deepEqual(state[PREVIEW_CONTEXTS_KEY], [config1.context_id]);
});
