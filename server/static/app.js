// 通用前端脚本：SSE 连接（断线降级为轻刷新，禁止裸整页重载）与软刷新工具

// 软刷新：保存滚动位置后重载，load 后恢复（按 URL 键控，10s 内有效）。
// 结构性事件（计算完成/发布/开闭场）确需重载时一律走这里，避免视口跳顶。
function softReload() {
  try {
    sessionStorage.setItem('__sr' + location.pathname + location.search,
      JSON.stringify({ y: window.scrollY || 0, t: Date.now() }));
  } catch (e) {}
  location.reload();
}
(function () {
  try {
    var k = '__sr' + location.pathname + location.search;
    var raw = sessionStorage.getItem(k);
    if (!raw) return;
    sessionStorage.removeItem(k);
    var d = JSON.parse(raw);
    if (Date.now() - d.t > 10000 || !d.y) return;
    setTimeout(function () { window.scrollTo(0, d.y); }, 0);
    setTimeout(function () { window.scrollTo(0, d.y); }, 150);
  } catch (e) {}
})();

function connectSSE(streamUrl, handlers, pollFn, pollMs) {
  pollMs = pollMs || 5000;
  var pollTimer = null, alive = false, debTimer = null, dirty = null;
  var badge = document.getElementById('net-badge');
  function setAlive(a) { alive = a; if (badge) badge.className = 'badge' + (a ? '' : ' off'); }
  // 500ms 窗口内多个事件合并为最后一个（风暴下只刷一次）；页面隐藏时挂起，
  // 回到前台补一次，避免后台无谓重载/重绘。
  function fire(name, payload) {
    dirty = { name: name, payload: payload };
    if (document.hidden) return;
    if (debTimer) clearTimeout(debTimer);
    debTimer = setTimeout(function () {
      debTimer = null;
      var d = dirty; dirty = null;
      if (d && handlers && handlers[d.name]) handlers[d.name](d.payload);
    }, 500);
  }
  function startPoll() {
    setAlive(false);
    if (!pollFn || pollTimer) return;   // 幂等：EventSource 自动重连会反复触发 onerror，不能重置轮询节奏
    pollTimer = setInterval(function () {
      if (document.hidden) return;
      // 输入保护：用户正在填表/查询时跳过本轮刷新，避免打断输入
      var ae = document.activeElement;
      var typing = ae && (ae.tagName === 'INPUT' || ae.tagName === 'TEXTAREA' ||
                          ae.tagName === 'SELECT' || ae.isContentEditable);
      if (typing) return;
      pollFn();
    }, pollMs);
  }
  function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && dirty && !debTimer) {
      var d = dirty; dirty = null;
      if (handlers && handlers[d.name]) handlers[d.name](d.payload);
    }
  });
  function connect() {
    try {
      var es = new EventSource(streamUrl);
      es.onopen = function () { setAlive(true); stopPoll(); };
      es.onerror = function () { setAlive(false); startPoll(); };
      Object.keys(handlers || {}).forEach(function (t) {
        es.addEventListener(t, function (e) {
          var payload = {};
          try { payload = JSON.parse(e.data).payload; } catch (err) {}
          fire(t, payload);
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
