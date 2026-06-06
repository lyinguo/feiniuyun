<script setup>
import { ref, watch, computed } from 'vue'
import { useNovelStore } from '@/stores/novelStore'
import { getChapter, convertNovel } from '@/api/backend'
import { highlightYaml } from '@/utils/highlightYaml'
import { downloadText, safeFilename } from '@/utils/download'

const store = useNovelStore()

// ========== 新增：剧本展示与流式状态的兼容逻辑 ==========

// 1. 判断流式生成是否刚好正在处理当前选中的章节
const isStreamGeneratingThis = computed(() => {
  return store.isStreaming && store.streamCurrentTitle === store.currentChapter?.title
})

// 2. 动态计算当前应该展示的剧本
const displayScript = computed(() => {
  // 优先展示单章手动生成的剧本（从缓存中读）
  if (store.currentScript) return store.currentScript
  
  // 如果没有单章缓存，去流式生成的列表里找找看有没有这章
  if (store.currentChapter && store.streamUnits?.length) {
    const unit = store.streamUnits.find(u => u.title === store.currentChapter.title)
    if (unit) return unit.plotText // 找到的话，返回流式生成的文本
  }
  
  return ''
})

// 3. 高亮逻辑现在绑定到 displayScript 上
const highlightedScript = computed(() => highlightYaml(displayScript.value))

// =======================================================

const chapterText = ref('')
const isFetchingText = ref(false)

// 监听当前选中章节的变化，自动获取小说原文
watch(
  () => store.currentChapter,
  async (newChapter) => {
    if (!newChapter) {
      chapterText.value = ''
      return
    }
    
    isFetchingText.value = true
    try {
      const parts = await Promise.all(
        newChapter.files.map((file) => getChapter(store.folderName, file))
      )
      chapterText.value = parts.join('\n\n')
    } catch (err) {
      chapterText.value = '加载小说原文失败: ' + (err.message || '未知错误')
    } finally {
      isFetchingText.value = false
    }
  },
  { immediate: true }
)

async function handleGenerate() {
  const chapter = store.currentChapter
  if (!chapter || !chapterText.value) return

  store.isLoading = true
  store.errorMessage = ''
  store.updateChapterStatus(chapter.id, 'generating')
  
  try {
    const resp = await convertNovel({
      user_id: store.userId,
      thread_id: store.threadId,
      novel_text: chapterText.value,
      title: chapter.title,
    })

    store.saveChapterScript(chapter.id, {
      yaml: resp.data?.yaml ?? '',
      diagnostics: resp.data?.diagnostics ?? [],
    })
    store.updateChapterStatus(chapter.id, 'done')
  } catch (err) {
    store.errorMessage = err.message ?? '生成失败'
    store.updateChapterStatus(chapter.id, 'error')
  } finally {
    store.isLoading = false
  }
}

// 复制和下载现在也使用 displayScript.value
async function handleCopy() {
  if (!displayScript.value) return
  await navigator.clipboard?.writeText(displayScript.value)
}

function handleDownload() {
  if (!displayScript.value) return
  const name = safeFilename(`${store.bookInfo.title}-${store.currentChapter?.title}`)
  downloadText(`${name}.yaml`, displayScript.value)
}
</script>

<template>
  <section class="script-preview">
    <header class="script-preview__bar">
      <div class="script-preview__title">
        {{ store.currentChapter ? store.currentChapter.title : '章节详情' }}
      </div>
      <div class="script-preview__controls">
        <button class="btn" :disabled="!displayScript" @click="handleCopy">复制</button>
        <button class="btn" :disabled="!displayScript" @click="handleDownload">下载</button>
        <button
          class="btn btn--primary"
          :disabled="!store.currentChapter || store.isLoading || isFetchingText || isStreamGeneratingThis"
          @click="handleGenerate"
        >
          {{ store.isLoading ? '生成中…' : '单章生成剧本' }}
        </button>
      </div>
    </header>

    <div class="script-preview__body">
      <div class="preview-panel novel-panel">
        <div class="panel-header">小说原文</div>
        <div class="panel-content">
          <div v-if="!store.currentChapter" class="script-preview__hint">请先在左侧选择一个章节</div>
          <div v-else-if="isFetchingText" class="script-preview__hint">正在加载原文...</div>
          <pre v-else class="text-content novel-text">{{ chapterText }}</pre>
        </div>
      </div>

      <div class="preview-panel script-panel">
        <div class="panel-header">剧本预览</div>
        <div class="panel-content">
          <pre
            v-if="displayScript"
            class="text-content script-text hl-yaml"
            v-html="highlightedScript"
          ></pre>
          
          <div v-else-if="isStreamGeneratingThis" class="script-preview__hint stream-loading">
            <span class="loading-dots">正在流式生成该章节剧本中，请稍候...</span>
          </div>
          
          <div v-else-if="store.currentChapter" class="script-preview__hint">
            点击右上角「单章生成剧本」开始转换，或使用右上角「整本流式生成」
          </div>
          
          <div v-else class="script-preview__hint">请先在左侧选择一个章节</div>
        </div>
      </div>
    </div>

    <footer v-if="store.diagnostics.length" class="script-preview__diagnostics">
      <div class="script-preview__diag-title">连续性提示（{{ store.diagnostics.length }}）</div>
      <ul>
        <li v-for="(item, i) in store.diagnostics" :key="i">{{ item }}</li>
      </ul>
    </footer>
  </section>
</template>

<style scoped>
.script-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg);
}

.script-preview__bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 1.25rem;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.script-preview__title {
  font-weight: 600;
  font-size: 0.95rem;
}

.script-preview__controls {
  display: flex;
  gap: 0.5rem;
}

.script-preview__body {
  flex: 1 1 auto;
  display: flex;
  overflow: hidden; 
}

.preview-panel {
  flex: 1; 
  display: flex;
  flex-direction: column;
  min-width: 0; 
}

.novel-panel {
  border-right: 1px solid var(--color-border); 
}

.panel-header {
  flex: 0 0 auto;
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text-muted);
  background: #f8f9fa;
  border-bottom: 1px solid var(--color-border);
}

.panel-content {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 1.25rem;
}

.text-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}

.novel-text {
  font-family: var(--font-sans);
  font-size: 0.9rem;
}

.script-text {
  font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 0.85rem;
}

.script-preview__hint {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-text-muted);
  font-size: 0.9rem;
  text-align: center;
  padding: 0 2rem;
}

/* 简单的流式加载动画样式提示 */
.stream-loading {
  color: var(--color-primary);
  font-weight: 500;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.script-preview__diagnostics {
  flex: 0 0 auto;
  max-height: 30%;
  overflow-y: auto;
  padding: 0.75rem 1.25rem;
  background: #fff8e1;
  border-top: 1px solid var(--color-border);
  font-size: 0.8rem;
}

.script-preview__diag-title {
  margin-bottom: 0.35rem;
  font-weight: 600;
  color: #b8860b;
}

.script-preview__diagnostics ul {
  padding-left: 1.1rem;
  list-style: disc;
}

.script-preview__diagnostics li {
  margin: 0.15rem 0;
}
</style>