import test from "node:test";
import assert from "node:assert/strict";
import { afterNodeConfigure, createCleanupBag } from "../../web/shared/lifecycle.js";
import { ensureStylesheet } from "../../web/shared/stylesheets.js";

test("stylesheet loader installs each id once", () => {
    const links = [];
    const documentRef = {
        getElementById: (id) => links.find((link) => link.id === id) || null,
        createElement: () => ({}),
        head: { appendChild: (link) => links.push(link) },
    };
    ensureStylesheet("test-once", "/first.css", documentRef);
    ensureStylesheet("test-once", "/second.css", documentRef);
    assert.equal(links.length, 1);
    assert.equal(links[0].href, "/first.css");
});

test("controller cleanup registry runs in reverse and is idempotent", () => {
    const calls = [];
    const bag = createCleanupBag();
    bag.add(() => calls.push("first"));
    bag.add(() => calls.push("second"));
    assert.equal(bag.size, 2);
    bag.run();
    bag.run();
    assert.deepEqual(calls, ["second", "first"]);
    assert.equal(bag.size, 0);
});

test("configuration restoration runs after ComfyUI applies serialized widget values", () => {
    function NodeType() {}
    NodeType.prototype.onConfigure = function (info) {
        this.widgetValue = info.savedValue;
        this.calls.push("comfy");
        return "configured";
    };
    afterNodeConfigure(NodeType, function () {
        this.restoredValue = this.widgetValue;
        this.calls.push("extension");
    });

    const node = new NodeType();
    node.widgetValue = "default";
    node.calls = [];
    const result = node.onConfigure({ savedValue: "persisted" });

    assert.equal(result, "configured");
    assert.equal(node.restoredValue, "persisted");
    assert.deepEqual(node.calls, ["comfy", "extension"]);
});
