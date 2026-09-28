import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard calls the FastAPI backend at VITE_API_URL (see .env.example).
// A dev proxy is also set up so relative /api requests work if you prefer that.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
