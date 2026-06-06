<script setup>
import { computed } from 'vue'
import { useNovelStore } from '@/stores/novelStore'
import { convertProjectStream } from '@/api/backend'
import { highlightYaml } from '@/utils/highlightYaml'
import { downloadText, safeFilename } from '@/utils/download'

defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close'])

const store = useNovelStore()

// fetch 的中断控制器（点「停止」时 abort）
let controller = null

const percent = computed(() => {
  const { current, total } = store.streamProgress
  return total ? Math.round((current / total) * 100) : 0
})

async function start() {
  if (store.isStreaming || !store.folderName) return
  store.resetStream()
  store.isStreaming = true
  controller = new AbortController()
  try {
    await convertProjectStream(
      {
        user_id: store.userId,
        thread_id: store.threadId,
        project_path: store.folderName, // 后端在 data/temp_epubs 下按此目录名找项目
        title: store.bookInfo.title,
      },
      (event) => store.applyStreamEvent(event),
      { signal: controller.signal },
    )
  } catch (err) {
    if (err.name !== 'AbortError') store.streamError = err.message ?? '生成失败'
  } finally {
    store.isStreaming = false
    controller = null
  }
}

function stop() {
  controller?.abort()
}

function close() {
  if (store.isStreaming) return // 生成中不允许直接关，请先「停止」
  emit('close')
}

// 把已完成的各段 YAML 拼成一个文件下载（整本导出）
function downloadAll() {
  if (!store.streamUnits.length) return
  const combined = store.streamUnits
    .map((u) => `# ===== ${u.title}（unit ${u.unitIndex}）=====\n${u.plotText}`)
    .join('\n\n')
  downloadText(`${safeFilename(store.bookInfo.title)}-整本.yaml`, combined)
}
</script>

<template>
  <div v-if="open" class="stream">
    <div class="stream__backdrop" @click="close"></div>
    <aside class="stream__panel">
      <header class="stream__head">
        <h2 class="stream__title">整本流式生成</h2>
        <button class="stream__close" :disabled="store.isStreaming" title="关闭" @click="close">
          ✕
        </button>
      </header>

      <div class="stream__sub">
        《{{ store.bookInfo.title || '未载入' }}》 · 目录 {{ store.folderName || '—' }}
      </div>

      <!-- 进度条 -->
      <div class="stream__progress">
        <div class="stream__bar">
          <div class="stream__bar-fill" :style="{ width: percent + '%' }"></div>
        </div>
        <div class="stream__progress-text">
          {{ store.streamProgress.current }} / {{ store.streamProgress.total || '?' }} 段 ·
          {{ percent }}%
          <span v-if="store.isStreaming && store.streamCurrentTitle" class="stream__now">
            · 正在处理：{{ store.streamCurrentTitle }}
          </span>
        </div>
      </div>

      <!-- 操作区 -->
      <div class="stream__actions">
        <button
          v-if="!store.isStreaming"
          class="btn btn--primary"
          :disabled="!store.folderName"
          @click="start"
        >
          {{ store.streamDone ? '重新生成' : '开始生成整本' }}
        </button>
        <button v-else class="btn" @click="stop">停止</button>
        <button class="btn" :disabled="!store.streamUnits.length" @click="downloadAll">
          下载整本
        </button>
      </div>

      <p v-if="store.streamError" class="stream__error">{{ store.streamError }}</p>

      <!-- 已完成单元（可展开看该段 YAML） -->
      <div class="stream__units">
        <details v-for="u in store.streamUnits" :key="u.unitIndex" class="stream__unit">
          <summary class="stream__unit-head">
            <span class="stream__unit-title">{{ u.unitIndex }}. {{ u.title }}</span>
            <span class="stream__unit-meta">
              {{ u.sceneCount }} 场
              <span v-if="u.warningCount" class="stream__warn">⚠ {{ u.warningCount }}</span>
            </span>
          </summary>
          <pre class="stream__unit-body hl-yaml" v-html="highlightYaml(u.plotText)"></pre>
        </details>
        <div v-if="!store.streamUnits.length && !store.isStreaming" class="stream__empty">
          点击「开始生成整本」对整本小说做流式改编。
        </div>
      </div>

      <footer v-if="store.streamDone && store.streamStats" class="stream__footer">
        ✅ 完成：共 {{ store.streamStats.processed_unit_count }} 段 ·
        {{ store.streamStats.scene_count }} 场戏
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.stream {
  position: fixed;
  inset: 0;
  z-index: 50;
}
.stream__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
}
.stream__panel {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  width: min(520px, 92vw);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  background: var(--color-surface);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
}
.stream__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.stream__title {
  font-size: 1.05rem;
  font-weight: 600;
}
.stream__close {
  border: none;
  background: none;
  font-size: 1rem;
  cursor: pointer;
  color: var(--color-text-muted);
}
.stream__close:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.stream__sub {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}
.stream__bar {
  height: 8px;
  border-radius: 999px;
  background: var(--color-border);
  overflow: hidden;
}
.stream__bar-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.25s ease;
}
.stream__progress-text {
  margin-top: 0.35rem;
  font-size: 0.78rem;
  color: var(--color-text-muted);
}
.stream__now {
  color: var(--color-primary);
}
.stream__actions {
  display: flex;
  gap: 0.5rem;
}
.stream__error {
  margin: 0;
  font-size: 0.8rem;
  color: var(--color-danger);
}
.stream__units {
  flex: 1 1 auto;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.stream__unit {
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-bg);
}
.stream__unit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  font-size: 0.85rem;
}
.stream__unit-title {
  font-weight: 500;
}
.stream__unit-meta {
  flex: 0 0 auto;
  font-size: 0.75rem;
  color: var(--color-text-muted);
}
.stream__warn {
  margin-left: 0.4rem;
  color: #e8590c;
}
.stream__unit-body {
  margin: 0;
  padding: 0.75rem;
  border-top: 1px solid var(--color-border);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.6;
}
.stream__empty {
  padding: 2rem 0.5rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}
.stream__footer {
  flex: 0 0 auto;
  font-size: 0.85rem;
  color: #2f9e44;
}
</style>
