<script setup>
import { ref, watch, computed } from 'vue'
import { useNovelStore } from '@/stores/novelStore'
import { getChapter, convertNovel } from '@/api/backend'
import { downloadText, safeFilename } from '@/utils/download'

const store = useNovelStore()

// ========== 视图与引擎模式切换 ==========
const viewMode = ref('dashboard')

function toggleViewMode() {
  viewMode.value = viewMode.value === 'dashboard' ? 'legacy' : 'dashboard'
}

// ========== 共享状态 ==========
const chapterText = ref('')
const isFetchingText = ref(false)

// ========== 老模式 (Legacy) 状态 ==========
const legacyScript = computed(() => {
  if (store.currentScript) return store.currentScript
  return ''
})

// ========== 最新模式 (Dashboard) 全局流式状态 ==========
const sseState = ref({
  isStreaming: false,
  currentProcessingTitle: '', 
  retrievedCharacters: '',
  retrievedLocations: '',
  oldStoryProgress: '',
  rawStreamText: '',
  errorMessage: ''
})

const extractTag = (text, tag) => {
  const regex = new RegExp(`<${tag}>([\\s\\S]*?)(?:</${tag}>|$)`)
  const match = text.match(regex)
  return match ? match[1].trim() : ''
}

// 实时响应式切片引擎
const parsedStream = computed(() => {
  const text = sseState.value.rawStreamText
  return {
    script: extractTag(text, 'script'),
    storyProgress: extractTag(text, 'story_progress'),
    newCharacters: extractTag(text, 'new_characters'),
    newLocations: extractTag(text, 'new_locations')
  }
})

// ==========================================
// 【核心新增】：智能显示中枢
// 自动判断当前应该显示“正在流式生成的实时数据”还是“Pinia里的历史缓存数据”
// ==========================================
const displayData = computed(() => {
  const isStreamingCurrent = sseState.value.isStreaming && 
    sseState.value.currentProcessingTitle === store.currentChapter?.title

  if (isStreamingCurrent) {
    // 状态 A：引擎正在跑这一章，显示实时切片的流式数据
    return {
      isStreaming: true,
      script: parsedStream.value.script,
      storyProgress: parsedStream.value.storyProgress || sseState.value.oldStoryProgress,
      retrievedCharacters: sseState.value.retrievedCharacters,
      retrievedLocations: sseState.value.retrievedLocations,
      newCharacters: parsedStream.value.newCharacters,
      newLocations: parsedStream.value.newLocations
    }
  } else {
    // 状态 B：引擎没在跑这一章（或者停了），去读取 Pinia 里的全量快照缓存
    const cache = store.currentCachedData || {}
    return {
      isStreaming: false,
      script: cache.yaml || '',
      storyProgress: cache.storyProgress || '',
      retrievedCharacters: cache.retrievedCharacters || '',
      retrievedLocations: cache.retrievedLocations || '',
      newCharacters: cache.newCharacters || '',
      newLocations: cache.newLocations || ''
    }
  }
})

// 监听左侧章节树点击，加载原文
watch(
  () => store.currentChapter,
  async (newChapter) => {
    if (!newChapter) {
      chapterText.value = ''
      return
    }
    // 切换查看单章时，如果是静止状态，可以清空上一次的新模式快照
    if (!sseState.value.isStreaming) {
      sseState.value = { isStreaming: false, currentProcessingTitle: '', retrievedCharacters: '', retrievedLocations: '', oldStoryProgress: '', rawStreamText: '', errorMessage: '' }
    }
    
    isFetchingText.value = true
    try {
      const parts = await Promise.all(
        newChapter.files.map((file) => getChapter(store.folderName, file))
      )
      chapterText.value = parts.join('\n\n')
    } catch (err) {
      chapterText.value = '加载原文失败: ' + err.message
    } finally {
      isFetchingText.value = false
    }
  },
  { immediate: true }
)

