import test from "node:test";
import assert from "node:assert/strict";
import {
    parseTooltipString,
    renderTooltipContent,
    resolveTooltipData,
} from "../../web/shared/tooltip/data.js";

test("native multiline tooltip parsing is isolated from DOM runtime", () => {
    const parsed = parseTooltipString("【检测算法】\n说明文本\n• 阈值：0.5");
    assert.deepEqual(parsed, {
        title: "检测算法", badge: "参数说明", desc: "说明文本", details: ["阈值：0.5"],
    });
    assert.equal(resolveTooltipData({ name: "format", tooltip: "[格式]\n说明" }).title, "格式");
});

test("tooltip renderer escapes user-controlled strings", () => {
    const rendered = renderTooltipContent({ title: "<script>", badge: "x", desc: "<img>", details: ["<b>bad</b>"] });
    assert.doesNotMatch(rendered, /<script>|<img>|<b>bad<\/b>/);
    assert.match(rendered, /&lt;script&gt;/);
});
