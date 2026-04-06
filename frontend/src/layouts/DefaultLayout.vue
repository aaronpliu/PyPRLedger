<template>
  <el-container class="layout-container">
    <!-- Header -->
    <el-header class="layout-header">
      <div class="header-content">
        <div class="header-left">
          <h1 class="logo">PR Ledger</h1>
          <el-menu
            mode="horizontal"
            :default-active="activeMenu"
            router
            background-color="#409eff"
            text-color="#fff"
            active-text-color="#ffd04b"
            style="border: none"
          >
            <el-menu-item index="/">Dashboard</el-menu-item>
            <el-menu-item index="/reviews">Reviews</el-menu-item>
            <el-sub-menu index="/scores">
              <template #title>Scores</template>
              <el-menu-item index="/scores">Score List</el-menu-item>
              <el-menu-item index="/scores/analytics">Analytics</el-menu-item>
            </el-sub-menu>
          </el-menu>
        </div>
        <div class="header-actions">
          <!-- Global Search -->
          <GlobalSearch />

          <!-- Notification Bell -->
          <NotificationBell />

          <!-- Language Switcher -->
          <el-dropdown @command="handleLanguageChange">
            <span class="language-switcher">
              {{ languageStore.getLanguageFlag(languageStore.currentLanguage) }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="lang in languageStore.availableLanguages"
                  :key="lang.code"
                  :command="lang.code"
                >
                  {{ lang.flag }} {{ lang.name }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <!-- User Menu -->
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-icon><User /></el-icon>
              {{ authStore.user?.username }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">{{ t('common.profile') }}</el-dropdown-item>
                <el-dropdown-item command="logout" divided>{{ t('common.logout') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-header>

    <!-- Main content -->
    <el-main class="layout-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { User, ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useLanguage } from '@/composables/useLanguage'
import NotificationBell from '@/components/common/NotificationBell.vue'
import GlobalSearch from '@/components/common/GlobalSearch.vue'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const languageStore = useLanguage()

const activeMenu = computed(() => route.path)

const handleCommand = (command: string) => {
  if (command === 'logout') {
    authStore.logout()
    ElMessage.success(t('auth.login_success'))
  } else if (command === 'profile') {
    router.push('/profile')
  }
}

const handleLanguageChange = (lang: string) => {
  languageStore.setLanguage(lang)
  ElMessage.success(`Language changed to ${languageStore.getLanguageName(lang)}`)
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-header {
  background: #409eff;
  color: white;
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.logo {
  font-size: 20px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.language-switcher {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.language-switcher:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: white;
}

.user-info:hover {
  opacity: 0.8;
}

.layout-main {
  padding: 20px;
  background: #f5f7fa;
}
</style>