// ========== 统一的生成入口 ==========
async function handleGenerate() {
  if (viewMode.value === 'legacy') {
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
      store.saveChapterScript(chapter.id, { yaml: resp.data?.yaml ?? '', diagnostics: [] })
      store.updateChapterStatus(chapter.id, 'done')
    } catch (err) {
      store.errorMessage = err.message ?? '生成失败'
      store.updateChapterStatus(chapter.id, 'error')
    } finally {
      store.isLoading = false
    }
  } else {
    // 执行新版全项目滚动 RAG 转换
    sseState.value.isStreaming = true
    sseState.value.rawStreamText = ''
    sseState.value.errorMessage = ''
    sseState.value.currentProcessingTitle = '准备中...'

    const jsonPath = `D:/SYJ/work_study/python/Novel2Script_AI/feiniuyun/data/temp_epubs/output_trimmed/metadata.json`
    const outputDir = `D:/SYJ/work_study/python/Novel2Script_AI/feiniuyun/tests_py/output_scripts`
    const sseUrl = `http://localhost:8000/api/v1/run_conversion?json_path=${encodeURIComponent(jsonPath)}&output_dir=${encodeURIComponent(outputDir)}`

    const evtSource = new EventSource(sseUrl)

    evtSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      switch (data.type) {
        case 'chapter_start':
          sseState.value.currentProcessingTitle = data.title
          sseState.value.rawStreamText = ''
          sseState.value.retrievedCharacters = ''
          sseState.value.retrievedLocations = ''
          if (store.chapters && store.chapters.length) {
            const targetChapter = store.chapters.find(c => c.title === data.title)
            if (targetChapter) {
              store.selectChapter(targetChapter.id) 
            }
          }
          break
        case 'retrieval_done':
          sseState.value.retrievedCharacters = data.retrieved_characters
          sseState.value.retrievedLocations = data.retrieved_locations
          break
        case 'node_start':
          sseState.value.oldStoryProgress = data.story_progress
          break
        case 'token':
          sseState.value.rawStreamText += data.content
          break
          
        // ==========================================
        // 【核心新增】：节点完成时，把整包四宫格数据存入 Pinia 缓存！
        // ==========================================
        case 'node_finish':
          if (store.currentChapter) {
            store.saveChapterScript(store.currentChapter.id, {
              yaml: parsedStream.value.script,
              storyProgress: parsedStream.value.storyProgress || sseState.value.oldStoryProgress,
              retrievedCharacters: sseState.value.retrievedCharacters,
              retrievedLocations: sseState.value.retrievedLocations,
              newCharacters: parsedStream.value.newCharacters,
              newLocations: parsedStream.value.newLocations
            })
            store.updateChapterStatus(store.currentChapter.id, 'done')
          }
          break
          
        case 'pipeline_complete':
          evtSource.close()
          sseState.value.isStreaming = false
          sseState.value.currentProcessingTitle = '全书转换完成！'
          break
        case 'error':
          evtSource.close()
          sseState.value.isStreaming = false
          sseState.value.errorMessage = data.message
          break
      }
    }
    evtSource.onerror = () => {
      evtSource.close()
      sseState.value.isStreaming = false
      sseState.value.errorMessage = "新版引擎通信被动断开"
    }
  }
}
</script>

