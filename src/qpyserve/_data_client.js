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

  return Object.freeze({
    schema: async (signal) => (await request("", { signal })).json(),
    query: async (query = {}, signal) => (await runQuery(query, "json", signal)).json(),
    // Returns an Arrow IPC Stream. Decode with tableFromIPC(bytes) from apache-arrow.
    arrow: async (query = {}, signal) =>
      new Uint8Array(await (await runQuery(query, "arrow", signal)).arrayBuffer()),
  });
}
