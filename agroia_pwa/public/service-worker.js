// =====================================================
// AgroIA Service Worker
// Cachea los recursos de la app para funcionamiento offline
// =====================================================

const CACHE_NAME = 'agroia-v1.0.0';
const RUNTIME_CACHE = 'agroia-runtime';

// Archivos que se cachean al instalar la PWA
const PRECACHE_URLS = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192x192.png',
  './icons/icon-512x512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon.png'
];

// =====================================================
// INSTALACION: cachear archivos esenciales
// =====================================================
self.addEventListener('install', event => {
  console.log('[ServiceWorker] Instalando...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker] Cacheando archivos esenciales');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(() => self.skipWaiting())
  );
});

// =====================================================
// ACTIVACION: limpiar caches antiguos
// =====================================================
self.addEventListener('activate', event => {
  console.log('[ServiceWorker] Activando...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME && name !== RUNTIME_CACHE)
          .map(name => {
            console.log('[ServiceWorker] Eliminando cache antiguo:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// =====================================================
// FETCH: estrategia "cache first, then network"
// Si está en cache, devuelve del cache (rápido, offline)
// Si no, va a la red y guarda copia en cache
// =====================================================
self.addEventListener('fetch', event => {
  // Solo cachear peticiones GET
  if (event.request.method !== 'GET') return;
  
  // No cachear peticiones a APIs externas (Datadog, servidor local)
  const url = new URL(event.request.url);
  if (url.hostname.includes('datadog') ||
      url.hostname.includes('localhost') ||
      url.protocol === 'chrome-extension:') {
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        // Si está en cache, devolverlo
        if (cachedResponse) {
          return cachedResponse;
        }
        
        // Si no, ir a la red
        return fetch(event.request)
          .then(networkResponse => {
            // Si la respuesta no es válida, no la cacheamos
            if (!networkResponse || networkResponse.status !== 200 || networkResponse.type === 'opaque') {
              return networkResponse;
            }
            
            // Cachear la respuesta para siguiente vez
            const responseToCache = networkResponse.clone();
            caches.open(RUNTIME_CACHE).then(cache => {
              cache.put(event.request, responseToCache);
            });
            
            return networkResponse;
          })
          .catch(() => {
            // Si falla todo, devolver página de error offline
            if (event.request.destination === 'document') {
              return caches.match('./index.html');
            }
          });
      })
  );
});
