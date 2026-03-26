import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/graph': { target: 'http://localhost:8000', changeOrigin: true },
      // SSE requires changeOrigin + no response buffering
      '/stream': { target: 'http://localhost:8000', changeOrigin: true },
      '/generate': { target: 'http://localhost:8000', changeOrigin: true },
      '/portfolio': { target: 'http://localhost:8000', changeOrigin: true },
      '/session': { target: 'http://localhost:8000', changeOrigin: true },
      '/consent': { target: 'http://localhost:8000', changeOrigin: true },
      '/upload': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
