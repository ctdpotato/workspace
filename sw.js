const CACHE_NAME = 'workstation-v3';
const ASSETS = ['./index.html', './manifest.json', './icon-192.png', './icon-512.png'];

// 安装时只缓存必要资源
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

// 网络优先策略，数据文件永不缓存
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  
  // 数据文件永远走网络
  if (url.hostname === 'raw.githubusercontent.com') {
    event.respondWith(fetch(event.request));
    return;
  }
  
  // 主页面永远走网络（不缓存 index.html），只缓存静态资源
  if (url.pathname.endsWith('/') || url.pathname.endsWith('/index.html')) {
    event.respondWith(fetch(event.request).catch(() => caches.match('./index.html')));
    return;
  }
  
  // 其他静态资源：网络优先
  event.respondWith(
    fetch(event.request).then(resp => {
      const clone = resp.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
      return resp;
    }).catch(() => caches.match(event.request))
  );
});
