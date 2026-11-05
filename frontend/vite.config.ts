import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// در تولید، خروجی dist توسط Nginx ارائه می‌شود؛ Vite Dev Server محصول نیست (سند ۱۲.۳)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8011', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
