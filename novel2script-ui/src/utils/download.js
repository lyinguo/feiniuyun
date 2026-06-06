/** 触发浏览器把一段文本下载为文件。 */
export function downloadText(filename, content, mime = 'text/yaml') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/** 把任意字符串清洗成安全的文件名片段（去掉非法字符）。 */
export function safeFilename(name, fallback = 'script') {
  const cleaned = String(name ?? '')
    .replace(/[\\/:*?"<>|]+/g, '_')
    .trim()
  return cleaned || fallback
}
