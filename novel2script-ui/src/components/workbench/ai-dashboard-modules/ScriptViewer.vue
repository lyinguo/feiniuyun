<script setup>
import { ref, watch, nextTick, computed, inject } from 'vue'
// 引入你抽离的解析工具
import { parseStreamingJson, getCharacterStyle, convertToTxtFormat, convertToYamlFormat } from '@/utils/scriptParsers'
import { useNovelStore } from '@/stores/novelStore'
const store = useNovelStore()
const props = defineProps({
  displayData: {
    type: Object,
    required: true
  }
})
const setHoveredRange = inject('setHoveredRange', () => {})
const setLockedRange = inject('setLockedRange', () => {})

// 2. 鼠标悬停：触发临时高亮
const handleMouseEnterScene = (range) => {
  if (range && range.length > 0) setHoveredRange(range)
}

// 3. 鼠标移出：清空临时高亮（由于父组件的 computed 逻辑，此时会自动恢复显示已锁定的高亮）
const handleMouseLeaveScene = () => {
  setHoveredRange([])
}

// 4. 鼠标点击：滚动定位 + 锁定高亮
const scrollToSource = (range) => {
  if (!range || !range.length) return
  
  // 🌟 核心新增：把这个区间死死“锁住”
  setLockedRange(range)
  
  // 提取首段数字
  const startNum = parseInt(range[0].split('_').pop().replace(/\D/g, ''))
  const targetElement = document.getElementById(`novel-p-${startNum}`)
  
  if (targetElement) {
    targetElement.scrollIntoView({ 
      behavior: 'smooth', 
      block: 'center' 
    })
  }
}

const scriptBodyRef = ref(null)
watch(
  () => props.displayData.script,
  async (newScript) => {
    if (!newScript || !scriptBodyRef.value) return
    
    // 等待 Vue 虚拟 DOM 更新
    await nextTick()
    
    // 🌟 核心修复：等待浏览器实际完成文字绘制，防止高度计算滞后
    requestAnimationFrame(() => {
      if (!scriptBodyRef.value) return

      // 1. 滚外层大容器（照顾 Visual 分镜模式）
      scriptBodyRef.value.scrollTop = scriptBodyRef.value.scrollHeight

      // 2. 滚内层代码框（照顾 TXT / JSON / YAML 模式下的独立滚动条）
      const innerPreBox = scriptBodyRef.value.querySelector('.terminal-pre-box')
      if (innerPreBox) {
        innerPreBox.scrollTop = innerPreBox.scrollHeight
      }
      
      // 兼容性补充：如果 panel 自身有滚动条也一并滚动
      const innerPanel = scriptBodyRef.value.querySelector('.code-terminal-panel')
      if (innerPanel) {
        innerPanel.scrollTop = innerPanel.scrollHeight
      }
    })
  }
)

const isReasoningExpanded = ref(false)
const reasoningBoxRef = ref(null)

// 提取最新的一小段思考文字，用于折叠状态下展示跑马灯效果
const reasoningSnippet = computed(() => {
  const text = props.displayData?.reasoningText || ''
  if (!text) return '等待思考...'
  // 取最后 18 个字符展示
  return text.length > 18 ? '...' + text.slice(-18).replace(/\n/g, ' ') : text.replace(/\n/g, ' ')
})
// 监听思考文本变化，如果面板是展开的，就自动滚动到底部
watch(
  () => props.displayData?.reasoningText,
  async () => {
    if (isReasoningExpanded.value && reasoningBoxRef.value) {
      await nextTick()
      reasoningBoxRef.value.scrollTop = reasoningBoxRef.value.scrollHeight
    }
  }
)
// ==========================================

