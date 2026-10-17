// Vite config for the DharRakshak React app (Component 2).
//
// - React + Tailwind CSS v4 plugins.
// - `/api/*` requests are forwarded to the FastAPI backend on port 8000,
//   so the browser never hits CORS issues during development.
// - `fs.allow: ['..']` lets the app import ../shared/sample_data.json
//   (mock mode) from outside the frontend folder.
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
    fs: {
      allow: ['..'],
    },
  },
})
