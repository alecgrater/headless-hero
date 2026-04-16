import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@remotion-src": path.resolve(__dirname, "../remotion/src"),
    },
    dedupe: ["react", "react-dom", "remotion", "@remotion/google-fonts"],
  },
  server: {
    port: 5173,
  },
})
