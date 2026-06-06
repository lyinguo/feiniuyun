import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

/**
 * 小说转剧本工作台的全局状态。
 * 后端 metadata 的字段映射集中在 setNovelFromMetadata 里完成。
 */
export const useNovelStore = defineStore('novel', () => {
  // ============ State ============

  /** 小说基本信息（映射自 /api/parse-epub 返回的 metadata） */
  const bookInfo = ref({
    title: '',
    totalCharCount: 0, // ← 后端 total_char_count
    totalTokens: 0, // ← 后端 total_estimated_tokens
    chapterCount: 0,
  })

  /** 解析后小说所在的输出目录名；get-chapter 与整本生成（project_path）都要用 */
  const folderName = ref('')

  /**
   * 章节列表（已规范化），每项：
   *   { id, title, logicalIndex, charCount, estimatedTokens, isChunked, files[], status }
   */
  const chapters = ref([])

  /** 当前选中的章节 id（数组下标） */
  const currentChapterId = ref(null)

  /**
   * 按章节缓存已生成剧本：{ [chapterId]: { yaml, diagnostics } }
   * 切换章节时不清空，回到该章可直接恢复，不丢失。
   */
  const scriptCache = ref({})

  /**
   * 调用方身份，暂用占位值。
   * TODO(user-system): 接入真实用户系统后，用登录用户与会话替换 userId / threadId。
   */
  const userId = ref('web_user')

  /** 单章异步操作（上传 / 生成）共用的加载与错误状态 */
  const isLoading = ref(false)
  const errorMessage = ref('')

  // ============ 整本流式生成状态 ============
  const isStreaming = ref(false)
  const streamProgress = ref({ current: 0, total: 0 })
  const streamCurrentTitle = ref('') // 正在处理的段标题
  const streamUnits = ref([]) // 已完成单元 [{ unitIndex, title, sceneCount, warningCount, plotText }]
  const streamStats = ref(null) // 最终 / 最新统计
  const streamError = ref('')
  const streamDone = ref(false)

  // ============ Getters ============

  const hasNovel = computed(() => chapters.value.length > 0)

  const currentChapter = computed(
    () => chapters.value.find((c) => c.id === currentChapterId.value) ?? null,
  )

  /** 生成时用作记忆 / 连续性的会话 id：暂以书籍目录名作 thread，让同书各段共享上下文 */
  const threadId = computed(() => folderName.value || 'default-thread')

  /** 当前章节的剧本 / 提示从缓存派生（切换章节自动恢复） */
  const currentScript = computed(() => scriptCache.value[currentChapterId.value]?.yaml ?? '')
  const diagnostics = computed(() => scriptCache.value[currentChapterId.value]?.diagnostics ?? [])

  // ============ Actions ============

  /**
   * 把 parse-epub 返回的后端 metadata 规范化后载入 store，并默认选中第一章。
   * 在这里集中完成 snake_case → 前端字段 的映射。
   */
  function setNovelFromMetadata(metadata = {}, folder = '') {
    folderName.value = folder
    bookInfo.value = {
      title: metadata.book_title ?? '未命名',
      totalCharCount: metadata.total_char_count ?? 0,
      totalTokens: metadata.total_estimated_tokens ?? 0,
      chapterCount: metadata.chapters?.length ?? 0,
    }
    chapters.value = (metadata.chapters ?? []).map((ch, index) => ({
      id: index, // logical_index 可能重复，改用数组下标作稳定唯一 id
      title: ch.original_title ?? `第 ${index + 1} 章`,
      logicalIndex: ch.logical_index,
      charCount: ch.total_char_count ?? 0,
      estimatedTokens: ch.total_estimated_tokens ?? 0,
      isChunked: ch.is_chunked ?? false,
      files: ch.is_chunked
        ? (ch.chunks ?? []).map((c) => c.file_path)
        : [ch.file_path].filter(Boolean),
      status: 'idle',
    }))
    currentChapterId.value = chapters.value[0]?.id ?? null
    scriptCache.value = {}
    errorMessage.value = ''
    resetStream()
  }

  /** 选中某一章节（剧本与提示会从缓存自动恢复，无需清空） */
  function selectChapter(chapterId) {
    currentChapterId.value = chapterId
  }

  /** 保存某章节的生成结果（按章缓存的写入口） */
  function saveChapterScript(chapterId, { yaml, diagnostics: diags } = {}) {
    scriptCache.value[chapterId] = { yaml: yaml ?? '', diagnostics: diags ?? [] }
  }

  /** 更新某一章节的状态（生成中 / 完成 / 失败） */
  function updateChapterStatus(chapterId, status) {
    const target = chapters.value.find((c) => c.id === chapterId)
    if (target) target.status = status
  }

  /** 重置整个 store（例如重新上传新书时） */
  function reset() {
    bookInfo.value = { title: '', totalCharCount: 0, totalTokens: 0, chapterCount: 0 }
    folderName.value = ''
    chapters.value = []
    currentChapterId.value = null
    scriptCache.value = {}
    isLoading.value = false
    errorMessage.value = ''
    resetStream()
  }

  // —— 整本流式生成 ——

  function resetStream() {
    isStreaming.value = false
    streamProgress.value = { current: 0, total: 0 }
    streamCurrentTitle.value = ''
    streamUnits.value = []
    streamStats.value = null
    streamError.value = ''
    streamDone.value = false
  }

  /** 归并一条流式事件（事件结构对应后端 stream_project_events） */
  function applyStreamEvent(event) {
    switch (event.event) {
      case 'start':
        streamProgress.value = { current: 0, total: event.unit_count ?? 0 }
        streamUnits.value = []
        streamStats.value = null
        streamError.value = ''
        streamDone.value = false
        break
      case 'unit_start':
        streamCurrentTitle.value = event.chapter_title ?? ''
        break
      case 'unit_done': {
        const act = event.act ?? {}
        streamUnits.value.push({
          unitIndex: event.unit_index,
          title: act.chapter_title ?? streamCurrentTitle.value,
          sceneCount: act.scene_count ?? 0,
          warningCount: (act.critic_warnings?.length ?? 0) + (act.continuity_warnings?.length ?? 0),
          plotText: event.plot_text ?? '',
        })
        streamProgress.value = {
          current: event.unit_index ?? streamProgress.value.current,
          total: event.unit_count ?? streamProgress.value.total,
        }
        streamStats.value = event.stats ?? streamStats.value
        streamCurrentTitle.value = ''
        break
      }
      case 'done':
        streamStats.value = event.data?.stats ?? streamStats.value
        streamDone.value = true
        break
      case 'error':
        streamError.value = event.message ?? '生成失败'
        break
      default:
        break
    }
  }

  return {
    // state
    bookInfo,
    folderName,
    chapters,
    currentChapterId,
    scriptCache,
    userId,
    isLoading,
    errorMessage,
    isStreaming,
    streamProgress,
    streamCurrentTitle,
    streamUnits,
    streamStats,
    streamError,
    streamDone,
    // getters
    hasNovel,
    currentChapter,
    threadId,
    currentScript,
    diagnostics,
    // actions
    setNovelFromMetadata,
    selectChapter,
    saveChapterScript,
    updateChapterStatus,
    reset,
    resetStream,
    applyStreamEvent,
  }
})
