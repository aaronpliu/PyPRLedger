import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables based on mode
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  
  // API configuration - single source of truth
  const apiBaseUrl = env.VITE_API_BASE_URL || '/api/v1'
  
  // Check if using relative path (development with proxy)
  const isRelativePath = apiBaseUrl.startsWith('/')
  
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    server: {
      port: parseInt(env.VITE_DEV_PORT || '3001'),
      // Only configure proxy for development (relative paths)
      ...(isRelativePath && {
        proxy: {
          [apiBaseUrl]: {
            target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:9097',
            changeOrigin: true,
            secure: false,
          },
        },
      }),
    },
    build: {
      outDir: 'dist',
      sourcemap: mode === 'prod' ? false : true,
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: mode === 'prod',
          drop_debugger: mode === 'prod',
        },
      },
      rollupOptions: {
        output: {
          manualChunks: undefined,
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
        },
      },
      chunkSizeWarningLimit: 2000,
    },
    optimizeDeps: {
      include: ['vue', 'vue-router', 'pinia', 'axios', 'element-plus', 'dayjs'],
    },
  }
})
