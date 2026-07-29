const CACHE_NAME = 'workstation-v2';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png'
];

// 安装时缓存核心资源
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS).catch(err => {
        console.log('缓存部分资源失败:', err);
      });
    })
  );
  self.skipWaiting();
});

// 激活时清理旧缓存
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => {
      return Promise.all(
        names.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// 网络优先策略：有网用网，没网用缓存
// 但对 raw.githubusercontent.com 的数据请求永远走网络，不走缓存
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  
  const url = new URL(event.request.url);
  
  // 数据文件永远走网络，不缓存（保证实时性）
  if (url.hostname === 'raw.githubusercontent.com') {
    event.respondWith(fetch(event.request));
    return;
  }
  
  event.respondWith(
    fetch(event.request).then(response => {
      const clone = response.clone();
      caches.open(CACHE_NAME).then(cache => {
        cache.put(event.request, clone);
      });
      return response;
    }).catch(() => {
      return caches.match(event.request).then(cached => {
        return cached || caches.match('./index.html');
      });
    })
  );
});
