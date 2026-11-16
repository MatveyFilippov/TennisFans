import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }
  return {
    plugins: [
      react(),
      {
        name: 'tennisfans-runtime',
        configureServer(server) {
          server.middlewares.use('/config.json', (_request, response) => {
            response.setHeader('Content-Type', 'application/json')
            response.setHeader('Cache-Control', 'no-store')
            response.end(JSON.stringify({ apiBaseUrl: env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000' }))
          })
        },
      },
    ],
    server: { host: env.FRONTEND_HOST ?? '127.0.0.1', port: Number(env.FRONTEND_PORT ?? 5173), strictPort: true },
  }
})
