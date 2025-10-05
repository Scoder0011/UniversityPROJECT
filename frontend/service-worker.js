// Change this version number EVERY time you deploy
const CACHE_NAME = 'file-combiner-v3.7.6'; // ← Change this!
const urlsToCache = [
  '/',
  '/index.html',
  '/about.html',
  '/help.html',
  '/contact.html',
  '/privacy.html',
  '/style.css',
  '/script.js',
  '/logo.jpg'
];
// Install event - cache resources
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});
// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});
// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  // Skip API calls - always fetch from network
  if (event.request.url.includes('file-combiner.onrender.com')) {
    return event.respondWith(fetch(event.request));
  }
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        // Clone the request
        const fetchRequest = event.request.clone();
        return fetch(fetchRequest).then(response => {
          // Check if valid response
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          // Clone the response
          const responseToCache = response.clone();
          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
          return response;
        });
      })
  );
