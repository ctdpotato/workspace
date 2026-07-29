const CACHE_NAME = 'workstation-v5';
const ASSETS = ['./manifest.json', './icon-192.png', './icon-512.png'];

// 安装时只缓存静态资源，不缓存 index.html 和数据文件
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS).catch(() => {}))
  );
  self.skipWaiting();
});

// 激活时清理所有旧缓存
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => Promise.all(
      names.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
    )).then(() => self.clients.matchAll()).then(clients => {
      clients.forEach(c => c.navigate(c.url));
    })
  );
});

// 网络优先策略
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  const path = url.pathname;
  
  // 数据文件永远走网络，绝不缓存
  if (path.endsWith('.json') || path.includes('/sync/')) {
    event.respondWith(fetch(event.request));
    return;
  }
  
  // raw.githubusercontent.com 永远走网络
  if (url.hostname === 'raw.githubusercontent.com') {
    event.respondWith(fetch(event.request));
    return;
  }
  
  // 主页面永远走网络（不缓存 index.html）
  if (path.endsWith('/') || path.endsWith('/index.html')) {
    event.respondWith(fetch(event.request).catch(() => new Response('Offline', {status: 503})));
    return;
  }
  
  // 其他静态资源（PNG等）：网络优先
  event.respondWith(
    fetch(event.request).then(resp => {
      const clone = resp.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
      return resp;
    }).catch(() => caches.match(event.request))
  );
});
