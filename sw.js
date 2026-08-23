/* SS2 SP 실행기 — 서비스워커
   목적 두 가지: ① 홈 화면에 설치된 뒤 오프라인으로 돌게 ② 두 번째 실행부터 즉시 뜨게.
   롬은 여기서 다루지 않는다 — 롬은 IndexedDB 에만 있고 캐시에 넣지 않는다. */
const VER   = "ss2sp-v0.7";
const SHELL = [
  "./", "./index.html", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/maskable-512.png"
];
/* 에뮬 자산은 교차 출처(CDN)일 수 있다. 처음 한 번 받아쓴 뒤로는 캐시에서 준다. */
const FAR = [/(^|\.)emulatorjs\.org$/, /(^|\.)jsdelivr\.net$/];

self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const c = await caches.open(VER);
    await Promise.all(SHELL.map(u => c.add(u).catch(() => {})));   /* 한 장 실패해도 설치는 진행 */
    self.skipWaiting();
  })());
});

self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VER) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener("message", e => { if (e.data === "skipWaiting") self.skipWaiting(); });

function cacheable(url) {
  if (url.origin === self.location.origin) return true;
  return FAR.some(re => re.test(url.hostname));
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  if (req.headers.has("range")) return;              /* 부분요청은 건드리지 않는다 */
  const url = new URL(req.url);
  if (!cacheable(url)) return;

  /* 페이지 자체는 망 먼저 — 새 판이 바로 온다. 망이 없으면 캐시. */
  if (req.mode === "navigate") {
    e.respondWith((async () => {
      try {
        const r = await fetch(req);
        const c = await caches.open(VER); c.put("./index.html", r.clone()).catch(() => {});
        return r;
      } catch (_) {
        return (await caches.match("./index.html")) || (await caches.match("./")) || Response.error();
      }
    })());
    return;
  }

  /* 나머지는 캐시 먼저 — 에뮬 코어(수 MB)를 매번 다시 받지 않는다. */
  e.respondWith((async () => {
    const hit = await caches.match(req, { ignoreVary: true });
    if (hit) return hit;
    try {
      const r = await fetch(req);
      if (r && (r.ok || r.type === "opaque")) {
        const c = await caches.open(VER); c.put(req, r.clone()).catch(() => {});
      }
      return r;
    } catch (err) {
      const alt = await caches.match(req, { ignoreVary: true, ignoreSearch: true });
      if (alt) return alt;
      throw err;
    }
  })());
});
