import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// In development the SPA runs on :5173 and proxies the API to the backend, so
// the browser always talks to a same-origin `/api/v1` — exactly like production,
// where FastAPI serves both the SPA and the API from one container.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.LMS_API_URL ?? 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 700,
  },
})
