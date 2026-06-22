// src/composables/useAgentStream.js
import { useAgentStore } from '@/stores/agentStore'
import { useNovelStore } from '@/stores/novelStore'
import { startAgentStream, closeAgentStream } from '@/services/agentSseService'

export function useAgentStream() {
  const agentStore = useAgentStore()
  const novelStore = useNovelStore()

  // ==========================================
  // 🧠 核心：多智能体数据分拣与自动翻页网关
  // ==========================================
  const handleAgentData = (data) => {
    // 🌟 核心隔离：优先用后端传的 ID，其次用全局锁死的写字笔 ID。
    // 彻底砍掉对 novelStore.currentChapterId 的依赖！断绝“看哪写哪”的 Bug。
    const targetId = data.unit_index ?? data.chapter_id ?? agentStore.activeTaskChapterId
    
    // 如果没有任何可用 ID，直接拦截，防止胡乱写入
    if (targetId === null || targetId === undefined) return 

    // 拿到这一章专属的干净大白板
    const targetStream = agentStore.getOrCreateStream(targetId)

    switch (data.type) {
      case 'agent_start':
        if (targetStream[data.agent]) targetStream[data.agent].status = 'processing'
        break

      case 'reasoning':
        if (targetStream[data.agent]) targetStream[data.agent].reasoning += data.content
        break

      case 'token':
        if (targetStream[data.agent]) targetStream[data.agent].content += data.content
        break

      case 'chapter_done':
        console.log(`✅ 后端图执行完毕，第 ${targetId} 章全链路完成！`)
        
        // 1. 目录变绿
        novelStore.updateChapterStatus(targetId, 'done')

        // 2. 寻找下一章，移交写字笔
        const currentIndex = novelStore.chapters.findIndex(c => c.id === targetId)
        if (currentIndex !== -1 && currentIndex + 1 < novelStore.chapters.length) {
          const nextChapterId = novelStore.chapters[currentIndex + 1].id
          agentStore.activeTaskChapterId = nextChapterId
          novelStore.updateChapterStatus(nextChapterId, 'processing')
          
          // 3. 自动翻页
          novelStore.selectChapter(nextChapterId)
        }
        break

      case 'agent_done':
        if (targetStream[data.agent]) {
          targetStream[data.agent].status = 'done'
        }
        break
    }

    if (data.event === 'pipeline_complete') {
      agentStore.isStreaming = false
      agentStore.activeTaskChapterId = null // 释放写字笔
      Object.keys(targetStream).forEach(key => {
        if (targetStream[key].status === 'processing') targetStream[key].status = 'done'
      })
    } else if (data.event === 'error') {
      agentStore.errorMessage = data.message
      agentStore.isStreaming = false
      agentStore.activeTaskChapterId = null
    }
  }

  // ==========================================
  // 🚀 暴露给 UI 组件的操作方法
  // ==========================================
  const startStream = (folderName) => {
    // 🌟 任务拉起的一瞬间，将全局写字笔初始化为当前用户选中的章节
    agentStore.activeTaskChapterId = novelStore.currentChapterId
    
    if (agentStore.activeTaskChapterId !== null) {
      agentStore.resetChapterStream(agentStore.activeTaskChapterId)
      novelStore.updateChapterStatus(agentStore.activeTaskChapterId, 'processing')
    }
    
    agentStore.isStreaming = true
    
    const payload = {
      project_path: folderName,
      user_id: novelStore.userId || "default_user",
      thread_id: novelStore.threadId || "default_thread"
    }
    
    startAgentStream(payload, handleAgentData)
  }

  const stopStream = () => {
    closeAgentStream()
    agentStore.isStreaming = false
    agentStore.activeTaskChapterId = null
    agentStore.errorMessage = '任务已被手动停止'
  }

  return {
    startStream,
    stopStream
  }
}