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
export default defineConfig({
  plugins: [react(), tailwindcss()],
  appType: 'spa',
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3000,
  },
})