<template>
  <el-dropdown @command="handleLanguageChange" trigger="click">
    <span class="language-mark" :title="currentLanguageName" :aria-label="currentLanguageName">
      <span
        v-for="glyph in offeredGlyphs"
        :key="glyph"
        class="language-mark__glyph"
        :class="{ 'is-current': glyph === currentGlyph }"
      >{{ glyph }}</span>
    </span>
    <template #dropdown>
      <el-dropdown-menu role="menu" aria-label="Language options">
        <el-dropdown-item
          v-for="lang in languageStore.availableLanguages"
          :key="lang.code"
          :command="lang.code"
          role="menuitem"
        >
          {{ languageStore.glyphForScript(lang.script) }} {{ lang.name }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'

const languageStore = useLanguage()

/**
 * Every script on offer, in a fixed order so the control does not shift as the
 * language changes. The one in effect is the one in full colour, which is what
 * makes a two-glyph control readable as "the language you are reading".
 */
const offeredGlyphs = computed(() => [
  ...new Set(
    languageStore.availableLanguages.map((lang) => languageStore.glyphForScript(lang.script)),
  ),
])

const currentGlyph = computed(() => languageStore.glyphForScript(languageStore.currentScript.value))

const currentLanguageName = computed(() =>
  languageStore.getLanguageName(languageStore.currentLanguage.value),
)

const handleLanguageChange = (lang: string) => {
  languageStore.setLanguage(lang)
  ElMessage.success(`Language changed to ${languageStore.getLanguageName(lang)}`)
}
</script>

<style scoped>
/* The two glyphs overlap into a layered monogram: "A" sits behind and
   slightly up-left, "文" in front and down-right, so the mark stays one
   compact glyph-sized icon with visible depth */
.language-mark {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  user-select: none;
}

.language-mark {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  user-select: none;
}

/* both glyphs in bold theme text colour; the inactive one just steps back
   through opacity, keeping the layered look legible in black */
.language-mark__glyph {
  color: var(--el-text-color-primary);
  font-weight: 700;
  transition: opacity 0.15s ease;
  opacity: 0.4;
}

.language-mark__glyph:nth-child(1) {
  transform: translateX(-0.3em);
}

.language-mark__glyph:nth-child(2) {
  /* pull the second glyph up into the first: the overlap is the depth, and
     the DOM order already paints it in front */
  margin-top: -0.55em;
  transform: translateX(0.3em);
  position: relative;
  z-index: 1;
}

.language-mark__glyph.is-current {
  opacity: 1;
}
</style>
