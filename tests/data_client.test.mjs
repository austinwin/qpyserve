import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const source = readFileSync("src/qpyserve/_data_client.js", "utf8");
const { dataset, data } = await import(
  "data:text/javascript;base64," + Buffer.from(source).toString("base64")
);

test("client validates names and same-origin prefix", () => {
  assert.throws(() => dataset("../secret"), /Invalid/);
  assert.throws(() => dataset("_hidden"), /Invalid/);
  assert.throws(() => dataset("pipes", { base: "https://untrusted.example" }), /same-origin/);
  assert.throws(() => dataset("pipes", { base: "//untrusted.example" }), /same-origin/);
});

test("client requests bounded JSON rows with credentials and abort", async () => {
  const calls = [];
  globalThis.fetch = async (url, opts) => {
    calls.push({ url, opts });
    if (String(url).endsWith("/pipes")) {
      return new Response(JSON.stringify({
        columns: [{ name: "id", type: "BIGINT" }]
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    return new Response(JSON.stringify({
      rows: [{ id: 1 }], has_more: true, limit: 1, offset: 0
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  const bridge = dataset("pipes", {
    headers: { "X-Token": "private" }, credentials: "include"
  });
  assert.equal((await bridge.schema()).columns[0].name, "id");
  const controller = new AbortController();
  const query = { columns: ["id"], limit: 1 };
  const page = await bridge.query(query, controller.signal);
  assert.equal(page.rows[0].id, 1);
  assert.equal(page.has_more, true);
  assert.equal(calls[1].url, "/api/data/pipes/query?format=json");
  assert.equal(calls[1].opts.method, "POST");
  assert.equal(calls[1].opts.credentials, "include");
  assert.equal(calls[1].opts.headers["X-Token"], "private");
  assert.equal(calls[1].opts.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[1].opts.body), query);
  assert.equal(calls[1].opts.signal, controller.signal);
});

test("Arrow client returns binary, and errors retain HTTP status", async () => {
  const bridge = dataset("pipes");
  globalThis.fetch = async (url) => {
    assert.equal(String(url), "/api/data/pipes/query?format=arrow");
    return new Response(new Uint8Array([1, 2, 3, 4]), { status: 200 });
  };
  assert.deepEqual([...await bridge.arrow({limit: 4})], [1, 2, 3, 4]);
  globalThis.fetch = async () => new Response(
    JSON.stringify({ detail: "Forbidden" }),
    { status: 403, headers: { "content-type": "application/json" } }
  );
  await assert.rejects(
    () => bridge.query({limit: 1}),
    error => error.status === 403 && /Forbidden/.test(error.message)
  );
});


async function waitFor(condition, timeoutMs = 3500) {
  const expires = Date.now() + timeoutMs;
  while (!condition() && Date.now() < expires) {
    await new Promise(resolve => setTimeout(resolve, 20));
  }
  assert.ok(condition(), "Timed out waiting for data event");
}

test("data() alias and rows() simplify a dashboard fetch", async () => {
  globalThis.fetch = async (url) => {
    assert.equal(String(url), "/api/data/pumpage/query?format=json");
    return new Response(JSON.stringify({rows: [{mgd: 10}], has_more: false}), {
      status: 200, headers: { "content-type": "application/json" }
    });
  };
  assert.deepEqual(await data("pumpage").rows(), [{mgd: 10}]);
});

test("watch() refetches only when file version changes, then stops", async () => {
  let revision = "first";
  let fetches = 0;
  const received = [];
  const errors = [];
  globalThis.fetch = async (url) => {
    if (String(url).endsWith("/version")) {
      return new Response(JSON.stringify({version: revision}), {
        status: 200, headers: { "content-type": "application/json" }
      });
    }
    assert.equal(String(url), "/api/data/pumpage/query?format=json");
    fetches += 1;
    return new Response(JSON.stringify({rows: [{seq: fetches}], has_more: false}), {
      status: 200, headers: { "content-type": "application/json" }
    });
  };
  const stop = data("pumpage").watch(
    page => received.push(page.rows[0].seq),
    { intervalMs: 1000, onError: error => errors.push(error) }
  );
  try {
    await waitFor(() => received.length === 1);
    await new Promise(resolve => setTimeout(resolve, 1120));
    assert.equal(fetches, 1, "Unchanged sources must not repeat expensive query");
    revision = "second";
    await waitFor(() => received.length === 2);
    assert.deepEqual(received, [1, 2]);
    assert.equal(errors.length, 0);
  } finally {
    stop();
  }
});

test("watch() rejects invalid polling and callback options", () => {
  const source = data("pumpage");
  assert.throws(() => source.watch(null), /callback/);
  assert.throws(() => source.watch(() => {}, {intervalMs: 10}), /at least 1000/);
  assert.throws(() => source.watch(() => {}, {onError: true}), /onError/);
});
