/**
 * Sonora HVAC — Frontend Config
 * Auto-detects environment and sets API base URL.
 *
 * - Production (Netlify): uses relative /api/ paths — Netlify proxies to Railway
 * - Local dev: uses localhost:5000 directly
 *
 * To point at a specific Railway URL, set window.SONORA_API_URL before loading this script.
 */

(function () {
  const isLocal =
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1';

  // Allow manual override
  const override = window.SONORA_API_URL;

  window.SONORA_CONFIG = {
    // Base API URL — all fetch calls use this
    API_BASE: override || (isLocal ? 'http://localhost:5000' : ''),

    // Full endpoint helpers
    api(path) {
      return `${this.API_BASE}/api/${path.replace(/^\//, '')}`;
    },

    // Business display name (can be overridden per deployment)
    BUSINESS_NAME: window.SONORA_BUSINESS_NAME || 'Desert Air HVAC',
  };
})();
