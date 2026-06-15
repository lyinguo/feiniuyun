// src/composables/useNovelStream.js
import { ref, computed } from 'vue'
import { startNovelStream, closeNovelStream } from '@/services/sseService'

export function useNovelStream(store) {
  // 1. 定义私有状态

  // 2. 正则切片工具
  const extractTag = (text, tag) => {
    const regex = new RegExp(`<${tag}>([\\s\\S]*?)(?:</${tag}>|$)`)
    const match = text.match(regex)
    return match ? match[1].trim() : ''
  }

  // 3. 实时响应式切片引擎
    const parsedStream = computed(() => {
        const text = store.sseState.rawStreamText
        return {
        script: extractTag(text, 'script'),
        newStoryProgress: extractTag(text, 'story_progress'),
        newCharacters: extractTag(text, 'new_characters'),
        newLocations: extractTag(text, 'new_locations')
        }
    })

    const displayData = computed(() => {
    const isStreamingCurrent = store.sseState.isStreaming && 
      store.sseState.currentProcessingTitle === store.currentChapter?.title

    if (isStreamingCurrent) {
      // 状态 A：显示正在全自动生成的实时切片数据
      return {
        isStreaming: true,
        script: parsedStream.value.script,
        reasoningText: store.sseState.reasoningText,
        oldStoryProgress: store.sseState.oldStoryProgress,
        newStoryProgress: parsedStream.value.newStoryProgress || store.sseState.newStoryProgress,
        retrievedCharacters: store.sseState.retrievedCharacters,
        retrievedLocations: store.sseState.retrievedLocations,
        newCharacters: parsedStream.value.newCharacters,
        newLocations: parsedStream.value.newLocations
      }
    }
    else if (
      !store.scriptCache[store.currentChapter?.id]?.yaml && 
      (
        store.sseState.rawStreamText || 
        store.sseState.reasoningText ||
        store.sseState.oldStoryProgress || 
        store.sseState.retrievedCharacters || 
        store.sseState.retrievedLocations
      )
    ){
      return {
        isStreaming: false,
        script: parsedStream.value.script, // 🌟 依然用正则去切底座里的残余碎字
        reasoningText: store.sseState.reasoningText,
        oldStoryProgress: store.sseState.oldStoryProgress,
        newStoryProgress: parsedStream.value.newStoryProgress,
        retrievedCharacters: store.sseState.retrievedCharacters,
        retrievedLocations: store.sseState.retrievedLocations,
        newCharacters: parsedStream.value.newCharacters,
        newLocations: parsedStream.value.newLocations
      }
    } 
    else {
      // 状态 B：去底座读取 Pinia 里的全量历史快照缓存
      const cache = store.scriptCache[store.currentChapter?.id] || {}
      console.log(`📖 [读取快照] 章节ID: ${store.currentChapter?.id} | 思考长度: ${cache.reasoningText?.length}`);
      return {
        isStreaming: false,
        script: cache.yaml || '',
        reasoningText: cache.reasoningText || '',
        oldStoryProgress: cache.oldStoryProgress || '',
        newStoryProgress: cache.newStoryProgress || '',
        retrievedCharacters: cache.retrievedCharacters || '',
        retrievedLocations: cache.retrievedLocations || '',
        newCharacters: cache.newCharacters || '',
        newLocations: cache.newLocations || ''
      }
    }
  })

  const startStream = (folderName) => {
    // 直接把文件夹暗号，原封不动地传给底座里的 sseService
    startNovelStream(folderName, parsedStream)
  }

  return {
    parsedStream,
    displayData,
    startStream,
    stopStream: closeNovelStream // 顺便暴露一个手动停止的接口给前端
  }
}