<script setup>
import { ref } from 'vue'
import { useNovelStore } from '@/stores/novelStore'
import NovelUploader from '@/components/NovelUploader.vue'
import ChapterList from '@/components/ChapterList.vue'
import ScriptPreview from '@/components/ScriptPreview.vue'
import ProjectStream from '@/components/ProjectStream.vue'

const store = useNovelStore()
const streamOpen = ref(false)
</script>

<template>
  <div class="workbench">
    <header class="workbench__header">
      <h1 class="workbench__brand">小说转剧本工作台</h1>
      <NovelUploader />
      <button
        class="btn btn--primary workbench__whole"
        :disabled="!store.hasNovel"
        @click="streamOpen = true"
      >
        生成整本（流式）
      </button>
    </header>

    <main class="workbench__main">
      <ChapterList class="workbench__sidebar" />
      <ScriptPreview class="workbench__content" />
    </main>

    <ProjectStream :open="streamOpen" @close="streamOpen = false" />
  </div>
</template>

<style scoped>
.workbench {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.workbench__header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  min-height: 64px;
  padding: 0 1.5rem;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.workbench__brand {
  font-size: 1.1rem;
  font-weight: 600;
  white-space: nowrap;
}
.workbench__whole {
  margin-left: auto;
  white-space: nowrap;
}
.workbench__main {
  flex: 1 1 auto;
  display: grid;
  grid-template-columns: 280px 1fr;
  min-height: 0; /* 允许内部子项滚动而不撑破布局 */
}
.workbench__sidebar {
  border-right: 1px solid var(--color-border);
  min-height: 0;
}
.workbench__content {
  min-height: 0;
}
</style>
