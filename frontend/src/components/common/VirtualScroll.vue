<template>
  <div ref="containerRef" class="virtual-scroll-container" :style="{ height: `${containerHeight}px` }">
    <div class="virtual-scroll-spacer" :style="{ height: `${totalHeight}px` }">
      <div
        class="virtual-scroll-content"
        :style="{
          transform: `translateY(${offsetTop}px)`,
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
        }"
      >
        <slot
          v-for="item in visibleItems"
          :key="item[indexKey]"
          :item="item"
          :index="item.__virtualIndex"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useElementSize } from '@vueuse/core'

interface Props {
  items: any[]
  itemHeight: number
  indexKey?: string
  bufferSize?: number
}

const props = withDefaults(defineProps<Props>(), {
  indexKey: 'id',
  bufferSize: 5,
})

const containerRef = ref<HTMLElement | null>(null)
const { height: containerHeight } = useElementSize(containerRef)

const scrollTop = ref(0)
const startIndex = ref(0)
const endIndex = ref(0)

// Calculate total height
const totalHeight = computed(() => props.items.length * props.itemHeight)

// Calculate visible range
const visibleCount = computed(() => 
  Math.ceil(containerHeight.value / props.itemHeight)
)

const visibleItems = computed(() => {
  const start = Math.max(0, startIndex.value - props.bufferSize)
  const end = Math.min(props.items.length, endIndex.value + props.bufferSize)
  
  return props.items.slice(start, end).map((item, idx) => ({
    ...item,
    __virtualIndex: start + idx,
  }))
})

const offsetTop = computed(() => startIndex.value * props.itemHeight)

// Handle scroll
const handleScroll = () => {
  if (!containerRef.value) return
  
  scrollTop.value = containerRef.value.scrollTop
  startIndex.value = Math.floor(scrollTop.value / props.itemHeight)
  endIndex.value = Math.min(
    props.items.length,
    startIndex.value + visibleCount.value + 1
  )
}

onMounted(() => {
  if (containerRef.value) {
    containerRef.value.addEventListener('scroll', handleScroll)
    // Initialize visible range
    endIndex.value = Math.min(props.items.length, visibleCount.value + 1)
  }
})

onUnmounted(() => {
  if (containerRef.value) {
    containerRef.value.removeEventListener('scroll', handleScroll)
  }
})

watch(() => props.items, () => {
  // Reset scroll when items change
  if (containerRef.value) {
    containerRef.value.scrollTop = 0
  }
  startIndex.value = 0
  endIndex.value = Math.min(props.items.length, visibleCount.value + 1)
})
</script>

<style scoped>
.virtual-scroll-container {
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  width: 100%;
}

.virtual-scroll-spacer {
  position: relative;
  width: 100%;
}

.virtual-scroll-content {
  will-change: transform;
}
</style>
