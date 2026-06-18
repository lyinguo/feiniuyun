export const parseStreamingJson = (rawText) => {
  if (!rawText) return []
  let text = rawText.replace(/^```json\s*|\s*```$/g, '').trim()
  // 2. 如果已经完全吐完，直接全量解析
  if (text.endsWith(']')) {
    try { return JSON.parse(text) } catch (e) {}
  }
  const scenes = []
  // 3. 核心：通过 {"scene" 关键字把文本流切成若干个场景块
  const sceneChunks = text.split(/\{\s*"scene"\s*:/)
  for (let i = 1; i < sceneChunks.length; i++) {
    let chunk = '{"scene":' + sceneChunks[i].trim()
    
    // 如果不是最后一个块，说明已经完全闭合，直接解析
    if (i < sceneChunks.length - 1) {
      try {
        if (!chunk.endsWith('}')) {
          const lastCloseGroup = chunk.lastIndexOf('}')
          if (lastCloseGroup !== -1) chunk = chunk.substring(0, lastCloseGroup + 1)
        }
        scenes.push(JSON.parse(chunk))
        continue
      } catch (e) {}
    }
    // 4. 重点突破：对最后一个正在打字的残缺场景进行“碎字抢救”
    const sceneTitleMatch = chunk.match(/"scene"\s*:\s*"([^"]*)"/)
    const summaryMatch = chunk.match(/"summary"\s*:\s*"([^"]*)"/)
    const currentScene = {
      scene: sceneTitleMatch ? sceneTitleMatch[1] : '正在构思新场景...',
      summary: summaryMatch ? summaryMatch[1] : '',
      elements: []
    }
    // 抠出里面已经打完字的完整元素块 (支持同角色无限重复登场)
    const elementRegex = /\{\s*"character"\s*:\s*"([^"]*)"\s*,\s*"action"\s*:\s*"([^"]*)"\s*,\s*"dialogue"\s*:\s*"([^"]*)"\s*\}/g
    let elemMatch
    let lastIndex = 0
    while ((elemMatch = elementRegex.exec(chunk)) !== null) {
      currentScene.elements.push({
        character: elemMatch[1],
        action: elemMatch[2],
        dialogue: elemMatch[3]
      })
      lastIndex = elementRegex.lastIndex
    }
    // 5. 闪光点：如果最后一条 element 还在流式变长（还没打出大括号），也把它抠出来蹦字
    const remainingPart = chunk.substring(lastIndex)
    const activeElementMatch = remainingPart.match(/"character"\s*:\s*"([^"]*)"/)
    if (activeElementMatch) {
      const actionPart = remainingPart.match(/"action"\s*:\s*"([^"]*)"?/)
      const dialoguePart = remainingPart.match(/"dialogue"\s*:\s*"([^"]*)"?/)
      currentScene.elements.push({
        character: activeElementMatch[1],
        action: actionPart ? actionPart[1] : '',
        dialogue: dialoguePart ? dialoguePart[1] : '...'
      })
    }
    scenes.push(currentScene)
  }
  return scenes
}
export const getCharacterStyle = (name) => {
  if (!name) return {}
  // 1. 简单的字符串 Hash 算法，算出名字的特征数字
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  // 2. 利用特征数字映射出 360 度的色相值 (Hue)
  // 固定饱和度 (75%-85%) 和明度 (93%-96%)，确保生成的颜色全都是非常柔和、高级的马卡龙浅色系
  const hue = Math.abs(hash) % 360
  return {
    // 动态生成专属的台词舱背景渐变
    background: `linear-gradient(135deg, hsl(${hue}, 85%, 96%) 0%, hsl(${hue}, 75%, 98%) 100%)`,
    // 动态生成专属的台词舱边框
    borderColor: `hsl(${hue}, 50%, 88%)`,
    // 动态生成左侧大括号引用符的颜色（颜色稍微加深，形成视觉提神）
    quoteColor: `hsl(${hue}, 80%, 45%)`,
    // 动态生成角色小标签的背景与边框
    tagBg: `hsl(${hue}, 85%, 94%)`,
    tagBorder: `hsl(${hue}, 50%, 84%)`,
    tagText: `hsl(${hue}, 85%, 25%)`
  }
}
// 🌟 新增：将 ChromaDB 的原生 RAG 文本智能拆解、按实体名字归类聚合（Group By）
// 🌟 升级版：彻底清洗任意多层章节嵌套的中括号标签，只保留纯净的实体名字
export const parseAndGroupMemory = (rawText) => {
  if (!rawText) return []
  
  const groups = {}
  const lines = rawText.split('\n').map(l => l.trim()).filter(l => l.length > 0)
  
  lines.forEach(line => {
    // 1. 【核心大清洗】：用全局正则 /\[[^\]]+\]/g 把这一行里所有的 "[第X章]" 统统抹平炸掉！
    // 顺便把前面的 "- " 抹掉
    let cleanLine = line.replace(/^-\s*/, '').replace(/\[[^\]]+\]/g, '').trim()
    
    // 2. 抓取冒号前面的名字部分，并把中英文括号及里面的内容切掉（例如切掉“（705室内部补充）”）
    const nameMatch = cleanLine.match(/^([^：（]+)(?:[（\(][^）\)]+[）\)])?\s*：/)
    
    if (nameMatch) {
      // 3. 拿到最纯净的实体名字，比如由 "- [第三章] [第三章] 案发现场..." 完美洗涤出的 "案发现场"
      const entityName = nameMatch[1].trim() 
      
      // 拿到冒号后面的具体细节描述
      const detail = cleanLine.substring(cleanLine.indexOf('：') + 1).trim()
      
      if (!groups[entityName]) {
        groups[entityName] = []
      }
      if (!groups[entityName].includes(detail)) {
        groups[entityName].push(detail)
      }
    } else {
      if (!groups['其他记录']) groups['其他记录'] = []
      groups['Other_Notes'].push(cleanLine)
    }
  })
  
  return Object.keys(groups).map(name => ({
    name: name,
    details: groups[name]
  }))
}
export const formatMemoryLines = (rawText) => {
  if (!rawText) return []
  return rawText
    .split('\n') // 按换行符切开
    .map(line => line.trim().replace(/^-\s*/, '')) // 清理前后空格，并抹掉开头的 "- "
    .filter(line => line.length > 0) // 过滤掉空行
}
// 🌟 3. 新增：将原始 JSON 文本流，实时优雅降级转存为纯文本(TXT)格式的工具
export const convertToTxtFormat = (rawText) => {
  const scenes = parseStreamingJson(rawText)
  if (!scenes || scenes.length === 0) return rawText || '暂无内容...'
  return scenes.map(s => {
    const header = `【场景】${s.scene}\n${s.summary ? `大纲概要：${s.summary}\n` : ''}`
    const body = s.elements.map(e => {
      const actionStr = e.action ? `[动作: ${e.action}]` : ''
      const dialogueStr = e.dialogue ? `：“${e.dialogue}”` : ''
      return `${e.character}${actionStr}${dialogueStr}`
    }).join('\n')
    return `${header}${body}`
  }).join('\n\n====================\n\n')
}
// 🌟 4. 核心补全：符合 YAML 规范的流式数据实时格式化工具（无需装包）
export const convertToYamlFormat = (rawText) => {
  const scenes = parseStreamingJson(rawText)
  if (!scenes || scenes.length === 0) return '# 暂无规范剧本数据...'
  // 内部工具函数：转义字符串，防止内容中包含单引号、换行等导致 YAML 语法崩溃
  const escapeYamlStr = (str) => {
    if (!str) return '""'
    // 如果包含特殊字符，用双引号包裹并转义，否则直接返回
    return /[:#[\]{},&*!|>-]|\n/.test(str) ? JSON.stringify(str) : str
  }
  // 按照 YAML 标准的缩进结构（2空格体系）进行拼装
  return scenes.map(s => {
    let yamlChunk = `- scene: ${escapeYamlStr(s.scene)}\n`
    if (s.summary) {
      yamlChunk += `  summary: ${escapeYamlStr(s.summary)}\n`
    }
    
    if (s.elements && s.elements.length > 0) {
      yamlChunk += `  elements:\n`
      const elementsYaml = s.elements.map(e => {
        let elemStr = `    - character: ${escapeYamlStr(e.character)}\n`
        if (e.action)   elemStr += `      action: ${escapeYamlStr(e.action)}\n`
        if (e.dialogue) elemStr += `      dialogue: ${escapeYamlStr(e.dialogue)}`
        return elemStr
      }).join('\n')
      yamlChunk += elementsYaml
    }
    return yamlChunk
  }).join('\n')
}