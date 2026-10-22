import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// /api/* 요청을 FastAPI(localhost:8000)로 넘김 → 백엔드에 CORS 설정 불필요
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
