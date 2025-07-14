/**
 * Service Worker for caching and performance optimization
 * 提供离线支持和资源缓存
 */

const CACHE_NAME = 'weblearn-v1.0.0';
const STATIC_CACHE = 'weblearn-static-v1.0.0';
const DYNAMIC_CACHE = 'weblearn-dynamic-v1.0.0';

// 需要缓存的静态资源
const STATIC_ASSETS = [
    '/',
    '/static/css/style.css',
    '/static/css/style.min.css',
    '/static/js/main.js',
    '/static/js/performance.js',
    '/static/js/api-client.js',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js'
];

// 需要网络优先的资源
const NETWORK_FIRST_URLS = [
    '/api/',
    '/study',
    '/exam',
    '/review',
    '/settings'
];

// 安装事件 - 缓存静态资源
self.addEventListener('install', event => {
    console.log('Service Worker: Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Service Worker: Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('Service Worker: Static assets cached');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('Service Worker: Failed to cache static assets', error);
            })
    );
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', event => {
    console.log('Service Worker: Activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
                            console.log('Service Worker: Deleting old cache', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('Service Worker: Activated');
                return self.clients.claim();
            })
    );
});

// 拦截请求 - 实现缓存策略
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // 只处理同源请求和CDN资源
    if (url.origin !== location.origin && !isCDNResource(url)) {
        return;
    }
    
    // 根据资源类型选择缓存策略
    if (isStaticAsset(request)) {
        // 静态资源：缓存优先
        event.respondWith(cacheFirst(request));
    } else if (isAPIRequest(request)) {
        // API请求：网络优先，带缓存回退
        event.respondWith(networkFirstWithCache(request));
    } else if (isPageRequest(request)) {
        // 页面请求：网络优先
        event.respondWith(networkFirst(request));
    } else {
        // 其他资源：缓存优先
        event.respondWith(cacheFirst(request));
    }
});

// 缓存优先策略
async function cacheFirst(request) {
    try {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        const networkResponse = await fetch(request);
        
        // 缓存成功的响应
        if (networkResponse.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.error('Cache first strategy failed:', error);
        
        // 返回离线页面或默认响应
        if (request.destination === 'document') {
            return caches.match('/offline.html') || new Response('离线模式', {
                status: 503,
                statusText: 'Service Unavailable'
            });
        }
        
        throw error;
    }
}

// 网络优先策略
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        
        // 缓存成功的响应
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('Network first: Falling back to cache for', request.url);
        
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        throw error;
    }
}

// 网络优先带缓存回退策略（用于API）
async function networkFirstWithCache(request) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时
        
        const networkResponse = await fetch(request, {
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        // 只缓存GET请求的成功响应
        if (networkResponse.ok && request.method === 'GET') {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('API request failed, trying cache:', request.url);
        
        // 只对GET请求尝试缓存回退
        if (request.method === 'GET') {
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
        }
        
        // 返回错误响应
        return new Response(JSON.stringify({
            error: '网络连接失败，请检查网络设置',
            offline: true
        }), {
            status: 503,
            statusText: 'Service Unavailable',
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }
}

// 工具函数：检查是否为静态资源
function isStaticAsset(request) {
    const url = new URL(request.url);
    return url.pathname.startsWith('/static/') || 
           isCDNResource(url) ||
           /\.(css|js|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$/i.test(url.pathname);
}

// 工具函数：检查是否为API请求
function isAPIRequest(request) {
    return request.url.includes('/api/');
}

// 工具函数：检查是否为页面请求
function isPageRequest(request) {
    return request.destination === 'document';
}

// 工具函数：检查是否为CDN资源
function isCDNResource(url) {
    const cdnDomains = [
        'cdn.jsdelivr.net',
        'cdnjs.cloudflare.com',
        'fonts.googleapis.com',
        'fonts.gstatic.com'
    ];
    
    return cdnDomains.some(domain => url.hostname.includes(domain));
}

// 消息处理 - 与主线程通信
self.addEventListener('message', event => {
    const { type, payload } = event.data;
    
    switch (type) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
            
        case 'CLEAR_CACHE':
            clearAllCaches().then(() => {
                event.ports[0].postMessage({ success: true });
            }).catch(error => {
                event.ports[0].postMessage({ success: false, error: error.message });
            });
            break;
            
        case 'GET_CACHE_SIZE':
            getCacheSize().then(size => {
                event.ports[0].postMessage({ size });
            });
            break;
            
        default:
            console.log('Unknown message type:', type);
    }
});

// 清理所有缓存
async function clearAllCaches() {
    const cacheNames = await caches.keys();
    await Promise.all(
        cacheNames.map(cacheName => caches.delete(cacheName))
    );
    console.log('All caches cleared');
}

// 获取缓存大小
async function getCacheSize() {
    const cacheNames = await caches.keys();
    let totalSize = 0;
    
    for (const cacheName of cacheNames) {
        const cache = await caches.open(cacheName);
        const requests = await cache.keys();
        
        for (const request of requests) {
            const response = await cache.match(request);
            if (response) {
                const blob = await response.blob();
                totalSize += blob.size;
            }
        }
    }
    
    return totalSize;
}

// 后台同步（如果支持）
if ('sync' in self.registration) {
    self.addEventListener('sync', event => {
        if (event.tag === 'background-sync') {
            event.waitUntil(doBackgroundSync());
        }
    });
}

async function doBackgroundSync() {
    try {
        // 执行后台同步任务
        console.log('Background sync triggered');
        
        // 可以在这里同步离线时的数据
        // 例如：发送离线时保存的表单数据
        
    } catch (error) {
        console.error('Background sync failed:', error);
    }
}