// 🌟 1. 声明当前的显示风格模式：'visual' (分镜) | 'json' | 'yaml' | 'txt'
const scriptStyleMode = ref('visual')
// 🌟 2. 快捷切换函数
const setScriptStyle = (mode) => {
  scriptStyleMode.value = mode
}
const parsedScenes = computed(() => {
  if (!props.displayData.script) return []
  return parseStreamingJson(props.displayData.script)
})
const getElemStyle = (character, type) => {
  if (character === '【环境】') return {}
  
  const style = getCharacterStyle(character)
  
  if (type === 'tag') {
    return { background: style.tagBg, borderColor: style.tagBorder, color: style.tagText }
  }
  if (type === 'bubble') {
    return { background: style.background, borderColor: style.borderColor }
  }
  if (type === 'quote') {
    return { color: style.quoteColor }
  }
  return {}
}
// 🌟 核心新增：智能下载当前剧本文件 (动态命名版)
const handleDownload = () => {
  if (!props.displayData.script) {
    alert('当前没有可下载的剧本数据！')
    return
  }

  // 1. 从 store 中动态获取书名和章节名 (做兜底处理防止空值报错)
  const bookName = store.folderName || '未知小说'
  const chapterName = store.currentChapter?.title || '未知章节'
  
  // 2. 拼接文件名，并用正则剔除掉 Windows/Mac 严禁出现在文件名里的特殊字符
  const safePrefix = `${bookName}_${chapterName}`
    .replace(/\//g, '-') // 把 1/2 变成 1-2
    .replace(/[\\:*?"<>|]/g, '') // 剔除其他非法字符
    
  let filename = `${safePrefix}_剧本`
  
  let content = ''
  let mimeType = 'text/plain;charset=utf-8'

  // 3. 根据当前视图模式，决定下载的格式内容和后缀名
  if (scriptStyleMode.value === 'json') {
    content = props.displayData.script
    filename += '.json'
    mimeType = 'application/json;charset=utf-8'
  } else if (scriptStyleMode.value === 'yaml') {
    content = convertToYamlFormat(props.displayData.script)
    filename += '.yaml'
  } else {
    // txt 模式和 visual (分块) 模式，统一默认下载为排版好的 TXT 文本
    content = convertToTxtFormat(props.displayData.script)
    filename += '.txt'
  }

  // 利用 Blob 触发浏览器原生下载机制
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>

<template>
    <div class="ai-card script-card">
        <div class="ai-card__header">
            <div class="header-left-title">
            <span>🎬 规范剧本正文 (多模态排版引擎)</span>
              <span v-if="displayData.isStreaming" class="streaming-indicator"></span>
                <div class="reasoning-module" v-if="displayData.reasoningText">
                <div class="reasoning-pill" @click="isReasoningExpanded = !isReasoningExpanded">
                  <span class="think-icon">💡</span>
                  <span class="think-text snippet-text" v-if="!isReasoningExpanded">{{ reasoningSnippet }}</span>
                  <span class="think-text" v-else>深度思考过程 (点击收起)</span>
                </div>
                <div class="reasoning-panel" v-show="isReasoningExpanded" ref="reasoningBoxRef">
                  {{ displayData.reasoningText }}
                </div>
              </div>
            </div>
            
            <div class="script-mode-selector">
            <button 
                class="mode-btn" 
                :class="{ 'is-active-btn': scriptStyleMode === 'visual' }"
                @click="setScriptStyle('visual')"
            >🎥 纯分块</button>
            <button 
                class="mode-btn" 
                :class="{ 'is-active-btn': scriptStyleMode === 'json' }"
                @click="setScriptStyle('json')"
            >{} JSON</button>
            <button 
                class="mode-btn" 
                :class="{ 'is-active-btn': scriptStyleMode === 'yaml' }"
                @click="setScriptStyle('yaml')"
            >📝 YAML</button>
            <button 
                class="mode-btn" 
                :class="{ 'is-active-btn': scriptStyleMode === 'txt' }"
                @click="setScriptStyle('txt')"
            >📄 TXT</button>
            <span class="btn-divider">|</span>
            <button class="mode-btn btn-download" @click="handleDownload">
              📥 下载
            </button>
            </div>
        </div>
  
  <div ref="scriptBodyRef" class="script-body-scroll-wrapper">
    
    <template v-if="scriptStyleMode === 'visual'">
      <template v-if="parsedScenes.length">
        <div 
          v-for="(sceneBlock, sIdx) in parsedScenes" 
          :key="sIdx" 
          class="scene-group"
          @mouseenter="handleMouseEnterScene(sceneBlock.source_paragraphs)"
          @mouseleave="handleMouseLeaveScene"
        >
          <div class="scene-title-bar">
            <span>🎥 {{ sceneBlock.scene }}</span>
            
            <button 
              v-if="sceneBlock.source_paragraphs && sceneBlock.source_paragraphs.length" 
              class="trace-capsule-btn"
              @click.stop="scrollToSource(sceneBlock.source_paragraphs)"
              title="点击快速定位到原文"
            >
              📌 源文: {{ sceneBlock.source_paragraphs.join(' ~ ') }}
            </button>
          </div>
          <div v-if="sceneBlock.summary" class="scene-summary-box">
            <strong>🎬 场景大纲概要：</strong>{{ sceneBlock.summary }}
          </div>

          <div class="elements-timeline">
            <div 
              v-for="(elem, eIdx) in sceneBlock.elements" 
              :key="eIdx" 
              class="element-row"
              :class="{ 'environment-row': elem.character === '【环境】' }"
            >
              <div 
                class="elem-character"
                :style="getElemStyle(elem.character, 'tag')"
              >
                {{ elem.character }}
              </div>
              
              <div class="elem-content">
                <div v-if="elem.action" class="action-capsule">
                  <span class="capsule-tag">ACTION</span>
                  <span class="capsule-text">{{ elem.action }}</span>
                </div>

                <div 
                  v-if="elem.dialogue" 
                  class="dialogue-bubble"
                  :style="getElemStyle(elem.character, 'bubble')"
                >
                  <span 
                    class="quote-mark"
                    :style="getElemStyle(elem.character, 'quote')"
                  >“</span>
                  <div class="bubble-text">{{ elem.dialogue }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <div v-if="displayData.isStreaming" class="empty-state">
          🚀 正在高频流式解析并排版最新剧本中，请稍后...
          <pre class="json-text-fallback">{{ displayData.script }}</pre>
        </div>
        <div v-else class="empty-state">请点击右上角「生成整本剧本」或选择已有缓存章节</div>
      </template>
    </template>

    <template v-else-if="scriptStyleMode === 'json'">
      <div class="code-terminal-panel">
        <pre class="terminal-pre-box json-theme-color">{{ displayData.script || '// 暂无原始数据...' }}</pre>
      </div>
    </template>

    <template v-else-if="scriptStyleMode === 'yaml'">
      <div class="code-terminal-panel">
        <pre class="terminal-pre-box yaml-theme-color">{{ convertToYamlFormat ? convertToYamlFormat(displayData.script) : displayData.script }}</pre>
      </div>
    </template>

    <template v-else-if="scriptStyleMode === 'txt'">
      <div class="code-terminal-panel txt-paper-theme">
        <pre class="terminal-pre-box txt-theme-color">{{ convertToTxtFormat(displayData.script) }}</pre>
      </div>
    </template>

  </div>
  </div>
  </template>
<style>
/* 引入并让它对所有子组件生效 */
@import './ai-dashboard-theme.css';
</style>