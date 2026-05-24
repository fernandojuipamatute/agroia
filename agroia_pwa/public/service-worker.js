// =====================================================
// AgroIA Service Worker v2.0.0
// Estrategia network-first para HTML (siempre actualizado)
// Estrategia cache-first para assets estáticos (íconos, etc.)
// =====================================================

const CACHE_NAME = 'agroia-v2.0.0'; // Cambio de version fuerza actualizacion
const RUNTIME_CACHE = 'agroia-runtime-v2';

// Solo precacheamos assets estaticos, NO el HTML
const PRECACHE_URLS = [
  './icons/icon-192x192.png',
  './icons/icon-512x512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon.png'
];

// =====================================================
// INSTALACION
// =====================================================
self.addEventListener('install', event => {
  console.log('[ServiceWorker v2] Instalando...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker v2] Cacheando assets estaticos');
        return cache.addAll(PRECACHE_URLS);
      })
      .then(() => {
        // Forzar activacion inmediata sin esperar
        return self.skipWaiting();
      })
  );
});

// =====================================================
// ACTIVACION: limpiar caches viejos
// =====================================================
self.addEventListener('activate', event => {
  console.log('[ServiceWorker v2] Activando...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME && name !== RUNTIME_CACHE)
          .map(name => {
            console.log('[ServiceWorker v2] Eliminando cache viejo:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// =====================================================
// FETCH: estrategias diferenciadas
// =====================================================
self.addEventListener('fetch', event => {
  // Solo cachear peticiones GET
  if (event.request.method !== 'GET') return;
  
  const url = new URL(event.request.url);
  
  // NO interceptar peticiones a APIs externas
  if (url.hostname.includes('datadog') ||
      url.hostname.includes('onrender.com') && url.pathname.includes('/api/') ||
      url.hostname.includes('localhost') ||
      url.hostname.includes('cdnjs') ||
      url.hostname.includes('supabase') ||
      url.protocol === 'chrome-extension:') {
    return;
  }
  
  // ESTRATEGIA NETWORK-FIRST para HTML
  // Siempre intentar version nueva, si falla usar cache
  if (event.request.destination === 'document' || 
      event.request.url.endsWith('.html') ||
      event.request.url.endsWith('/')) {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          // Guardar copia en cache para offline
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(RUNTIME_CACHE).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return networkResponse;
        })
        .catch(() => {
          // Si falla la red, usar cache (modo offline real)
          return caches.match(event.request);
        })
    );
    return;
  }
  
  // ESTRATEGIA CACHE-FIRST para assets (iconos, manifest)
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }
        
        return fetch(event.request)
          .then(networkResponse => {
            if (!networkResponse || networkResponse.status !== 200 || networkResponse.type === 'opaque') {
              return networkResponse;
            }
            
            const responseToCache = networkResponse.clone();
            caches.open(RUNTIME_CACHE).then(cache => {
              cache.put(event.request, responseToCache);
            });
            
            return networkResponse;
          });
      })
  );
});
