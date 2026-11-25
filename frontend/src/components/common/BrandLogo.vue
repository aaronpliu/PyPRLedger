<template>
  <span
    :class="['brand-logo', { 'brand-logo-chip': chip }]"
    :style="sizeStyle"
  >
    <img :src="src" :alt="alt" draggable="false" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * The system logo, from the one source image:
 *  - `mark`       the brackets-and-graph icon alone, for chips and the header
 *  - `full`       icon + wordmark in navy, for light surfaces
 *  - `full-light` the same lockup with white lettering, for the dark brand panel
 *
 * All three are transparent PNGs, so they sit on any surface without a white
 * square around them. The `chip` variant gives the navy mark its own white
 * tile, which is what keeps it legible on coloured backgrounds.
 */
const props = withDefaults(
  defineProps<{
    variant?: 'mark' | 'full' | 'full-light'
    height?: number
    chip?: boolean
    alt?: string
  }>(),
  { variant: 'mark', height: undefined, chip: false, alt: 'PR Ledger' },
)

// When no height is passed, the surrounding CSS owns the size (a media query
// can then shrink a logo at a breakpoint without fighting an inline style)
const sizeStyle = computed(() =>
  props.height == null ? undefined : { '--brand-logo-height': `${props.height}px` },
)

const src = computed(
  () =>
    ({
      mark: '/brand/pr-ledger-mark.png',
      full: '/brand/pr-ledger-logo.png',
      'full-light': '/brand/pr-ledger-logo-light.png',
    })[props.variant],
)
</script>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  height: var(--brand-logo-height, 40px);
}

.brand-logo img {
  display: block;
  height: 100%;
  width: auto;
  max-width: 100%;
  object-fit: contain;
  user-select: none;
}

.brand-logo-chip {
  box-sizing: border-box;
  width: var(--brand-logo-height, 40px);
  padding: 4px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.12);
}

.brand-logo-chip img {
  width: 100%;
}
</style>
