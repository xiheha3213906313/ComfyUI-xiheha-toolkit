import test from "node:test";
import assert from "node:assert/strict";
import {
    buildSplitPayload,
    closestTimelineHandle,
    MIN_EDGE_GAP,
    moveTimelineHandle,
    parseSplitterState,
    round1,
    setSplitMode,
    usesSceneDetection,
    videoViewPath,
} from "../../web/features/smart-video-splitter/state.js";

test("splitter state restores video and normalizes timeline constraints", () => {
    const state = parseSplitterState(JSON.stringify({
        split_mode: "fuzzy", fuzzy_min: 12, target_duration: 5, fuzzy_max: 4, video: "sub/video.mp4",
    }));
    assert.equal(state.video, "sub/video.mp4");
    assert.ok(state.fuzzy_min <= state.target_duration);
    assert.ok(state.target_duration <= state.fuzzy_max);
    assert.ok(state.fuzzy_max - state.fuzzy_min >= MIN_EDGE_GAP);
    assert.equal(parseSplitterState("bad", "fallback.mp4").video, "fallback.mp4");
});

test("timeline movement enforces fuzzy and exact bounds", () => {
    let state = parseSplitterState('{"split_mode":"fuzzy","fuzzy_min":4,"target_duration":5,"fuzzy_max":6}');
    state = moveTimelineHandle(state, "min", 9);
    assert.equal(state.fuzzy_min, 5);
    state = moveTimelineHandle(state, "max", 3);
    assert.equal(state.fuzzy_max, 5.2);
    assert.equal(round1(state.fuzzy_max - state.fuzzy_min), MIN_EDGE_GAP);
    assert.equal(closestTimelineHandle({ ...state, split_mode: "exact" }, 10), "target");
});

test("scene mode keeps target dormant and constrains only minimum and maximum", () => {
    let state = parseSplitterState('{"split_mode":"scene","fuzzy_min":11,"target_duration":3,"fuzzy_max":5}');
    assert.equal(state.split_mode, "scene");
    assert.equal(state.fuzzy_min, 5);
    assert.equal(state.fuzzy_max, 11);
    assert.equal(state.target_duration, 3);

    state = moveTimelineHandle(state, "min", 14);
    assert.equal(state.fuzzy_min, 10.8);
    state = moveTimelineHandle(state, "max", 4);
    assert.equal(state.fuzzy_max, 11);
    assert.equal(moveTimelineHandle(state, "target", 9).target_duration, 3);
});

test("all three timeline modes round-trip through persisted state", () => {
    let state = parseSplitterState("{}");
    assert.equal(state.split_mode, "fuzzy");
    state = setSplitMode(state, "scene");
    assert.equal(state.split_mode, "scene");
    state = setSplitMode(state, "exact");
    assert.equal(state.split_mode, "exact");
    state = setSplitMode(state, "fuzzy");
    assert.equal(state.split_mode, "fuzzy");
});

test("white edge handles keep at least 0.2 seconds apart", () => {
    let state = parseSplitterState('{"split_mode":"fuzzy","fuzzy_min":8,"target_duration":8,"fuzzy_max":8}');
    assert.equal(state.fuzzy_min, 8);
    assert.equal(state.fuzzy_max, 8.2);
    state = moveTimelineHandle(state, "min", 15);
    assert.equal(state.fuzzy_min, 8);
    state = moveTimelineHandle(state, "max", 3);
    assert.equal(state.fuzzy_max, 8.2);
});

test("timeline regions route dark areas to edge handles and blue range to target", () => {
    const state = parseSplitterState('{"split_mode":"fuzzy","fuzzy_min":5,"target_duration":8,"fuzzy_max":11}');
    assert.equal(closestTimelineHandle(state, 4.9), "min");
    assert.equal(closestTimelineHandle(state, 5), "target");
    assert.equal(closestTimelineHandle(state, 9.5), "target");
    assert.equal(closestTimelineHandle(state, 11), "target");
    assert.equal(closestTimelineHandle(state, 11.1), "max");
});

test("scene timeline routes clicks to the nearest edge handle", () => {
    const state = parseSplitterState('{"split_mode":"scene","fuzzy_min":5,"target_duration":8,"fuzzy_max":11}');
    assert.equal(closestTimelineHandle(state, 6), "min");
    assert.equal(closestTimelineHandle(state, 8), "min");
    assert.equal(closestTimelineHandle(state, 8.1), "max");
    assert.equal(closestTimelineHandle(state, 10), "max");
});

test("target and scene modes show detection controls while exact mode hides them", () => {
    assert.equal(usesSceneDetection("fuzzy"), true);
    assert.equal(usesSceneDetection("scene"), true);
    assert.equal(usesSceneDetection("exact"), false);
});

test("request and preview URL construction use normalized state", () => {
    assert.equal(videoViewPath("nested/folder/video.mp4"), "/view?filename=video.mp4&type=input&subfolder=nested%2Ffolder");
    const payload = buildSplitPayload("42", "video.mp4", { split_mode: "exact", target_duration: 7 }, {
        force_rate: 24, format: "Wan", sensitivity: 0.7,
    });
    assert.equal(payload.node_id, "42");
    assert.equal(payload.split_mode, "exact");
    assert.equal(payload.target_duration, 7);
    assert.equal(payload.force_rate, 24);
    assert.equal(payload.format, "Wan");
    assert.equal(payload.algorithm, "智能自适应检测（推荐）");

    const scenePayload = buildSplitPayload("42", "video.mp4", {
        split_mode: "scene", fuzzy_min: 4, target_duration: 15, fuzzy_max: 6,
    });
    assert.equal(scenePayload.split_mode, "scene");
    assert.equal(scenePayload.fuzzy_min, 4);
    assert.equal(scenePayload.fuzzy_max, 6);
    assert.equal(scenePayload.target_duration, 15);
});
