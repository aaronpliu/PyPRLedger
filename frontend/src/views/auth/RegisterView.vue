<template>
  <div class="placeholder-view">
    <el-result icon="info" title="Register" sub-title="Registration page - Coming soon">
      <template #extra>
        <el-button type="primary" @click="$router.push('/login')">Back to Login</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
// Registration view - placeholder
</script>

<style scoped>
.placeholder-view {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
}
</style>
