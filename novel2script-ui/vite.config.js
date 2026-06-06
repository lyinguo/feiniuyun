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
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    // 开发环境跨域代理：前端所有以 /api 开头的请求，
    // 都会被转发到后端 FastAPI (http://127.0.0.1:8000)，
    // 浏览器侧只看到同源的 /api，从而绕过 CORS 限制。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // 已确认：后端 epub 路由挂在 /api、scripts 路由 prefix=/api/scripts、
        // health 为 /api/health —— 全部以 /api 开头，故保留前缀转发，无需 rewrite。
      },
    },
  },
})
