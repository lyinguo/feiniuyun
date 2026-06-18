// src/services/sseService.js
import { useNovelStore } from '@/stores/novelStore'

// 定义一个全局变量，用来持有 EventSource 实例，方便随时手动关闭
let currentEvtSource = null

/**
 * 启动全书滚动 RAG 流式生成服务
 * @param {string} jsonPath 后端所需元数据路径
 * @param {string} outputDir 后端剧本输出目录
 * @param {object} parsedStreamRef 传入 Composable 的解析引擎（用于在 node_finish 时提取最新数据）
 */
export function startNovelStream(folderName, parsedStreamRef) {
  const store = useNovelStore()

  // 1. 如果已有连接，先断开，防止多次点击创建多个长连接
  if (currentEvtSource) {
    currentEvtSource.close()
  }

  // 2. 初始化 Store 里的临时流式传送带
  store.sseState.isStreaming = true
  store.sseState.rawStreamText = ''
  store.sseState.reasoningText = ''
  store.sseState.errorMessage = ''
  store.sseState.currentProcessingTitle = '准备中...'

  // 3. 构建 SSE URL 并建立长连接
  const sseUrl = `http://localhost:8000/api/v1/run_conversion?folder_name=${encodeURIComponent(folderName)}`
  currentEvtSource = new EventSource(sseUrl)

  // 4. 开始监听收音机广播
  currentEvtSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    switch (data.type) {
      case 'chapter_start':
        store.sseState.currentProcessingTitle = data.title
        store.sseState.rawStreamText = ''
        store.sseState.retrievedCharacters = ''
        store.sseState.reasoningText = ''
        store.sseState.retrievedLocations = ''
        store.sseState.oldStoryProgress = ''
        store.sseState.newStoryProgress = ''
        // 自动联动目录树高亮选中
        if (store.chapters && store.chapters.length) {
          const targetChapter = store.chapters.find(c => 
            c.title.replace(/\s+/g, '') === data.title.replace(/\s+/g, '') && 
            c.status !== 'done'
          )
          if (targetChapter) store.selectChapter(targetChapter.id)
        }
        break

      case 'retrieval_done':
        store.sseState.retrievedCharacters = data.retrieved_characters
        store.sseState.retrievedLocations = data.retrieved_locations
        break

      case 'node_start':
        store.sseState.oldStoryProgress = data.story_progress ?? ''
        break

      case 'reasoning':
        // 🌟 新增：接收深度思考的碎字
        store.sseState.reasoningText += data.content
        break

      case 'token':
        // 碎字疯狂塞进底座
        store.sseState.rawStreamText += data.content
        break

      case 'node_finish':
        // 当一章结束，立刻把数据打包固化存入 Store 底座的 scriptCache 桶中
        if (store.chapters && store.chapters.length) {
          const finishTitle = data.title || store.sseState.currentProcessingTitle
          // const targetChapter = store.chapters.find(c => 
          //   (c.title === data.title || c.title.startsWith(data.title + ' (')) && 
          //   c.status !== 'done'
          // )
          // 🔴 探照灯：看看到底是什么妖魔鬼怪导致匹配失败！
          console.log(`🚨 [匹配测试] 后端发来的标题: "${finishTitle}"`);
          console.log(`🚨 [匹配测试] 前端仓库的标题列表:`, store.chapters.map(c => c.title));
          const targetChapter = store.chapters.find(c => 
            c.title.replace(/\s+/g, '') === finishTitle.replace(/\s+/g, '') && 
            c.status !== 'done'
          )
          if (targetChapter) {
            store.saveChapterScript(targetChapter.id, {
                yaml: String(parsedStreamRef.value.script),
                reasoningText: store.sseState.reasoningText,
                newStoryProgress: String(parsedStreamRef.value.newStoryProgress),
                oldStoryProgress: String(store.sseState.oldStoryProgress),
                retrievedCharacters: String(store.sseState.retrievedCharacters),
                retrievedLocations: String(store.sseState.retrievedLocations),
                newCharacters: String(parsedStreamRef.value.newCharacters),
                newLocations: String(parsedStreamRef.value.newLocations)
              })
              store.updateChapterStatus(targetChapter.id, 'done')
          }}
        break

      case 'pipeline_complete':
        closeNovelStream()
        store.sseState.isStreaming = false
        store.sseState.currentProcessingTitle = '全书转换完成！'
        break

      case 'error':
        closeNovelStream()
        store.sseState.isStreaming = false
        store.sseState.errorMessage = data.message
        break
    }
  }

  // 5. 异常网络断开善后
  currentEvtSource.onerror = () => {
    if (currentEvtSource === null) return
    closeNovelStream()
    store.sseState.isStreaming = false
    store.sseState.errorMessage = "新版引擎通信被动断开"
  }
}

/**
 * 主动关闭 SSE 流（比如用户点击了停止，或者页面强制退出时调用）
 */
export function closeNovelStream() {
  if (currentEvtSource) {
    currentEvtSource.close()
    currentEvtSource = null
  }
}