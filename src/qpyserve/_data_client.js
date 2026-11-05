/* QPyServe Data Bridge: tiny dependency-free browser client for bounded queries.
 * Native Arrow decoding is deliberately delegated to the established apache-arrow package.
 */
const NAME = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;

export function dataset(name, options = {}) {
  if (typeof name !== "string" || !NAME.test(name) || name.startsWith("_")) {
    throw new TypeError("Invalid QPyServe dataset name");
  }
  const base = options.base ?? "/api/data";
  if (typeof base !== "string" || !base.startsWith("/") || base.startsWith("//")) {
    throw new TypeError("Data Bridge base must be a same-origin URL path");
  }
  const endpoint = base.replace(/\/$/, "") + "/" + encodeURIComponent(name);
  const authHeaders = options.headers ?? {};
  const credentials = options.credentials ?? "same-origin";

  async function request(path, init = {}) {
    const response = await fetch(endpoint + path, {
      credentials,
      ...init,
      headers: { ...authHeaders, ...(init.headers ?? {}) },
    });
    if (!response.ok) {
      let message = `Data Bridge failed: HTTP ${response.status}`;
      try {
        const error = await response.json();
        if (typeof error.detail === "string") message += `: ${error.detail}`;
      } catch {
        // Preserve the original response status for non-JSON server failures.
      }
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return response;
  }

  function runQuery(query = {}, format = "json", signal) {
    return request("/query?format=" + encodeURIComponent(format), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(query),
      signal,
    });
  }

  function watch(onData, options = {}) {
    if (typeof onData !== "function") {
      throw new TypeError("watch(onData) expects a callback");
    }
    const { query = {}, intervalMs = 5000, onError } = options;
    if (!Number.isSafeInteger(intervalMs) || intervalMs < 1000) {
      throw new RangeError("watch intervalMs must be at least 1000 milliseconds");
    }
    if (onError !== undefined && typeof onError !== "function") {
      throw new TypeError("watch onError must be a callback");
    }

    let stopped = false;
    let timer = null;
    let active = null;
    let loaded = false;
    let lastVersion;

    async function tick() {
      const controller = new AbortController();
      active = controller;
      try {
        // Cheap file-stat revision check. A custom relation with no revision
        // token falls back to refreshing the bounded query each interval.
        const current = await (await request("/version", {
          signal: controller.signal,
        })).json();
        const version = current.version;
        if (!loaded || version == null || version !== lastVersion) {
          const page = await (await runQuery(query, "json", controller.signal)).json();
          if (stopped) return;
          lastVersion = version;
          loaded = true;
          onData(page);
        }
      } catch (error) {
        if (!stopped && error?.name !== "AbortError") {
          if (onError) onError(error);
          else console.error("[qpyserve] Data watch failed", error);
        }
      } finally {
        if (active === controller) active = null;
        if (!stopped) timer = setTimeout(tick, intervalMs);
      }
    }
    void tick();

    // Clean up in a React useEffect return or Vue onUnmounted hook.
    return () => {
      stopped = true;
      if (timer !== null) clearTimeout(timer);
      active?.abort();
    };
  }

  return Object.freeze({
    schema: async (signal) => (await request("", { signal })).json(),
    version: async (signal) => (await request("/version", { signal })).json(),
    query: async (query = {}, signal) => (await runQuery(query, "json", signal)).json(),
    rows: async (query = {}, signal) =>
      (await (await runQuery(query, "json", signal)).json()).rows,
    watch,
    // Returns an Arrow IPC Stream. Decode with tableFromIPC(bytes) from apache-arrow.
    arrow: async (query = {}, signal) =>
      new Uint8Array(await (await runQuery(query, "arrow", signal)).arrayBuffer()),
  });
}

// Shorter, intuitive entry point. Keep dataset() fully backward compatible.
export const data = dataset;
