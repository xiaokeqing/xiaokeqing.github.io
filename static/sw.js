/* XK-LAB 的离线壳（2026-11-07 站主「把项目全做完」）
   策略：
   - HTML / JSON / 接口：network-first（永远先要新的，断网才回缓存）—— 站点靠数据新鲜度，不能给用户看旧数字
   - 指纹化静态资源（带 hash 的 /js/xk-*.min.<hash>.js、/css/*、/kurisu/**、/images/**）：cache-first
   - 只缓存同源 GET；跨域（demo.xiaokeqing.cn 接口）不拦截、不进缓存
   注意：这个 SW 不做预缓存清单（站点 240MB 级），只在访问时顺带存，避免装一次就吞配额。 */
const VER = 'xk-v1';
const IMG_MAX = 60;           /* 最多留 60 张图片，超过按 LRU 丢 */
const CACHE_HTML = VER + '-html';
const CACHE_ASSET = VER + '-asset';

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
    try {
      const res = await fetch(req);
      if (res && res.ok) c.put(req, res.clone());
      return res;
    } catch (err) {
      const hit = await c.match(req);
      if (hit) return hit;
      throw err;
    }
  })());
});

async function trim(cache) {
  const keys = await cache.keys();
  if (keys.length <= IMG_MAX) return;
  for (const k of keys.slice(0, keys.length - IMG_MAX)) await cache.delete(k);
}
