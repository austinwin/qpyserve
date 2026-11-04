/* QPyServe Trace: local development diagnostics; no external telemetry. */
(() => {
  'use strict';
  if (window.__qpyserveTrace) return;
  window.__qpyserveTrace = true;

  const apiPrefixes = __QPYSERVE_API_PATHS__;
  const events = [];
  let requests = [];
  let open = false;
  const nativeFetch = window.fetch.bind(window);

  const requestInfo = (input) => {
    try {
      const url = new URL(input instanceof Request ? input.url : String(input), location.href);
      if (url.origin !== location.origin) return null;
      const prefix = apiPrefixes.find((p) => url.pathname === p || url.pathname.startsWith(p + '/'));
      if (!prefix) return null;
      // Client reports use a prefix and marker, never a raw parameter or URL query.
      return { path: prefix + (url.pathname === prefix ? '' : '/[redacted]') };
    } catch (_) { return null; }
  };
  const pathFor = (input) => {
    try {
      const url = new URL(String(input), location.href);
      return url.origin === location.origin ? url.pathname.split('/').pop() || '/' : '(external)';
    } catch (_) { return '(unknown)'; }
  };
  const nextId = () => {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID().replace(/-/g, '').slice(0, 16);
    }
    // A missing crypto API should not cause application requests to fail.
    return null;
  };
  const add = (event) => {
    events.push({time: new Date().toISOString(), ...event});
    if (events.length > 50) events.shift();
    if (open) render();
  };
  const classify = (status) => {
    if (status === 429) return 'rate_limited';
    if (status === 401 || status === 403) return 'access_denied';
    if (status === 404) return 'not_found';
    if (status >= 500) return 'server_error';
    if (status >= 400) return 'client_error';
    return 'ok';
  };
  const traceHeaders = (original, extra, id) => {
    const headers = new Headers(original instanceof Request ? original.headers : undefined);
    if (extra && extra.headers) {
      new Headers(extra.headers).forEach((value, key) => headers.set(key, value));
    }
    headers.set('x-qpyserve-trace-id', id);
    return headers;
  };

  window.fetch = function (...args) {
    const input = args[0];
    const info = requestInfo(input);
    if (!info) return nativeFetch(...args);
    const init = args[1] || {};
    const method = String(init.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const id = nextId();
    const start = performance.now();
    const invoke = id
      ? nativeFetch(input, {...init, headers: traceHeaders(input, init, id)})
      : nativeFetch(...args);
    return invoke.then((response) => {
      if (!response.ok) {
        add({kind: 'HTTP', category: classify(response.status), method, path: info.path,
          status: response.status, duration_ms: Math.round(performance.now() - start),
          trace_id: response.headers.get('x-qpyserve-trace-id') || id});
      }
      return response;
    }, (error) => {
      add({kind: 'Network', category: 'network_error', method, path: info.path,
        trace_id: id, name: error && error.name || 'FetchError'});
      throw error;
    });
  };

  // XMLHttpRequest/Axios uses the same correlation scheme as fetch.
  const XHR = window.XMLHttpRequest;
  if (XHR && XHR.prototype) {
    const originalOpen = XHR.prototype.open;
    const originalSend = XHR.prototype.send;
    XHR.prototype.open = function (method, url, ...rest) {
      this.__qpyserveInfo = {method: String(method).toUpperCase(), info: requestInfo(url)};
      return originalOpen.call(this, method, url, ...rest);
    };
    XHR.prototype.send = function (...args) {
      const record = this.__qpyserveInfo;
      if (record && record.info) {
        const id = nextId();
        const start = performance.now();
        if (id) {
          try { this.setRequestHeader('x-qpyserve-trace-id', id); } catch (_) { /* Keep request working. */ }
        }
        this.addEventListener('loadend', () => {
          const status = this.status || 0;
          if (status >= 400 || status === 0) {
            add({kind: status === 0 ? 'Network' : 'HTTP', category: status === 0
              ? 'network_error' : classify(status), method: record.method,
              path: record.info.path, status,
              duration_ms: Math.round(performance.now() - start),
              trace_id: this.getResponseHeader('x-qpyserve-trace-id') || id});
          }
        }, {once: true});
      }
      return originalSend.apply(this, args);
    };
  }

  window.addEventListener('error', (event) => {
    add({ kind: 'JavaScript', name: event.error?.name || 'Error',
      source: event.filename ? pathFor(event.filename) : '(unknown script)',
      line: event.lineno || null, column: event.colno || null });
  });
  window.addEventListener('unhandledrejection', (event) => {
    add({ kind: 'Promise', name: event.reason?.name || 'UnhandledRejection' });
  });

  const root = document.createElement('div');
  root.setAttribute('data-qpyserve-trace', '');
  const ui = root.attachShadow({mode: 'open'});
  ui.innerHTML = `
    <style>
      :host { all: initial; font: 13px/1.45 system-ui, sans-serif; color: #e9f1ff; }
      * { box-sizing: border-box; } button { font: inherit; cursor: pointer; }
      .launcher { position: fixed; z-index: 2147483000; right: 18px; bottom: 18px;
        border: 1px solid #506380; background: #15243b; color: #fff; padding: 10px 15px;
        border-radius: 999px; box-shadow: 0 5px 22px #0005; }
      .panel { position: fixed; z-index: 2147483000; right: 18px; bottom: 70px;
        width: min(420px, calc(100vw - 36px)); max-height: min(560px, calc(100vh - 92px));
        background: #101c30; border: 1px solid #405373; border-radius: 14px;
        box-shadow: 0 15px 40px #0008; overflow: hidden; display: none; }
      .panel.open { display: flex; flex-direction: column; }
      header { display: flex; justify-content: space-between; align-items: center;
        border-bottom: 1px solid #30415d; padding: 12px 14px; }
      header strong { font-size: 15px; }
      .sub { color: #aebfdb; font-size: 11px; }
      .toolbar { display: flex; gap: 8px; padding: 10px 12px; }
      .toolbar button, .close { background: #263b59; border: 1px solid #506380;
        border-radius: 7px; color: #fff; padding: 7px 11px; }
      .close { padding: 4px 9px; }
      .events { overflow: auto; min-height: 90px; padding: 0 12px 12px; }
      .event { padding: 10px 0; border-top: 1px solid #30415d; }
      .event-title { font-weight: 650; overflow-wrap: anywhere; }
      .danger { color: #ffb0a5; } .ok { color: #a8e6b0; }
      .detail { font-size: 11px; color: #acbedd; overflow-wrap: anywhere; }
      .empty { color: #acbedd; padding: 16px 0; }
      footer { border-top: 1px solid #30415d; padding: 8px 12px;
        color: #aebfdb; font-size: 11px; }
    </style>
    <button type="button" class="launcher" aria-label="Open QPyServe Trace">Trace</button>
    <section class="panel" aria-label="QPyServe Trace diagnostics">
      <header><div><strong>QPyServe Trace</strong><div class="sub">Local development only</div></div>
      <button class="close" type="button" aria-label="Close QPyServe Trace">×</button></header>
      <div class="toolbar"><button class="refresh" type="button">Refresh</button>
        <button class="copy" type="button">Copy AI report</button></div>
      <div class="events" role="log" aria-live="polite"></div>
      <footer>No request bodies, cookies or authorization headers are stored.</footer>
    </section>`;
  (document.body || document.documentElement).append(root);

  const panel = ui.querySelector('.panel');
  const listing = ui.querySelector('.events');
  const copy = ui.querySelector('.copy');

  async function refresh() {
    try {
      const response = await nativeFetch('/__qpyserve/trace', {cache: 'no-store'});
      if (!response.ok) throw new Error('Unavailable');
      requests = (await response.json()).requests || [];
    } catch (_) {
      requests = [];
      add({kind: 'Trace', name: 'Backend trace unavailable'});
    }
    render();
  }
  function render() {
    listing.replaceChildren();
    const list = [
      ...requests.map((x) => ({kind: 'FastAPI', ...x})), ...events
    ].sort((a, b) => String(b.time || '').localeCompare(String(a.time || ''))).slice(0, 60);
    if (!list.length) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = 'No API calls or errors yet. Try your application.';
      listing.append(empty);
    }
    for (const event of list) {
      const box = document.createElement('div'); box.className = 'event';
      const title = document.createElement('div'); title.className = 'event-title';
      title.textContent = event.kind === 'FastAPI'
        ? `${event.method} ${event.route} · ${event.status}`
        : `${event.kind} · ${event.method || event.name || ''} ${event.path || ''}`;
      title.classList.add(event.status >= 400 || event.kind !== 'FastAPI' ? 'danger' : 'ok');
      const detail = document.createElement('div'); detail.className = 'detail';
      detail.textContent = [event.duration_ms != null ? `${event.duration_ms} ms` : '',
        event.trace_id || event.id || '', event.category || '', event.exception || '', event.source || '']
        .filter(Boolean).join(' · ');
      box.append(title, detail); listing.append(box);
    }
  }
  function toggle() {
    open = !open;
    panel.classList.toggle('open', open);
    if (open) refresh();
  }
  ui.querySelector('.launcher').addEventListener('click', toggle);
  ui.querySelector('.close').addEventListener('click', toggle);
  ui.querySelector('.refresh').addEventListener('click', refresh);
  window.addEventListener('keydown', (event) => {
    if (event.altKey && event.shiftKey && event.key.toLowerCase() === 't') toggle();
  });
  copy.addEventListener('click', async () => {
    await refresh();
    const failed = requests.filter((r) => r.status >= 400 || r.exception);
    const linkedBrowser = events.map((event) => {
      const match = event.trace_id && requests.find((r) => r.id === event.trace_id);
      return match
        ? {...event, backend: {route: match.route, category: match.category,
          status: match.status, source: match.source || null}}
        : event;
    });
    const report = {
      format: 'qpyserve-trace-v2',
      generated_at: new Date().toISOString(),
      summary: {
        backend_requests: requests.length, backend_failures: failed.length,
        browser_events: events.length, correlated_events:
          linkedBrowser.filter((e) => e.backend).length,
      },
      backend_failures: failed.slice(-40),
      browser_events: linkedBrowser.slice(-50),
      recent_backend_requests: requests.slice(-20),
      privacy: 'No request bodies, secrets, raw URLs, or query strings collected. Review before sharing.',
      limitations: 'No automatic SQL or external HTTP tracing; unmatched requests cannot be diagnosed automatically.',
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      copy.textContent = 'Copied!';
    } catch (_) { copy.textContent = 'Copy blocked'; }
    setTimeout(() => { copy.textContent = 'Copy AI report'; }, 1500);
  });
})();
