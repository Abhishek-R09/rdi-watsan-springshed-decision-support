import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Default base '/': the Python server serves dist/ at http://127.0.0.1:8765/
  build: { target: 'es2022', chunkSizeWarningLimit: 900 },
  // `npm run dev` forwards the page's /api calls to the local Python tool server.
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
  preview: { proxy: { '/api': 'http://127.0.0.1:8765' } },
});
