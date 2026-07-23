import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendHost = env.VITE_API_HOST || '127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      // Cho phép truy cập từ ngoài VM (Windows host dùng IP VM)
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: `http://${backendHost}`,
          changeOrigin: true,
          secure: false,
        },
        '/ws': {
          target: `ws://${backendHost}`,
          ws: true,
        },
        '/health': {
          target: `http://${backendHost}`,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'charts': ['recharts'],
            'icons': ['lucide-react'],
          },
        },
      },
      chunkSizeWarningLimit: 600,
    },
  }
})
