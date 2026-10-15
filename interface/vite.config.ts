import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
  build: { target: 'es2022' },
  // `npm run dev` forwards the page's /api calls to the local Python server (scripts/serve_tool.py).
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
});
