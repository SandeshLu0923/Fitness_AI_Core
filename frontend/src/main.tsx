import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Register Service Worker for PWA support
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register(new URL('./serviceWorker.ts', import.meta.url), {
      type: 'module',
    }).then((registration) => {
      console.log('[PWA] Service Worker registered:', registration);
    }).catch((error) => {
      console.warn('[PWA] Service Worker registration failed:', error);
    });
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
