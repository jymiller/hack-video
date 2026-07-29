const $ = id => document.getElementById(id);

function stat(m, c) {
  const el = $('stat');
  if (!el) return;
  el.textContent = String(m).toUpperCase().slice(0, 60);
  el.style.color = c || 'var(--vfd)';
}

let logN = 0;
function logCall(meth, path, status, data) {
  const box = $('log');
  if (!box) return;
  const d = document.createElement('div');
  d.className = 'log';
  const cls = status >= 200 && status < 300 ? 'b-ok' : 'b-err';
  d.innerHTML = `<div class="h"><span class="meth">${meth}</span>
    <span class="path">${path}</span><span class="badge ${cls}">${status}</span></div>
    <pre>${JSON.stringify(data, null, 2).slice(0, 20000)}</pre>`;
  d.querySelector('.h').onclick = () => d.classList.toggle('open');
  box.prepend(d);
  logN++;
  if ($('logCount')) $('logCount').textContent = `(${logN})`;
}

async function api(meth, path, body, isForm) {
  const opt = { method: meth };
  if (body && !isForm) { opt.headers = { 'Content-Type': 'application/json' }; opt.body = JSON.stringify(body); }
  if (isForm) opt.body = body;
  const r = await fetch(path, opt);
  const j = await r.json().catch(() => ({}));
  logCall(meth, path, r.status, j);
  return j;
}

function toggleLog() {
  const s = $('logSect'), collapsed = s.classList.toggle('collapsed');
  s.classList.toggle('grow', !collapsed);
  $('logBtn').textContent = collapsed ? 'show' : 'hide';
}
