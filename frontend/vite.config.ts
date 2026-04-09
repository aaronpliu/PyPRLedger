import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables based on mode
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  
  // Get API domain from environment or use default
  const apiDomain = env.VITE_API_DOMAIN || 'http://127.0.0.1:9097'
  const apiBasePath = env.VITE_API_BASE_PATH || '/api/v1'
  
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    server: {
      port: parseInt(env.VITE_DEV_PORT || '3001'),
      proxy: {
        [apiBasePath]: {
          target: apiDomain,
          changeOrigin: true,
          rewrite: (path) => path.replace(new RegExp(`^${apiBasePath}`), apiBasePath),
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: mode === 'prod' ? false : true, // Disable sourcemap in production for security
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: mode === 'prod', // Remove console.log in production
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
      // Chunk size warning limit
      chunkSizeWarningLimit: 2000,
    },
    // Optimize dependencies
    optimizeDeps: {
      include: ['vue', 'vue-router', 'pinia', 'axios', 'element-plus', 'dayjs'],
    },
  }
})
