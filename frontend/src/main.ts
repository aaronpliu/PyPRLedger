import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useAuthStore } from './stores/auth'
// Import theme composable to initialize global theme management
import './composables/useTheme'

const app = createApp(App)

// Pinia
const pinia = createPinia()
app.use(pinia)

// Router
app.use(router)

// i18n
app.use(i18n)

// Element Plus
app.use(ElementPlus)

// Register Element Plus icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// Initialize auth
const authStore = useAuthStore()
authStore.initAuth().finally(() => {
  // The auth call that gates the first paint is exactly the wait nobody was told
  // about: the boot element in index.html stands in for the app until it mounts.
  document.getElementById('boot-loading')?.remove()
  app.mount('#app')
})
