// 通用前端脚本：SSE 连接（带降级轮询由页面各自处理）与徽标
function connectSSE(streamUrl, handlers, pollFn, pollMs) {
  pollMs = pollMs || 5000;
  var es = null, pollTimer = null, alive = false;
  var badge = document.getElementById('net-badge');
  function setAlive(a) { alive = a; if (badge) badge.className = 'badge' + (a ? '' : ' off'); }
  function startPoll() {
    setAlive(false);
    if (!pollFn) return;
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollFn, pollMs);
    pollFn();
  }
  function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }
  function connect() {
    try {
      es = new EventSource(streamUrl);
      es.onopen = function () { setAlive(true); stopPoll(); };
      es.onerror = function () { setAlive(false); startPoll(); };
      Object.keys(handlers || {}).forEach(function (t) {
        es.addEventListener(t, function (e) {
          var payload = {};
          try { payload = JSON.parse(e.data).payload; } catch (err) {}
          handlers[t](payload);
        });
      });
    } catch (e) { startPoll(); }
  }
  connect();
}

async function api(method, url, body) {
  var opt = { method: method, headers: {} };
  if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
  var r = await fetch(url, opt);
  var data = null;
  try { data = await r.json(); } catch (e) {}
  if (!r.ok) { throw new Error((data && data.detail) || ('HTTP ' + r.status)); }
  return data;
}
