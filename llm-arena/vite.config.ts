import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  css: {
    devSourcemap: true,
  },
  server: {
    // Windows Hyper-V reserves 5149-5248 (covers Vite default 5173) → EACCES.
    // Bind IPv4 on a free port outside excluded ranges.
    // strictPort:false → if 3000 busy, try 3001, 3002...
    host: '127.0.0.1',
    port: 3000,
    strictPort: false,
  },
})

