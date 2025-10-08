// ==================== UPDATED SERVICE WORKER ====================
// Change this version number EVERY time you deploy
const CACHE_VERSION = 'v4.1.2'; // ← Increment this with each update!
const CACHE_NAME = `file-combiner-${CACHE_VERSION}`;

const urlsToCache = [
  '/',
  '/index.html',
  '/about.html',
  '/help.html',
  '/contact.html',
  '/privacy.html',
  '/style.css',
  '/script.js',
  '/logo.jpg',
  '/icon-192.png',
  '/manifest.json'
];

// Install event - cache resources IMMEDIATELY
self.addEventListener('install', event => {
  console.log(`🔧 Installing Service Worker ${CACHE_VERSION}...`);
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log(`✅ Caching files for ${CACHE_VERSION}`);
        return cache.addAll(urlsToCache);
      })
  );
  
  // Skip waiting to activate immediately
  self.skipWaiting();
});

// Activate event - DELETE ALL old caches
self.addEventListener('activate', event => {
  console.log(`🚀 Activating Service Worker ${CACHE_VERSION}...`);
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          // Delete ANY cache that doesn't match current version
          if (cacheName !== CACHE_NAME) {
            console.log(`🗑️ Deleting old cache: ${cacheName}`);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  // Take control of all pages immediately
  return self.clients.claim();
});

// Fetch event - NETWORK FIRST strategy (fixes your caching issue!)
self.addEventListener('fetch', event => {
  const requestUrl = new URL(event.request.url);
  
  // Skip API calls - always fetch from network
  if (requestUrl.hostname.includes('file-combiner.onrender.com') || 
      requestUrl.hostname.includes('googletagmanager.com') ||
      requestUrl.hostname.includes('google-analytics.com')) {
    return event.respondWith(fetch(event.request));
  }
  
  // NETWORK FIRST for HTML, CSS, JS (ensures updates work!)
  if (event.request.url.includes('.html') || 
      event.request.url.includes('.css') || 
      event.request.url.includes('.js') ||
      event.request.url.match(/\/$/) // Root path
  ) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // If network succeeds, update cache and return
          if (response && response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // If network fails, fallback to cache
          console.log('📡 Network failed, using cache for:', event.request.url);
          return caches.match(event.request);
        })
    );
  } 
  // CACHE FIRST for static assets (images, fonts, etc.)
  else {
    event.respondWith(
      caches.match(event.request)
        .then(response => {
          if (response) {
            return response;
          }
          
          const fetchRequest = event.request.clone();
          return fetch(fetchRequest).then(response => {
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseToCache);
            });
            
            return response;
          });
        })
    );
  }
});

// Listen for messages from the page
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
