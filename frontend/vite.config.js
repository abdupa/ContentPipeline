import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true,
    },
    // Add this block for Ngrok's live-reloading to work
    hmr: {
      host: 'localhost',
      port: 5173,
    },
    // Add this line to allow the Ngrok hostname
    allowedHosts: ['.ngrok-free.app'],
  },
})