/**
 * 后端接口封装（FastAPI）。
 *
 * 所有请求统一走 /api 前缀，由 vite.config.js 的 server.proxy 转发到
 * http://127.0.0.1:8000。已确认后端所有路由均以 /api 开头，无需 rewrite。
 *
 * 注意后端有【两套错误约定】：
 *   - epub 路由 (/api/parse-epub, /api/get-chapter)：出错仍返回 HTTP 200，
 *     靠响应体里的 status:"error" 判断；
 *   - scripts 路由 (/api/scripts/*)：出错是真正的 HTTP 4xx/5xx，信息在 detail 字段
 *     （流式接口的错误则作为流内 {event:"error"} 事件下发，HTTP 仍为 200）。
 */

const BASE_URL = '/api'

/**
 * 基础请求模板：处理 HTTP 层错误（适用于 scripts 路由及通用场景）。
 * @param {string} path 相对 /api 的路径，如 '/parse-epub'
 * @param {RequestInit} [options] 原生 fetch 配置
 * @returns {Promise<any>} 解析后的响应体（204 返回 null）
 */
async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData

  const resp = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      // FormData（文件上传）交给浏览器自动设置 Content-Type 与 boundary
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  })

  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const data = await resp.json()
      detail = data.detail ?? detail // FastAPI HTTPException 的错误字段
    } catch {
      // 响应体非 JSON，忽略
    }
    throw new Error(`请求失败 (${resp.status}): ${detail}`)
  }

  return resp.status === 204 ? null : resp.json()
}

/**
 * epub 路由专用：HTTP 恒为 200，需根据响应体里的 status 字段判定成败。
 */
function ensureEpubOk(payload) {
  if (payload?.status === 'error') {
    throw new Error(payload.message ?? '后端处理失败')
  }
  return payload
}

/**
 * 上传 EPUB 并解析 / 拆分章节。
 * POST /api/parse-epub  (multipart，字段名 file)
 * @param {File} file
 * @returns {Promise<{ status, message, data, folder_name }>}
 *   data 为 book_metadata（含 book_title / total_char_count / chapters[]）
 */
export async function parseEpub(file) {
  const form = new FormData()
  form.append('file', file)
  const payload = await request('/parse-epub', { method: 'POST', body: form })
  return ensureEpubOk(payload)
}

/**
 * 获取单个章节 / 分块文件的纯文本。
 * GET /api/get-chapter?folder=<folder_name>&file_name=<file_path>
 * @param {string} folder parse-epub 返回的 folder_name
 * @param {string} fileName 章节的 file_path（如 './chapter_001_001.txt'）
 * @returns {Promise<string>} 章节正文
 */
export async function getChapter(folder, fileName) {
  const query = new URLSearchParams({ folder, file_name: fileName })
  const payload = await request(`/get-chapter?${query.toString()}`)
  return ensureEpubOk(payload).content
}

/**
 * 将一段小说原文转换为剧本（YAML）。
 * POST /api/scripts/convert
 * @param {object} payload ConvertNovelRequest，必填 user_id / thread_id / novel_text
 * @returns {Promise<{ code, message, data }>} data 为 ConvertNovelData（含 yaml / diagnostics …）
 */
export function convertNovel(payload) {
  return request('/scripts/convert', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * 整本流式生成（NDJSON）：对已解析的项目目录做全书改编，逐事件回调。
 * POST /api/scripts/convert-project-stream
 * 事件类型：start / unit_start / unit_done / done / error（详见后端 stream_project_events）。
 * @param {object} payload ConvertProjectRequest，必填 user_id / thread_id / project_path
 * @param {(event: object) => void} onEvent 每解析到一条事件触发一次
 * @param {{ signal?: AbortSignal }} [opts] 传 AbortSignal 可中断生成
 */
export async function convertProjectStream(payload, onEvent, { signal } = {}) {
  const resp = await fetch(`${BASE_URL}/scripts/convert-project-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  if (!resp.ok || !resp.body) {
    let detail = resp.statusText
    try {
      detail = (await resp.json()).detail ?? detail
    } catch {
      // 忽略
    }
    throw new Error(`请求失败 (${resp.status}): ${detail}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  // NDJSON：每行一个完整 JSON 事件，可能跨多个网络分片，需要按换行切分
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let newlineIndex
    while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newlineIndex).trim()
      buffer = buffer.slice(newlineIndex + 1)
      if (line) onEvent(JSON.parse(line))
    }
  }

  const tail = buffer.trim()
  if (tail) onEvent(JSON.parse(tail))
}

export default { parseEpub, getChapter, convertNovel, convertProjectStream }
