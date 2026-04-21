<template>
  <el-container class="admin-layout">
    <!-- Sidebar -->
    <el-aside width="200px" class="admin-sidebar">
      <div class="sidebar-header">
        <h2>{{ t('menu.adminPanel') }}</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="var(--el-bg-color)"
        text-color="var(--el-text-color-regular)"
        active-text-color="var(--el-color-primary)"
      >
        <el-menu-item index="/myadmin">
          <el-icon><DataAnalysis /></el-icon>
          <span>{{ t('menu.dashboard') }}</span>
        </el-menu-item>
        <el-menu-item index="/myadmin/users">
          <el-icon><User /></el-icon>
          <span>{{ t('menu.users') }}</span>
        </el-menu-item>
        <el-menu-item index="/myadmin/roles">
          <el-icon><Lock /></el-icon>
          <span>{{ t('menu.roles') }}</span>
        </el-menu-item>
        <el-menu-item index="/myadmin/delegations">
          <el-icon><Share /></el-icon>
          <span>{{ t('menu.delegations') }}</span>
        </el-menu-item>
        <el-menu-item index="/myadmin/audit">
          <el-icon><Document /></el-icon>
          <span>{{ t('menu.auditLogs') }}</span>
        </el-menu-item>
        <el-menu-item index="/myadmin/sessions">
          <el-icon><Monitor /></el-icon>
          <span>{{ t('menu.sessions') }}</span>
        </el-menu-item>
        <el-menu-item index="/myadmin/project-registry">
          <el-icon><Folder /></el-icon>
          <span>{{ t('menu.projectRegistry') }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- Main content -->
    <el-container>
      <el-header class="admin-header">
        <div class="header-right">
          <!-- Global Search -->
          <div class="header-item">
            <GlobalSearch />
          </div>

          <!-- Notification Bell -->
          <div class="header-item">
            <NotificationBell />
          </div>

          <!-- Theme Switcher -->
          <div class="header-item">
            <ThemeSwitcher />
          </div>

          <!-- User Dropdown -->
          <div class="header-item user-dropdown-wrapper">
            <el-dropdown @command="handleCommand">
              <span class="user-info">
                {{ authStore.user?.username }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="home">{{ t('common.backToHome') }}</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>{{ t('common.logout') }}</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-header>

      <el-main class="admin-main">
        <div class="page-wrapper">
          <router-view />
          
          <!-- Page-level version info (shown at bottom of each page) -->
          <div class="page-version-info">
            <span class="copyright">{{ COPYRIGHT }}</span>
            <span class="version-separator">|</span>
            <span class="version-info">
              UI v{{ UI_VERSION }} | API v{{ apiVersion }}
            </span>
          </div>
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock, Share, Document, Monitor, ArrowDown, DataAnalysis, Folder } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import NotificationBell from '@/components/common/NotificationBell.vue'
import GlobalSearch from '@/components/common/GlobalSearch.vue'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'
import { UI_VERSION, COPYRIGHT, fetchApiVersion } from '@/config/versions'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

// API version state
const apiVersion = ref<string>('loading...')

// Fetch API version on mount
onMounted(async () => {
  apiVersion.value = await fetchApiVersion()
})

const activeMenu = computed(() => route.path)

const handleCommand = (command: string) => {
  if (command === 'logout') {
    authStore.logout()
    ElMessage.success('Logged out successfully')
  } else if (command === 'home') {
    router.push('/')
  }
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}

.admin-sidebar {
  background: var(--el-bg-color);
  overflow-y: auto;
}

.sidebar-header {
  padding: 20px;
  color: var(--el-text-color-primary);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.sidebar-header h2 {
  margin: 0;
  font-size: 18px;
}

.admin-header {
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 0 24px;
  height: 60px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-item {
  display: flex;
  align-items: center;
}

.user-dropdown-wrapper {
  margin-left: 8px;
}

.user-info {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-primary);
  padding: 8px 12px;
  border-radius: 4px;
  transition: background-color 0.2s;
  font-weight: 500;
}

.user-info:hover {
  background-color: var(--el-fill-color-light);
}

.admin-main {
  background: var(--el-bg-color-page);
  padding: 20px;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 60px); /* Subtract header height */
}

.page-wrapper {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.page-version-info {
  margin-top: auto;
  padding-top: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  opacity: 0.7;
}

.copyright {
  font-weight: 500;
}

.version-separator {
  margin: 0 8px;
  opacity: 0.5;
}

.version-info {
  font-family: monospace;
}
</style>
