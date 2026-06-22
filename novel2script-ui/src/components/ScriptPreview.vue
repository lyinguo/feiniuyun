<script setup>
import { ref, watch, computed, provide, inject } from 'vue'
import { useNovelStore } from '@/stores/novelStore'
import { useAgentStore } from '@/stores/agentStore'
import { getChapter, convertNovel } from '@/api/backend'
import { downloadText, safeFilename } from '@/utils/download'
import { useNovelStream } from '@/composables/useNovelStream'
import { useAgentStream } from '@/composables/useAgentStream'
import NovelViewer from '@/components/workbench/NovelViewer.vue'
import AiDashboard from '@/components/workbench/AiDashboard.vue'
import LegacyScriptViewer from '@/components/workbench/LegacyScriptViewer.vue'

const store = useNovelStore()
const agentStore = useAgentStore()
// const activeSourceRange = ref([])

// 1. 分别记录“悬停”和“锁定”的状态
const hoveredRange = ref([])
const lockedRange = ref([])

// 2. 智能计算：有悬停就优先显示悬停，没悬停就显示锁定的
const activeSourceRange = computed(() => {
  return hoveredRange.value.length > 0 ? hoveredRange.value : lockedRange.value
})

provide('activeSourceRange', activeSourceRange)

// 3. 提供修改“悬停”的方法
provide('setHoveredRange', (range) => {
  hoveredRange.value = range || []
})

// 4. 提供修改“锁定”的方法（带有再次点击取消锁定的开关逻辑）
provide('setLockedRange', (range) => {
  // 如果点击的是已经锁定的同一段，就取消锁定
  if (lockedRange.value[0] === range[0] && lockedRange.value[1] === range[1]) {
    lockedRange.value = []
  } else {
    lockedRange.value = range || []
  }
})

// 鼠标点击：平滑滚动到左侧对应段落
const scrollToSource = (range) => {
  if (!range || !range.length) return
  // 提取首段数字
  const startNum = parseInt(range[0].split('_').pop().replace(/\D/g, ''))
  // 找到左侧 NovelViewer 中对应的那个 <p> 标签
  const targetElement = document.getElementById(`novel-p-${startNum}`)
  
  if (targetElement) {
    targetElement.scrollIntoView({ 
      behavior: 'smooth', 
      block: 'center' // 保证滚动完之后，该段落处于屏幕正中央
    })
  }
}
// ========== 视图模式切换 ==========
const viewMode = ref('dashboard')
function toggleViewMode() {
  viewMode.value = viewMode.value === 'dashboard' ? 'legacy' : 'dashboard'
}

// ========== 共享状态（左侧原文）==========
const chapterText = ref('')
const isFetchingText = ref(false)


