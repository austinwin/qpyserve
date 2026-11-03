/* QPyServe Trace: local development diagnostics; no external telemetry. */
(() => {
  'use strict';
  if (window.__qpyserveTrace) return;
  window.__qpyserveTrace = true;

  const events = [];
  let requests = [];
  let open = false;
  const nativeFetch = window.fetch.bind(window);
  const pathFor = (input) => {
    try {
      const url = new URL(input instanceof Request ? input.url : String(input), location.href);
      if (url.origin !== location.origin) return '(external origin)';
      return url.pathname.split('/').map((part) => part.length > 24 ? '[id]' : part).join('/');
    } catch (_) { return '(invalid URL)'; }
  };
  const add = (event) => {
    events.push({ time: new Date().toISOString(), ...event });
    if (events.length > 50) events.shift();
    if (open) render();
  };

  window.fetch = function (...args) {
    const url = args[0];
    const path = pathFor(url);
    const method = String(args[1]?.method || (url instanceof Request ? url.method : 'GET')).toUpperCase();
    const start = performance.now();
    return nativeFetch(...args).then((res) => {
      if (!res.ok && !path.startsWith('/__qpyserve/')) {
        add({ kind: 'HTTP', method, path, status: res.status,
          duration_ms: Math.round(performance.now() - start),
          trace_id: res.headers.get('x-qpyserve-trace-id') || null });
      }
      return res;
    }, (err) => {
      if (!path.startsWith('/__qpyserve/')) add({ kind: 'Network', method, path, error: err?.name || 'FetchError' });
      throw err;
    });
  };

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
    ].sort((a, b) => b.time.localeCompare(a.time)).slice(0, 60);
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
        event.trace_id || event.id || '', event.exception || '', event.source || '']
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
    const report = {format: 'qpyserve-trace-v1', time: new Date().toISOString(),
      backend: requests, browser: [...events],
      warning: 'Review routes and errors for sensitive information before sharing.'};
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      copy.textContent = 'Copied!';
    } catch (_) { copy.textContent = 'Copy blocked'; }
    setTimeout(() => { copy.textContent = 'Copy AI report'; }, 1500);
  });
})();
