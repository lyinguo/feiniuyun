// src/stores/agentStore.js
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useNovelStore } from './novelStore' // 🌟 引入小说底座，获取当前指针对齐

// 生成空白面板的函数
const createEmptyStreams = () => ({
  background: { status: 'idle', reasoning: '', content: '' },
  character: { status: 'idle', reasoning: '', content: '' },
  relationship: { status: 'idle', reasoning: '', content: '' },
  casting: { status: 'idle', reasoning: '', content: '' },
  screenwriter: { status: 'idle', reasoning: '', content: '' },
  critic: { status: 'idle', reasoning: '', content: '' },
  continuity_critic: { status: 'idle', reasoning: '', content: '' },
  summarizer: { status: 'idle', reasoning: '', content: '' },
})

export const useAgentStore = defineStore('agent', () => {
  const isStreaming = ref(false)
  const errorMessage = ref('')
  
  const novelStore = useNovelStore()

  // ============ 🌟 核心状态：多章节数据大字典 ============
  // 数据结构：{ [chapterId]: { background: {...}, character: {...}, ... } }
  const chapterStreams = ref({})
  const activeTaskChapterId = ref(null)
  // ============ 🌟 核心指针：当前屏幕该看哪一章？ ============
  // 前端四个面板组件将直接绑定这个 computed！
  // 它会自动紧盯 novelStore 的章节选中情况，瞬间切换显示内容，且绝不丢失！
  const currentAgentStreams = computed(() => {
    const currentId = novelStore.currentChapterId
    if (currentId === null) return createEmptyStreams()
    
    // 如果字典里有这一章的数据，就显示；如果没有，就显示空白面板
    return chapterStreams.value[currentId] || createEmptyStreams()
  })

  // ============ Actions ============

  /**
   * 🌟 后端推流写入口：获取或创建某一章的流数据对象
   * 哪怕用户在看第一章，只要你传入第二章的 ID，后端就能在后台默默给第二章写数据！
   */
  function getOrCreateStream(chapterId) {
    if (!chapterStreams.value[chapterId]) {
      chapterStreams.value[chapterId] = createEmptyStreams()
    }
    return chapterStreams.value[chapterId]
  }

  /**
   * 仅重置特定某一章的 AI 状态（例如重新生成该章时）
   */
  function resetChapterStream(chapterId) {
    chapterStreams.value[chapterId] = createEmptyStreams()
  }

  /**
   * 彻底清空所有章节的流状态（例如上传了新小说时）
   */
  function resetAllStreams() {
    isStreaming.value = false
    errorMessage.value = ''
    activeTaskChapterId.value = null
    chapterStreams.value = {}
  }

  return {
    isStreaming,
    errorMessage,
    chapterStreams,
    activeTaskChapterId,
    currentAgentStreams, // 👈 暴露给前端 UI 读取
    getOrCreateStream,   // 👈 暴露给后端 SSE 写入
    resetChapterStream,
    resetAllStreams
  }
})