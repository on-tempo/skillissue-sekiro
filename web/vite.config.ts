import { copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const root = fileURLToPath(new URL('.', import.meta.url));

const file = (name: string) =>
  fileURLToPath(new URL(name, import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'preserve-static-share-assets',
      closeBundle() {
        for (const name of [
          'og-image.png',
          'apple-touch-icon.png',
          'moon-katana-mark.svg',
          'moon-katana.svg',
        ]) {
          copyFileSync(file(name), file(`dist/${name}`));
        }
      },
    },
  ],

  root,

  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/healthz': 'http://127.0.0.1:8000',
    },
  },

  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        main: file('index.html'),
        privacy: file('privacy.html'),
      },
    },
  },
});