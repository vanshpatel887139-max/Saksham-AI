import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

/**
 * Vite config for SakshamAI.
 *
 * - appType: 'spa' (default) gives us proper history-API fallback, so direct
 *   navigation/refresh on routes like /dashboard serves index.html.
 * - Optionally proxy /api to the FastAPI backend. If you run the backend on
 *   a different port, change the target below or set VITE_API_PROXY_TARGET.
 */
/**
 * Security headers for the static app.
 *
 * `vite dev` and `vite preview` are the only servers in this repo that actually
 * hand the SPA to a browser, and neither sets security headers by default — the
 * headers set by the FastAPI backend do not apply here, because the bundle is
 * served by a different process. In production something else serves these
 * files; `deploy/nginx.conf.example` carries the same set, and the CSP there is
 * the one that matters, because it is what stops an injected script from
 * running in a page that holds an authenticated session.
 *
 * The dev CSP is looser than production on purpose: Vite's HMR client and its
 * React refresh preamble both use inline scripts, so a production-grade policy
 * breaks the dev server. The API's own CSP is strict either way.
 */
const CSP_DEV = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self' ws: http://localhost:* http://127.0.0.1:*",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "object-src 'none'",
].join('; ')

const HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Permitted-Cross-Domain-Policies': 'none',
  'Cross-Origin-Opener-Policy': 'same-origin',
  // HSTS is omitted here on purpose: these are plain-HTTP localhost servers,
  // and a browser that has cached the header refuses to fall back to http for
  // a year, which breaks local development in a way that is tedious to undo.
  // The production example config in deploy/ sets it.
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  appType: 'spa',
  server: {
    port: 3000,
    headers: { ...HEADERS, 'Content-Security-Policy': CSP_DEV },
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3000,
    headers: { ...HEADERS, 'Content-Security-Policy': CSP_DEV },
    // Same /api proxy as `server`, and it is what makes a local production
    // build testable. src/services/api.ts defaults a production build to
    // same-origin requests, so `npm run build && npm run preview` exercises
    // exactly the shape Vercel serves — without this, every preview request
    // would hit the preview server's own /api, find nothing, and fall back to
    // mock data, which is a false pass.
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
