<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useAgentStore } from '@/stores/agentStore'
import { useNovelStore } from '@/stores/novelStore'

const agentStore = useAgentStore() 
const novelStore = useNovelStore()
const writerScrollContainer = ref(null)
const isUserScrollingUp = ref(false)

// 🌟 2. 滚动事件监听器：智能判断用户意图
const handleScroll = (e) => {
  const el = e.target
  // 计算距离底部的距离 (scrollHeight = 内容总高度, scrollTop = 卷去的高度, clientHeight = 视口高度)
  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  
  // 如果距离底部超过 50px，说明用户手动往上滑了，开启锁定；如果滚回到底部，解除锁定
  isUserScrollingUp.value = distanceToBottom > 50
}
const writerData = computed(() => agentStore.currentAgentStreams['screenwriter'] || { status: 'idle', reasoning: '', content: '' })

/**
 * 🚀 流式 JSON 实时修补算法 (完全复用前置节点的黑科技)
 * 能够瞬间修复剧本嵌套深层结构（scenes -> dialogue）的残缺 JSON
 */
function parseIncompleteJson(jsonString) {
  let str = jsonString.trim()
  if (!str) return null

  try {
    return JSON.parse(str)
  } catch (e) {
    const quoteCount = (str.match(/(?<!\\)"/g) || []).length
    if (quoteCount % 2 !== 0) str += '"'
    str = str.replace(/[,:]\s*$/, '')

    let stack = []
    let inString = false
    let escapeNext = false

    for (let i = 0; i < str.length; i++) {
      let char = str[i]
      if (escapeNext) { escapeNext = false; continue }
      if (char === '\\') { escapeNext = true; continue }
      if (char === '"') { inString = !inString; continue }

      if (!inString) {
        if (char === '{') stack.push('}')
        else if (char === '[') stack.push(']')
        else if (char === '}' || char === ']') stack.pop()
      }
    }

    while (stack.length > 0) str += stack.pop()

    try { return JSON.parse(str) } 
    catch (err) { return null }
  }
}
const downloadScript = () => {
  if (!writerData.value.content) return
  
  // 创建文件内容 Blob
  const blob = new Blob([writerData.value.content], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  
  // 动态获取文件名，如果没有标题就默认叫 script_output
  const fileName = parsedScript.value?.chapter_title || 'script_output'
  
  // 创建隐藏的 a 标签触发下载
  const a = document.createElement('a')
  a.href = url
  a.download = `${fileName}.json` 
  
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url) // 释放内存
}
// 实时驱动的剧本结构化数据
const parsedScript = ref(null)

watch(
  () => writerData.value.content,
  (newContent) => {
    if (!newContent) {
      parsedScript.value = null
      return
    }
    const result = parseIncompleteJson(newContent)
    // 只有成功修复出结构时，才更新界面；若是 null 损坏帧，则保留上一帧界面不动
    if (result) {
      parsedScript.value = result
    }
  },
  { immediate: true }
)

// 自动滚动到底部
watch(
  // 🔥 这里已经修复为 writerData，不再报错 rawAgentData undefined
  () => [writerData.value?.content, writerData.value?.reasoning],
  async () => {
    if (!writerScrollContainer.value) return
    await nextTick()
    
    // 如果用户没有往上翻，才自动跟随到底部
    if (!isUserScrollingUp.value) {
      writerScrollContainer.value.scrollTop = writerScrollContainer.value.scrollHeight
    }
  },
  { deep: true }
)

// 辅助函数：格式化场景头 (Slugline)
const formatSlugline = (scene) => {
  const spaceMap = { 'interior': 'INT.', 'exterior': 'EXT.', 'interior/exterior': 'INT./EXT.', 'unknown': 'INT/EXT' }
  const space = spaceMap[scene.space] || 'INT./EXT.'
  const location = scene.location || '未知地点'
  const timeMap = { 'dawn': '黎明', 'morning': '早晨', 'noon': '中午', 'afternoon': '下午', 'evening': '傍晚', 'night': '夜晚', 'unknown': '日夜未知' }
  const time = timeMap[scene.time] || scene.time || ''
  return `${space} ${location} - ${time}`.toUpperCase()
}
</script>

<template>
  <div class="writer-panel">
    <div class="writer-header">
      <span class="title">🎬 主笔编剧 (Screenwriter)</span>
      <div class="header-right">
        <button 
          v-if="writerData.content" 
          class="download-btn" 
          @click="downloadScript"
        >
          ⬇️ 下载剧本
        </button>
        <span class="writer-status" :class="writerData.status">
          {{ writerData.status === 'processing' ? '✍️ 剧本撰写中...' : 
             writerData.status === 'done' ? '✅ 撰写完成' : '待命' }}
        </span>
      </div>
    </div>
    
    <div class="writer-body" ref="writerScrollContainer" @scroll="handleScroll">
      <details v-if="writerData.reasoning" class="writer-reasoning" :open="writerData.status === 'processing'">
        <summary>💡 查看主笔构思过程</summary>
        <div class="reasoning-content">{{ writerData.reasoning }}</div>
      </details>
      
      <div v-if="parsedScript" class="script-view">
        
        <div class="script-meta" v-if="parsedScript.chapter_title || parsedScript.chapter_logline">
          <h2 class="chapter-title">{{ parsedScript.chapter_title || '生成中...' }}</h2>
          <div class="logline" v-if="parsedScript.chapter_logline"><strong>一句话梗概:</strong> {{ parsedScript.chapter_logline }}</div>
          <div class="summary" v-if="parsedScript.chapter_summary"><strong>剧情提要:</strong> {{ parsedScript.chapter_summary }}</div>
        </div>

        <div v-if="parsedScript.scenes?.length" class="scenes-container">
          <div v-for="(scene, sIdx) in parsedScript.scenes" :key="sIdx" class="scene-block">
            
            <div class="slugline">{{ scene.scene_number ? scene.scene_number + '. ' : '' }}{{ formatSlugline(scene) }}</div>
            
            <div class="scene-purpose" v-if="scene.purpose || scene.conflict">
              <span v-if="scene.purpose">🎯 目标: {{ scene.purpose }} </span>
              <span v-if="scene.conflict">⚔️ 冲突: {{ scene.conflict }}</span>
            </div>

            <div class="action-lines" v-if="scene.action">
              {{ scene.action }}
            </div>

            <div v-if="scene.dialogue?.length" class="dialogue-container">
              <div v-for="(d, dIdx) in scene.dialogue" :key="dIdx" class="dialogue-block">
                <div class="speaker">{{ d.speaker || '...' }}</div>
                <div class="emotion" v-if="d.emotion">({{ d.emotion }})</div>
                <div class="line">{{ d.line || '...' }}</div>
              </div>
            </div>

          </div>
        </div>
        
        <div v-if="writerData.status === 'processing'" class="typing-indicator">
          <span>_</span>
        </div>
      </div>

      <div v-else class="fallback-view">
        <div v-if="!writerData.content" class="empty-text">等待大纲与人物数据就绪，准备起草...</div>
        <pre v-else class="raw-content">{{ writerData.content }}</pre>
      </div>

    </div>
  </div>
</template>

<style scoped>
.writer-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fdfdfd; /* 稍微泛黄的纸张底色 */
  border-left: 1px solid #e0e0e0;
}
.writer-header {
  padding: 12px 16px;
  background: #e6f7ff;
  border-bottom: 1px solid #91d5ff;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title { font-weight: 600; color: #0050b3; }
.header-right { display: flex; gap: 12px; align-items: center; font-size: 0.85rem; flex-wrap: nowrap; white-space: nowrap;}
.current-chapter-tag { background: #fff; padding: 2px 8px; border-radius: 4px; border: 1px solid #91d5ff; color: #0050b3; }
.writer-status.processing { color: #096dd9; animation: pulse 1.5s infinite; }
.writer-status.done { color: #389e0d; font-weight: bold; }

.writer-body {
  flex: 1;
  padding: 24px 40px; /* 剧本需要更宽的两侧留白 */
  overflow-y: auto;
  font-family: "Courier New", Courier, monospace; /* 🌟 核心：好莱坞标准剧本字体 */
  font-size: 1rem;
}

.writer-reasoning {
  margin-bottom: 24px;
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  font-family: sans-serif; /* 思考过程用普通字体 */
  font-size: 0.85rem;
  border-left: 3px solid #1890ff;
}
.reasoning-content { margin-top: 8px; color: #595959; white-space: pre-wrap; font-style: italic; }

/* 🌟 剧本排版样式 🌟 */
.script-view {
  max-width: 800px;
  margin: 0 auto;
  color: #1a1a1a;
  line-height: 1.6;
}

.script-meta {
  margin-bottom: 40px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e8e8e8;
  font-family: sans-serif;
}
.chapter-title { text-align: center; font-size: 1.5rem; margin-bottom: 16px; letter-spacing: 2px; }
.logline, .summary { margin-bottom: 8px; font-size: 0.9rem; color: #434343; }

.scene-block { margin-bottom: 32px; }

/* 场景标题：大写、加粗、靠左 */
.slugline {
  font-weight: bold;
  text-transform: uppercase;
  margin-bottom: 12px;
  background: #f0f0f0;
  display: inline-block;
  padding: 2px 6px;
}

/* 导演/分析辅助信息 */
.scene-purpose {
  font-family: sans-serif;
  font-size: 0.75rem;
  color: #8c8c8c;
  margin-bottom: 12px;
  padding: 4px 8px;
  background: #fafafa;
  border-left: 2px solid #d9d9d9;
}

/* 动作描写：正常顶格 */
.action-lines {
  margin-bottom: 16px;
  white-space: pre-wrap;
  text-align: justify;
}

/* 对白块：居中缩进排版 */
.dialogue-block {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  align-items: center; /* 角色名居中 */
}
.speaker {
  font-weight: bold;
  text-transform: uppercase;
  width: 50%;
  text-align: center;
}
.emotion {
  font-style: italic;
  width: 50%;
  text-align: center;
  margin-bottom: 4px;
}
.line {
  width: 60%; /* 对白区域比屏幕窄 */
  text-align: left;
}

.typing-indicator span {
  display: inline-block;
  width: 10px;
  height: 18px;
  background-color: #1a1a1a;
  animation: blink 1s step-end infinite;
}

.empty-text { text-align: center; color: #bfbfbf; margin-top: 40px; font-family: sans-serif; }
.raw-content { white-space: pre-wrap; font-family: inherit; color: #595959; }

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
/* 🌟 新增下载按钮样式 */
.download-btn {
  background: #ffffff;
  border: 1px solid #91d5ff;
  color: #0050b3;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.3s;
  flex-shrink: 0; /* 🌟 防止按钮被挤扁 */
  white-space: nowrap;
}

.download-btn:hover {
  background: #bae0ff;
  border-color: #1890ff;
}
.writer-status {
  flex-shrink: 0; 
  white-space: nowrap;
}
</style>