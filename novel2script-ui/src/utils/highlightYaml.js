/**
 * 轻量 YAML 语法高亮。
 *
 * 设计原则：先对原文做 HTML 转义，再仅插入我们自己的 <span> 标签，
 * 因此用于 v-html 渲染不会有 XSS 注入风险。
 * 仅覆盖常见情形（键、字符串、数字、布尔、注释、列表符），
 * 足以让后端输出的剧本 YAML 更易读；不追求完整 YAML 规范。
 */

function escapeHtml(input) {
  return String(input).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function highlightValue(raw) {
  const trimmed = raw.trim()
  if (!trimmed) return escapeHtml(raw)
  let cls = 'hl-string'
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) cls = 'hl-number'
  else if (/^(true|false|null|~|yes|no|on|off)$/i.test(trimmed)) cls = 'hl-bool'
  return `<span class="${cls}">${escapeHtml(raw)}</span>`
}

// 找到行内注释（前面有空白的 #）起始下标，找不到返回 -1
function findInlineComment(line) {
  const match = line.match(/\s#/)
  return match ? match.index : -1
}

function highlightLine(line) {
  // 整行注释
  const full = line.match(/^(\s*)(#.*)$/)
  if (full) {
    return escapeHtml(full[1]) + `<span class="hl-comment">${escapeHtml(full[2])}</span>`
  }

  let body = line
  let comment = ''
  const cIdx = findInlineComment(body)
  if (cIdx >= 0) {
    comment = body.slice(cIdx)
    body = body.slice(0, cIdx)
  }

  const m = body.match(/^(\s*)(- )?([\s\S]*)$/)
  const indent = escapeHtml(m[1])
  const dash = m[2] ? '<span class="hl-dash">- </span>' : ''
  const rest = m[3]

  let inner
  const kv = rest.match(/^("[^"]*"|'[^']*'|[^:#]+):(\s*)([\s\S]*)$/)
  if (kv) {
    inner =
      `<span class="hl-key">${escapeHtml(kv[1])}</span>:` +
      escapeHtml(kv[2]) +
      (kv[3] ? highlightValue(kv[3]) : '')
  } else {
    inner = highlightValue(rest)
  }

  const commentHtml = comment ? `<span class="hl-comment">${escapeHtml(comment)}</span>` : ''
  return indent + dash + inner + commentHtml
}

export function highlightYaml(text) {
  if (!text) return ''
  return text.split('\n').map(highlightLine).join('\n')
}
