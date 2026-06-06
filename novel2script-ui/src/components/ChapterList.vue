<script setup>
import { useNovelStore } from '@/stores/novelStore'

const store = useNovelStore()

const statusText = {
  idle: '待生成',
  generating: '生成中',
  done: '已完成',
  error: '失败',
}
</script>

<template>
  <aside class="chapter-list">
    <header class="chapter-list__header">章节列表</header>

    <ul v-if="store.hasNovel" class="chapter-list__items">
      <li
        v-for="chapter in store.chapters"
        :key="chapter.id"
        class="chapter-item"
        :class="{ 'chapter-item--active': chapter.id === store.currentChapterId }"
        @click="store.selectChapter(chapter.id)"
      >
        <span class="chapter-item__title">{{ chapter.title }}</span>
        <span class="chapter-item__meta">
          <span>{{ (chapter.charCount ?? 0).toLocaleString() }} 字</span>
          <span class="chapter-item__tags">
            <span v-if="chapter.isChunked" class="chapter-item__chunk">分块</span>
            <span class="chapter-item__status" :data-status="chapter.status">
              {{ statusText[chapter.status] ?? '待生成' }}
            </span>
          </span>
        </span>
      </li>
    </ul>

    <div v-else class="chapter-list__empty">上传小说后在此显示章节</div>
  </aside>
</template>

<style scoped>
.chapter-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-surface);
}
.chapter-list__header {
  flex: 0 0 auto;
  padding: 0.85rem 1rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-border);
}
.chapter-list__items {
  flex: 1 1 auto;
  overflow-y: auto;
}
.chapter-item {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.7rem 1rem;
  cursor: pointer;
  border-bottom: 1px solid var(--color-border);
  transition: background 0.15s;
}
.chapter-item:hover {
  background: var(--color-bg);
}
.chapter-item--active {
  background: #eef2ff;
  box-shadow: inset 3px 0 0 var(--color-primary);
}
.chapter-item__title {
  font-size: 0.9rem;
}
.chapter-item__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}
.chapter-item__tags {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.chapter-item__chunk {
  padding: 0 0.3rem;
  font-size: 0.7rem;
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: 4px;
}
.chapter-item__status[data-status='done'] {
  color: #2f9e44;
}
.chapter-item__status[data-status='generating'] {
  color: var(--color-primary);
}
.chapter-item__status[data-status='error'] {
  color: var(--color-danger);
}
.chapter-list__empty {
  padding: 2rem 1rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}
</style>