// ========== 新版流式引擎（通过 composable 接管）==========
// const { displayData, startStream, stopStream} = useNovelStream(store)
const { displayData, startStream: startOldStream, stopStream: stopOldStream } = useNovelStream(store)
const { startStream: startAgentStream, stopStream: stopAgentStream } = useAgentStream()
const handleStop = () => {
  if (confirm('确定要强行停止当前的剧本生成任务吗？')) {
    if (viewMode.value === 'legacy') {
      stopAgentStream() // 停掉新后端
    } else{
      stopOldStream() // 核心：切断长连接
      store.sseState.isStreaming = false // 修改底座状态，让打字机和动画停下来
      store.sseState.currentProcessingTitle = '任务已被手动停止'
      // console.log('🛑 用户手动触发了强行停止按钮！')
    }
    
  }
}
// ========== 监听章节点击加载原文 ==========
watch(
  () => store.currentChapter,
  async (newChapter) => {
    if (!newChapter) {
      chapterText.value = ''
      return
    }
    // 非流式状态可以清空上一次的 dashboard 状态（已在 store 中）
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
// ========== 统一生成入口 ==========
async function handleGenerate() {
  if (viewMode.value === 'legacy') {
    // 老模式：单章接口不变
    if (!store.folderName) {
      store.sseState.errorMessage = '请先在上方上传 EPUB 小说后再进行生成！'
      return
    }
    // 直接启动新流式后端
    startAgentStream(store.folderName)
  } else {
    store.sseState.rawStreamText = ''
    store.sseState.oldStoryProgress = ''
    store.sseState.newStoryProgress = ''
    store.sseState.retrievedCharacters = ''
    store.sseState.retrievedLocations = ''
    store.sseState.errorMessage = ''
    // 新版：全自动滚动 RAG 转换，直接交给 composable
    // const jsonPath = `D:/SYJ/work_study/python/Novel2Script_AI/feiniuyun/data/temp_epubs/output_trimmed/metadata.json`
    // const outputDir = `D:/SYJ/work_study/python/Novel2Script_AI/feiniuyun/tests_py/output_scripts`
    // startStream(jsonPath, outputDir)
    if (!store.folderName) {
      store.sseState.errorMessage = '请先在上方上传 EPUB 小说后再进行整本生成！'
      return
    }
    startOldStream(store.folderName)
  }
}
// ========== 状态指示器计算 ==========
const engineStatusInfo = computed(() => {
  const isStreaming = store.sseState.isStreaming
  const title = store.sseState.currentProcessingTitle || ''
  const isError = store.sseState.errorMessage !== ''

  if (isError) {
    return {
      type: 'error',
      icon: '🚨',
      text: `引擎异常: ${store.sseState.errorMessage}`
    }
  }

  if (isStreaming) {
    return {
      type: 'processing',
      icon: '⚡', // 改用闪电更带感
      text: `引擎运转中: ${title}`
    }
  }

  if (title.includes('完成')) {
    return {
      type: 'success',
      icon: '✅',
      text: title
    }
  }

  // 默认空闲状态
  return {
    type: 'idle',
    icon: '',
    text: ''
  }
})
</script>

<template>
  <section class="script-preview">
    <header class="script-preview__bar">
      <div class="script-preview__title">
        <span>{{ store.currentChapter ? store.currentChapter.title : '章节详情' }}</span>
        <div 
          v-if="viewMode === 'dashboard' && engineStatusInfo.type !== 'idle'" 
          class="status-indicator"
          :class="`status--${engineStatusInfo.type}`"
        >
          <span class="status-icon">{{ engineStatusInfo.icon }}</span>
          <span class="status-text">{{ engineStatusInfo.text }}</span>
          <div v-if="engineStatusInfo.type === 'processing'" class="progress-sweep"></div>
        </div>
      </div>

      <div class="script-preview__controls">
        <button class="btn btn-toggle" @click="toggleViewMode">
          切换为：{{ viewMode === 'dashboard' ? '多Token消耗复杂模式' : '更少token消耗引擎' }}
        </button>
        <button
          class="btn btn--primary"
          :disabled="isFetchingText || store.isLoading || store.sseState.isStreaming || agentStore.isStreaming"
          @click="handleGenerate"
        >
          <span v-if="viewMode === 'legacy'">
            {{ store.isLoading ? '转换中…' : '生成剧本' }}
          </span>
          <span v-else>
            {{ store.sseState.isStreaming ? '⚡ 正在全自动生成...' : '🚀 生成整本剧本' }}
          </span>
        </button>
        <button 
          v-if="store.sseState.isStreaming || agentStore.isStreaming"
          @click="handleStop" 
          class="btn btn-stop"
        >
          🛑 强行停止生成
        </button>
      </div>
    </header>

    <div class="script-preview__body">
      <div class="layout-left">
        <NovelViewer :chapterText="chapterText" />
      </div>
      

      <!-- 老版剧本预览 -->
      <div class="layout-right">
        <LegacyScriptViewer v-if="viewMode === 'legacy'" />

        <!-- 新版四宫格：笨组件 -->
        <AiDashboard
          v-else
          :displayData="displayData"
          :errorMessage="store.sseState.errorMessage"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
/* 仅保留 ScriptWorkbench 布局相关样式，panel 和 dashboard 内部样式已移入子组件 */
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
/* ==========================================
   🌟 状态指示器 (科技蓝 / 成功绿 / 警示红)
   ========================================== */
.status-indicator {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
  margin-left: 12px;
  overflow: hidden; /* 为了进度条扫光动画不超出边界 */
  transition: all 0.3s ease;
}

.status-icon {
  font-size: 0.9rem;
}

.status-text {
  z-index: 1; /* 保证文字在动画条上方 */
}

/* 🟢 成功状态：轻柔的浅绿色 */
.status--success {
  background-color: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #389e0d;
}

/* 🔴 错误状态：警示红色 */
.status--error {
  background-color: #fff1f0;
  border: 1px solid #ffa39e;
  color: #cf1322;
}

/* 🔵 处理中状态：标准的科技蓝 */
.status--processing {
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
  color: #096dd9;
}

/* ⚡ 处理中独有的底部分布式扫光进度条 */
.progress-sweep {
  position: absolute;
  bottom: 0;
  left: -100%;
  height: 2px;
  width: 100%;
  background: linear-gradient(90deg, transparent, #1890ff, transparent);
  animation: sweep 1.5s infinite linear;
}

@keyframes sweep {
  0% { left: -100%; }
  100% { left: 100%; }
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
/* 停止按钮专用制服：危险警示红 */
.btn-stop {
  background-color: #fff1f0;
  color: #cf1322;
  border-color: #ffa39e;
}

.btn-stop:hover {
  background-color: #cf1322;
  color: #fff;
  border-color: #cf1322;
}
/* 🌟 新增：左侧面板占 4 份 (40%) */
.layout-left {
  flex: 4;
  display: flex; /* 让内部的 NovelViewer 撑满高度 */
  overflow: hidden;
  border-right: 1px solid #e0e0e0; /* 加上一条灰色的分割线，视觉更清晰 */
}

/* 🌟 新增：右侧面板占 6 份 (60%) */
.layout-right {
  flex: 6;
  display: flex; /* 让内部的 Viewer 或 Dashboard 撑满高度 */
  overflow: hidden;
}
</style>