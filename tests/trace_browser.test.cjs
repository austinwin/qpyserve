"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {test} = require("node:test");
const path = require("node:path");

const source = fs.readFileSync(
  path.join(__dirname, "../src/qpyserve/_trace_client.js"), "utf8"
).replace("__QPYSERVE_API_PATHS__", JSON.stringify(["/api"]));

class Control {
  constructor() {
    this.listeners = {};
    this.classList = {toggle() {}, add() {}};
    this.textContent = "";
    this.children = [];
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute() {}
}

function browser(responses) {
  const controls = {};
  const shadow = {
    set innerHTML(_html) {},
    querySelector(selector) {
      if (!controls[selector]) controls[selector] = new Control();
      return controls[selector];
    },
  };
  const root = new Control();
  root.attachShadow = () => shadow;
  const windowEvents = {};
  const nativeCalls = [];
  const clipboard = {report: ""};
  const window = {
    crypto: {randomUUID: () => "01234567-89ab-cdef-0123-456789abcdef"},
    fetch: (input, init) => {
      nativeCalls.push({input, init});
      return Promise.resolve(responses(input, init));
    },
    addEventListener: (event, fn) => { windowEvents[event] = fn; },
  };
  const context = {
    window, Request, Headers, URL, location: {href: "http://localhost:1111/", origin: "http://localhost:1111"},
    document: {createElement: () => root, body: {append() {}}},
    performance: {now: () => 100},
    navigator: {clipboard: {writeText: async (value) => { clipboard.report = value; }}},
    setTimeout: () => {},
  };
  vm.runInNewContext(source, context);
  return {window, controls, nativeCalls, clipboard, windowEvents};
}

test("real failing API request correlates and redacts private URL segments", async () => {
  const env = browser((input, init) => {
    if (input === "/__qpyserve/trace") {
      return new Response(JSON.stringify({requests: [{
        id: "0123456789abcdef", time: "2026-11-04T03:10:00Z", method: "GET", route: "/api/items/{item_id}",
        status: 503, category: "server_error", duration_ms: 12.5
      }]}), {status: 200, headers: {"content-type": "application/json"}});
    }
    return new Response("unavailable", {status: 503, headers: {
      "x-qpyserve-trace-id": "0123456789abcdef"
    }});
  });
  const response = await env.window.fetch("/api/items/secret-42?token=DO_NOT_LEAK");
  assert.equal(response.status, 503);
  assert.equal(env.nativeCalls[0].init.headers.get("x-qpyserve-trace-id"), "0123456789abcdef");
  await env.controls[".copy"].listeners.click();
  const report = JSON.parse(env.clipboard.report);
  assert.equal(report.summary.backend_failures, 1);
  assert.equal(report.summary.correlated_events, 1);
  assert.equal(report.browser_events[0].path, "/api/[redacted]");
  assert.equal(report.browser_events[0].backend.route, "/api/items/{item_id}");
  assert.equal(report.browser_events[0].category, "server_error");
  assert.ok(!env.clipboard.report.includes("DO_NOT_LEAK"));
  assert.ok(!env.clipboard.report.includes("secret-42"));
});

test("cross-origin requests are not modified by QPyServe", async () => {
  const env = browser(() => new Response("ok", {status: 200}));
  await env.window.fetch("https://example.org/api/private?token=SECRET");
  assert.equal(env.nativeCalls[0].init, undefined);
});

test("browser exception names do not disclose exception messages", async () => {
  const env = browser((input) => {
    if (input === "/__qpyserve/trace") {
      return new Response(JSON.stringify({requests: []}), {status: 200});
    }
    return new Response("ok", {status: 200});
  });
  env.windowEvents.error({
    error: {name: "TypeError", message: "PRIVATE_PASSWORD"},
    filename: "http://localhost:1111/assets/bundle.js", lineno: 7, colno: 4,
  });
  await env.controls[".copy"].listeners.click();
  const report = JSON.parse(env.clipboard.report);
  assert.equal(report.browser_events[0].name, "TypeError");
  assert.ok(!env.clipboard.report.includes("PRIVATE_PASSWORD"));
});
