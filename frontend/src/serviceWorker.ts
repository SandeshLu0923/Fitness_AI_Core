/// <reference lib="webworker" />
declare const self: ServiceWorkerGlobalScope;

const CACHE_NAME = 'ai-gym-v1';
const RUNTIME_CACHE = 'ai-gym-runtime-v1';
const NETWORK_TIMEOUT = 3000; // 3 seconds

// URLs to cache on install
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/App.css',
  '/index.css',
];

// Regex patterns for runtime caching
const CACHE_PATTERNS = {
  // Cache API responses for 5 minutes
  api: /^https?:\/\/(localhost|127\.0\.0\.1):8000\/api\//,
  // Cache images indefinitely
  images: /\.(jpg|jpeg|png|gif|webp|svg)$/i,
  // Cache fonts indefinitely
  fonts: /\.(woff|woff2|ttf|otf|eot)$/i,
  // Cache styles and scripts
  assets: /\.(css|js|json)$/i,
};

// Install event - cache essential files
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Caching core assets');
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn('[ServiceWorker] Some assets failed to cache:', err);
        // Continue even if some assets fail
      });
    })
  );
  
  // Activate immediately
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activating...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== RUNTIME_CACHE) {
            console.log('[ServiceWorker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  self.clients.claim();
});

// Fetch event - network-first strategy with fallback
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests and WebSocket
  if (url.origin !== self.location.origin || request.url.includes('ws')) {
    return;
  }

  // Skip data URIs and blob requests
  if (url.protocol === 'data:' || url.protocol === 'blob:') {
    return;
  }

  // Network-first strategy
  event.respondWith(fetchWithTimeout(request, NETWORK_TIMEOUT));
});

async function fetchWithTimeout(request: Request, timeout: number): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(request, {
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Cache successful API responses
    if (response.ok && shouldCache(request.url)) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request.url, response.clone());
    }

    return response;
  } catch {
    clearTimeout(timeoutId);

    // Try cache on network failure
    if (request.method === 'GET') {
      const cached = await caches.match(request.url);
      if (cached) {
        console.log('[ServiceWorker] Serving from cache:', request.url);
        return cached;
      }
    }

    // Return offline fallback for navigation requests
    if (request.mode === 'navigate') {
      const cached = await caches.match('/index.html');
      if (cached) {
        return cached;
      }
    }

    // Return error response
    return new Response('Offline - Resource not available', {
      status: 503,
      statusText: 'Service Unavailable',
    });
  }
}

function shouldCache(url: string): boolean {
  return (
    CACHE_PATTERNS.api.test(url) ||
    CACHE_PATTERNS.images.test(url) ||
    CACHE_PATTERNS.fonts.test(url) ||
    CACHE_PATTERNS.assets.test(url)
  );
}

// Background sync for deferred updates
self.addEventListener('sync', (event: Event) => {
  const syncEvent = event as SyncEvent;
  console.log('[ServiceWorker] Background sync event:', syncEvent.tag);
  
  if (syncEvent.tag === 'sync-workouts') {
    syncEvent.waitUntil(syncWorkouts());
  }
});

interface SyncEvent extends Event {
  tag: string;
  waitUntil(promise: Promise<unknown>): void;
}

async function syncWorkouts(): Promise<void> {
  try {
    // Get pending workouts from IndexedDB or localStorage
    const pending = localStorage.getItem('pending_workouts');
    
    if (pending) {
      const workouts = JSON.parse(pending);
      
      for (const workout of workouts) {
        try {
          const response = await fetch('http://localhost:8000/api/gym-trainer/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(workout),
          });
          
          if (response.ok) {
            console.log('[ServiceWorker] Synced workout:', workout.id);
          }
        } catch (err) {
          console.error('[ServiceWorker] Failed to sync workout:', err);
          throw err; // Retry
        }
      }
      
      // Clear pending after successful sync
      localStorage.removeItem('pending_workouts');
    }
  } catch (error) {
    console.error('[ServiceWorker] Sync failed:', error);
    throw error; // Trigger retry
  }
}

// Message handling for cache control
self.addEventListener('message', (event) => {
  console.log('[ServiceWorker] Message received:', event.data);
  
  if (event.data.type === 'CLEAR_CACHE') {
    caches.delete(RUNTIME_CACHE).then(() => {
      event.ports[0]?.postMessage({ success: true });
    });
  }
  
  if (event.data.type === 'GET_CACHE_SIZE') {
    caches.open(RUNTIME_CACHE).then((cache) => {
      cache.keys().then((requests) => {
        event.ports[0]?.postMessage({ size: requests.length });
      });
    });
  }
});

// Periodic background sync (optional - requires user permission)
self.addEventListener('periodicsync', (event: Event) => {
  const syncEvent = event as SyncEvent;
  if (syncEvent.tag === 'update-performance-data') {
    syncEvent.waitUntil(updatePerformanceData());
  }
});

async function updatePerformanceData(): Promise<void> {
  try {
    const response = await fetch('/api/performance/weekly-report/current-user');
    const data = await response.json();
    
    // Store in cache for quick access
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(
      '/api/performance/weekly-report/current-user',
      new Response(JSON.stringify(data), {
        headers: { 'Content-Type': 'application/json' },
      })
    );
  } catch (error) {
    console.error('[ServiceWorker] Failed to update performance data:', error);
  }
}

export {};
