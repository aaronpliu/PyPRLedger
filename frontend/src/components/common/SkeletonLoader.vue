<template>
  <div class="skeleton-loader">
    <el-skeleton :rows="rows" :animated="animated">
      <template #template>
        <el-skeleton-item variant="image" style="width: 100%; height: 200px" />
        <div style="padding: 14px">
          <el-skeleton-item variant="h3" style="width: 50%" />
          <el-skeleton-item variant="text" style="width: 70%; margin-top: 10px" />
          <el-skeleton-item variant="text" style="width: 50%; margin-top: 10px" />
          <div style="display: flex; gap: 10px; margin-top: 16px">
            <el-skeleton-item variant="button" style="width: 100px; height: 36px" />
            <el-skeleton-item variant="button" style="width: 100px; height: 36px" />
          </div>
        </div>
      </template>
    </el-skeleton>
  </div>
</template>

<script setup lang="ts">
interface Props {
  rows?: number
  animated?: boolean
}

withDefaults(defineProps<Props>(), {
  rows: 4,
  animated: true,
})
</script>

<style scoped>
.skeleton-loader {
  padding: 20px;
}
</style>
