/* XK-LAB 的离线壳（2026-11-07 站主「把项目全做完」；2026-11-07 晚 A8 补完）
   策略：
   - HTML / JSON / 接口：network-first（永远先要新的，断网才回缓存）—— 站点靠数据新鲜度，不能给用户看旧数字。
     ★A8 追加：HTML 类请求最多等 3 秒（HTML_TIMEOUT），超时就先给缓存，别让慢网把首屏吊到白屏；
       网络那一路继续跑，跑成功照样回写缓存 —— 下次进来就是新的。
   - 指纹化静态资源（带 hash 的 /js/xk-*.min.<hash>.js、/css/*、/kurisu/**、/images/**）：cache-first
   - 只缓存同源 GET；跨域（demo.xiaokeqing.cn 接口）不拦截、不进缓存
   - ★A8 追加「离线提示条」：回缓存兜底时给受控页面 postMessage({xk:'offline'})，
     DOM 由页面侧的 assets/js/xk-ux.js 插一行「当前离线，显示的是缓存版本」（SW 碰不到 DOM，只负责通知）。
   注意：这个 SW 不做预缓存清单（站点 240MB 级），只在访问时顺带存，避免装一次就吞配额。
   改 VER ⇒ activate 里会把旧版本的两个 cache 一起删掉（v1 的缓存不会被 v2 复用）。 */
const VER = 'xk-v3';
const IMG_MAX = 60;           /* 最多留 60 张图片，超过按 LRU 丢 */
const HTML_TIMEOUT = 3000;    /* HTML network-first 的等待上限（毫秒），到点回缓存 */
const CACHE_HTML = VER + '-html';
const CACHE_ASSET = VER + '-asset';

/* 最近一次「回缓存兜底」的时间戳：页面启动时来问一句（{xk:'state'}），
   60 秒内兜底过就补插一次提示条 —— 断网首屏时消息常常比页面脚本先到，光靠广播会丢。 */
let lastFallback = 0;

self.addEventListener('install', (e) => { self.skipWaiting(); });

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keep = new Set([CACHE_HTML, CACHE_ASSET]);
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

function isAsset(url) {
  return /\/js\/.+\.(min\.)?[0-9a-f]{8,}\.js$/.test(url.pathname) ||
         /\/css\/.+[0-9a-f]{8,}\.css$/.test(url.pathname) ||
         /^\/(kurisu|images)\//.test(url.pathname);
}

/* 通知所有受控页面：这一页是缓存版本。失败静默（没有受控页面/浏览器不支持都无所谓）。 */
function notifyOffline(reason) {
  lastFallback = Date.now();
  self.clients.matchAll({ type: 'window' }).then((cs) => {
    cs.forEach((c) => { try { c.postMessage({ xk: 'offline', reason: reason, at: lastFallback }); } catch (e) { } });
  }).catch(() => { });
}

/* 页面侧问「刚才是不是兜底过」：断网首屏时 HTML 的兜底可能早于 xk-ux.js 执行，广播会丢。
   带上 at（兜底时刻）让页面自己判断这次兜底是不是「本次导航」发生的 —— 否则 60 秒内
   重新联网正常打开的页面也会误挂一条「当前离线」。 */
self.addEventListener('message', (e) => {
  const d = e.data || {};
  if (d.xk !== 'state') return;
  if (!lastFallback || Date.now() - lastFallback > 60000) return;
  const src = e.source;
  if (src && src.postMessage) { try { src.postMessage({ xk: 'offline', reason: 'state', at: lastFallback }); } catch (err) { } }
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;          /* 接口在 demo.xiaokeqing.cn，交给浏览器 */

  if (isAsset(url)) {
    e.respondWith((async () => {
      const c = await caches.open(CACHE_ASSET);
      const hit = await c.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res && res.ok) { c.put(req, res.clone()); trim(c); }
      return res;
    })());
    return;
  }

  e.respondWith((async () => {
    const c = await caches.open(CACHE_HTML);
    const hit = await c.match(req);

    const net = fetch(req).then((res) => {
      if (res && res.ok) c.put(req, res.clone());
      return res;
    });

    /* 没有缓存可退：只能等网络（超时也没东西给，等它比给错误页强） */
    if (!hit) return net;

    let res = null;
    try {
      res = await Promise.race([net, new Promise((r) => setTimeout(() => r(null), HTML_TIMEOUT))]);
    } catch (err) {
      res = null;                                      /* 断网/DNS 失败：走下面回缓存 */
    }
    if (res) return res;

    net.catch(() => { });                              /* 慢网那一路还可能成功，别抛未处理拒绝 */
    notifyOffline('cache');
    return hit;
  })());
});

async function trim(cache) {
  const keys = await cache.keys();
  if (keys.length <= IMG_MAX) return;
  for (const k of keys.slice(0, keys.length - IMG_MAX)) await cache.delete(k);
}
