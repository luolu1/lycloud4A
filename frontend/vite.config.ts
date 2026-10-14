import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        xfwd: true,
        // 不复用长连接：后端会回收空闲的 keep-alive 连接，若代理继续复用旧连接
        // 会触发 ECONNRESET，前端就会偶发 “Network Error”
        agent: false,
        timeout: 30000,
        proxyTimeout: 30000,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            // 代理异常时返回明确的 502，而不是直接重置连接
            const response = res as {
              headersSent?: boolean
              writeHead?: (status: number, headers: Record<string, string>) => void
              end?: (body: string) => void
            }
            if (
              response &&
              !response.headersSent &&
              typeof response.writeHead === 'function' &&
              typeof response.end === 'function'
            ) {
              response.writeHead(502, { 'Content-Type': 'application/json' })
              response.end(JSON.stringify({ detail: '网关与后端通信失败，请重试' }))
            }
            console.warn('[vite-proxy] 请求后端失败：', err.message)
          })
        },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