<template>
  <section class="script-preview">
    <header class="script-preview__bar">
      <div class="script-preview__title">
        <span>{{ store.currentChapter ? store.currentChapter.title : '章节详情' }}</span>
        
        <span v-if="viewMode === 'dashboard' && sseState.currentProcessingTitle" class="batch-status-tag">
          🚀 引擎正在全自动处理: {{ sseState.currentProcessingTitle }}
        </span>
      </div>
      
      <div class="script-preview__controls">
        <button class="btn btn-toggle" @click="toggleViewMode">
          切换为：{{ viewMode === 'dashboard' ? '老版单章模式' : '最新项目引擎' }}
        </button>

        <button
          class="btn btn--primary"
          :disabled="isFetchingText || store.isLoading || sseState.isStreaming"
          @click="handleGenerate"
        >
          <span v-if="viewMode === 'legacy'">
            {{ store.isLoading ? '单章转换中…' : '单章生成剧本' }}
          </span>
          <span v-else>
            {{ sseState.isStreaming ? '整本批量生产中…' : '生成整本剧本' }}
          </span>
        </button>
      </div>
    </header>

    <div class="script-preview__body">
      <div class="preview-panel novel-panel">
        <div class="panel-header">小说原文</div>
        <div class="panel-content">
          <pre v-if="chapterText" class="text-content novel-text">{{ chapterText }}</pre>
          <div v-else class="empty-state">等待在左侧章节树选中章节...</div>
        </div>
      </div>

      <div v-if="viewMode === 'legacy'" class="preview-panel script-panel">
        <div class="panel-header">剧本预览 (老版单章接口)</div>
        <div class="panel-content">
          <pre v-if="legacyScript" class="text-content script-text">{{ legacyScript }}</pre>
          <div v-else class="empty-state">等待点击右上角「单章生成剧本」...</div>
        </div>
      </div>

      <div v-else class="preview-panel ai-dashboard">
        <div v-if="sseState.errorMessage" class="error-banner">
          🚨 引擎报错: {{ sseState.errorMessage }}
        </div>

        <div class="ai-card memory-card">
          <div class="ai-card__header">🧠 长期记忆 (ChromaDB 历史 RAG 召回)</div>
          <div class="ai-card__body">
            <template v-if="displayData.retrievedCharacters || displayData.retrievedLocations">
              <div class="memory-section">
                <strong>💡 历史人物设定：</strong>
                <pre class="lines-content">{{ displayData.retrievedCharacters }}</pre>
              </div>
              <div class="memory-section" style="margin-top: 0.75rem;">
                <strong>💡 历史地理场所：</strong>
                <pre class="lines-content">{{ displayData.retrievedLocations }}</pre>
              </div>
            </template>
            <div v-else-if="displayData.isStreaming" class="empty-state">等待引擎启动 RAG 数据检索...</div>
            <div v-else class="empty-state">该章节暂无历史记忆记录...</div>
          </div>
        </div>

        <div class="ai-card progress-card">
          <div class="ai-card__header">📖 短期记忆 & 故事发展简述 (500字内滚动前情提要)</div>
          <div class="ai-card__body">
            <pre v-if="displayData.storyProgress" class="highlight-text">{{ displayData.storyProgress }}</pre>
            <div v-else-if="displayData.isStreaming" class="empty-state">等待继承上一章节的剧情备忘录...</div>
            <div v-else class="empty-state">该章节暂无剧情进展数据...</div>
          </div>
        </div>

        <div class="ai-card script-card">
          <div class="ai-card__header">
            🎬 规范剧本正文 (标准格式 JSON 数组)
            <span v-if="displayData.isStreaming" class="streaming-indicator"></span>
          </div>
          <div class="ai-card__body script-body">
            <pre v-if="displayData.script" class="json-text">{{ displayData.script }}</pre>
            <div v-else-if="displayData.isStreaming" class="empty-state">正在流式接收最新章节的剧本内容...</div>
            <div v-else class="empty-state">请点击右上角「生成整本剧本」或选择已有缓存章节</div>
          </div>
        </div>

        <div class="ai-card new-memory-card">
          <div class="ai-card__header">🆕 本章节新长期记忆 (代码层提取自动打标)</div>
          <div class="ai-card__body new-memory-container">
             <div class="memory-section">
                <strong>🔍 抓取新出场/变化人物：</strong>
                <pre class="lines-content">{{ displayData.newCharacters || (displayData.isStreaming ? '分析中...' : '暂无数据') }}</pre>
              </div>
              <div class="memory-section">
                <strong>🔍 抓取新登场重要场所：</strong>
                <pre class="lines-content">{{ displayData.newLocations || (displayData.isStreaming ? '分析中...' : '暂无数据') }}</pre>
              </div>
          </div>
        </div>

      </div>
    </div>
  </section>
</template>

<style scoped>
.script-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f0f2f5;
}

.script-preview__bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1.25rem;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
}

.batch-status-tag {
  font-size: 0.8rem;
  background: #fff3e0;
  color: #e65100;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  margin-left: 12px;
  font-weight: 500;
  border: 1px solid #ffe0b2;
}

.btn-toggle {
  background: #f5f5f5;
  color: #424242;
  border: 1px solid #dcdcdc;
}
.btn-toggle:hover {
  background: #eeeeee;
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
  background: #fff;
}

.novel-panel {
  border-right: 1px solid #e0e0e0; 
}

.ai-dashboard {
  flex: 1.3; 
  background: #f0f2f5;
  padding: 1rem;
  gap: 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.error-banner {
  background: #ffebee;
  color: #c62828;
  padding: 0.75rem;
  border-radius: 6px;
  font-weight: bold;
  border: 1px solid #ffcdd2;
}

.ai-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border: 1px solid #e8e8e8;
}

.script-card {
  min-height: 420px; 
}

.ai-card__header {
  padding: 0.75rem 1rem;
  font-size: 0.88rem;
  font-weight: 600;
  color: #262626;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ai-card__body {
  padding: 1rem;
  font-size: 0.85rem;
  color: #434343;
  line-height: 1.6;
}

.script-body {
  overflow-y: auto;
  max-height: 600px;
}

.new-memory-container {
  display: flex;
  gap: 1rem;
}

.memory-section {
  flex: 1;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.lines-content {
  background: #fafafa;
  padding: 0.5rem;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
  margin-top: 0.25rem;
}

.json-text {
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: #0b5ed7;
  font-size: 0.82rem;
}

.highlight-text {
  color: #c0392b;
  font-weight: 500;
}

.empty-state {
  color: #bfbfbf;
  font-style: italic;
  font-size: 0.82rem;
}

.streaming-indicator {
  width: 9px;
  height: 9px;
  background-color: #52c41a;
  border-radius: 50%;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.panel-header {
  padding: 0.75rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 600;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}
.panel-content {
  padding: 1.25rem;
  overflow-y: auto;
}
.text-content {
  line-height: 1.8;
}
</style>