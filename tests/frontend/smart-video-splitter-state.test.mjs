import test from "node:test";
import assert from "node:assert/strict";
import {
    buildSplitPayload,
    closestTimelineHandle,
    moveTimelineHandle,
    parseSplitterState,
    videoViewPath,
} from "../../web/features/smart-video-splitter/state.js";

test("splitter state restores video and normalizes timeline constraints", () => {
    const state = parseSplitterState(JSON.stringify({
        split_mode: "fuzzy", fuzzy_min: 12, target_duration: 5, fuzzy_max: 4, video: "sub/video.mp4",
    }));
    assert.equal(state.video, "sub/video.mp4");
    assert.ok(state.fuzzy_min <= state.target_duration);
    assert.ok(state.target_duration <= state.fuzzy_max);
    assert.equal(parseSplitterState("bad", "fallback.mp4").video, "fallback.mp4");
});

test("timeline movement enforces fuzzy and exact bounds", () => {
    let state = parseSplitterState('{"split_mode":"fuzzy","fuzzy_min":4,"target_duration":5,"fuzzy_max":6}');
    state = moveTimelineHandle(state, "min", 9);
    assert.equal(state.fuzzy_min, 5);
    state = moveTimelineHandle(state, "max", 3);
    assert.equal(state.fuzzy_max, 5);
    assert.equal(closestTimelineHandle({ ...state, split_mode: "exact" }, 10), "target");
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
});
