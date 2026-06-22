<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useAgentStore } from '@/stores/agentStore'
import { useNovelStore } from '@/stores/novelStore'

const props = defineProps({
  title: String,
  icon: String,
  agentKey: String // 'background', 'character', 'relationship', 'casting', 'critic', 'continuity_critic', 'summarizer'
})

const agentStore = useAgentStore() 
const novelStore = useNovelStore()
const scrollContainer = ref(null)
// 🌟 1. 增加一个标志位：记录用户是否正在向上翻看
const isUserScrollingUp = ref(false)

// 🌟 2. 滚动事件监听器：智能判断用户意图
const handleScroll = (e) => {
  const el = e.target
  // 计算距离底部的距离 (scrollHeight = 内容总高度, scrollTop = 卷去的高度, clientHeight = 视口高度)
  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  
  // 如果距离底部超过 50px，说明用户手动往上滑了，开启锁定；如果滚回到底部，解除锁定
  isUserScrollingUp.value = distanceToBottom > 50
}
// 1. 获取原始基础流状态数据
const rawAgentData = computed(() => agentStore.currentAgentStreams[props.agentKey])

const agentData = computed(() => {
  return rawAgentData.value || { status: 'idle', reasoning: '', content: '' }
})

/**
 * 🚀 终极黑科技：流式 JSON 实时修补算法
 * 原理：通过栈机制扫描残缺的字符串，自动补齐缺失的引号、中括号和大括号，
 * 让由于流式传输截断的 JSON 瞬间变成合法的 JS 对象，从而驱动 Vue 实时渲染。
 */
function parseIncompleteJson(jsonString) {
  let str = jsonString.trim()
  if (!str) return null

  try {
    // 如果已经是完整合法的 JSON，直接解析
    return JSON.parse(str)
  } catch (e) {
    // 1. 补全未闭合的字符串双引号 (排除被转义的 \")
    const quoteCount = (str.match(/(?<!\\)"/g) || []).length
    if (quoteCount % 2 !== 0) {
      str += '"'
    }

    // 2. 清理尾部多余的逗号或冒号，防止解析崩溃
    str = str.replace(/[,:]\s*$/, '')

    // 3. 用栈结构追踪缺失的括号
    let stack = []
    let inString = false
    let escapeNext = false

    for (let i = 0; i < str.length; i++) {
      let char = str[i]
      if (escapeNext) { escapeNext = false; continue }
      if (char === '\\') { escapeNext = true; continue }
      if (char === '"') { inString = !inString; continue }

      if (!inString) {
        if (char === '{') stack.push('}')
        else if (char === '[') stack.push(']')
        else if (char === '}' || char === ']') stack.pop()
      }
    }

    // 4. 从栈顶依次弹出缺失的闭合符号
    while (stack.length > 0) {
      str += stack.pop()
    }

    // 5. 再次尝试解析修补后的字符串
    try {
      return JSON.parse(str)
    } catch (err) {
      // 若当前帧数据极度异常无法修复，返回 null，界面短暂保持上一帧状态
      return null
    }
  }
}

const parsedStructuredContent = ref(null)

watch(
  () => agentData.value.content,
  (newContent) => {
    if (!newContent) {
      parsedStructuredContent.value = null
      return
    }
    const result = parseIncompleteJson(newContent)
    // 🌟 核心防御：只有当修复算法成功返回有效对象时，才更新 UI
    // 如果 result 为 null，什么都不做！保留屏幕上上一帧的合法卡片，避免 DOM 崩溃
    if (result) {
      parsedStructuredContent.value = result
    }
  },
  { immediate: true }
)

// 3. 自动平滑滚动控制
watch(
  () => [rawAgentData.value?.content, rawAgentData.value?.reasoning], // 如果是编剧文件，这里是 writerData
  async () => {
    if (!scrollContainer.value) return
    await nextTick()
    
    // 🔥 核心改动：只有当用户没有往上翻时，才自动滚动到底部
    if (!isUserScrollingUp.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  },
  { deep: true }
)
</script>

<template>
  <div class="agent-panel" :class="{ 'is-active': agentData.status === 'processing' }">
    <div class="agent-header">
      <span class="agent-title">{{ icon }} {{ title }}</span>
      <span class="agent-status" :class="agentData.status">
        {{ agentData.status === 'processing' ? '思考中...' : 
           agentData.status === 'done' ? '完成' : '待命' }}
      </span>
    </div>
    
    <div class="agent-body" ref="scrollContainer" @scroll="handleScroll">
      <div v-if="agentData.reasoning" class="reasoning-box">
        <div class="reasoning-label">💡 深度思考过程：</div>
        <div class="reasoning-text">{{ agentData.reasoning }}</div>
      </div>
      
      <div class="content-box">
        <div v-if="!agentData.content" class="empty-text">等待数据输入...</div>

        <div v-else-if="parsedStructuredContent" class="structured-view">
          
          <div v-if="agentKey === 'background'">
            <div v-if="parsedStructuredContent.new_settings?.length" class="sub-section">
              <div class="section-tag">🆕 新增设定</div>
              <div v-for="(s, idx) in parsedStructuredContent.new_settings" :key="idx" class="data-item">
                <strong>📍 {{ s.name || '读取中...' }}</strong> 
                <span class="badge" v-if="s.category">{{ s.category }}</span>
                <p v-if="s.visual_identity">🎬 视觉: {{ s.visual_identity }}</p>
              </div>
            </div>
            <div v-if="parsedStructuredContent.canon_facts?.length" class="sub-section">
              <div class="section-tag">📌 铁律事实</div>
              <div v-for="(f, idx) in parsedStructuredContent.canon_facts" :key="idx" class="fact-card">
                {{ f.fact || '...' }} 
                <span class="conf" v-if="f.confidence" :class="f.confidence">{{ f.confidence }}</span>
              </div>
            </div>
          </div>

          <div v-if="agentKey === 'character'">
            <div class="sub-section">
              <div class="section-tag">👥 提取到的人物</div>
              <div v-if="parsedStructuredContent.new_characters || parsedStructuredContent.updated_characters">
                <div v-for="(c, idx) in [...(parsedStructuredContent.new_characters || []), ...(parsedStructuredContent.updated_characters || [])]" :key="idx" class="data-item">
                  <strong>👤 {{ c.name || '提取姓名中...' }}</strong>
                  <div class="traits" v-if="c.personality?.length">
                    <span v-for="(p, i) in c.personality" :key="i" class="mini-tag">{{ p }}</span>
                  </div>
                  <p v-if="c.appearance">🎭 外貌: {{ c.appearance }}</p>
                </div>
              </div>
            </div>
          </div>

          <div v-if="agentKey === 'relationship'">
            <div class="sub-section">
              <div class="section-tag">⛓️ 情感与冲突链</div>
              <div v-if="parsedStructuredContent.relationships?.length">
                <div v-for="(r, idx) in parsedStructuredContent.relationships" :key="idx" class="data-item">
                  <strong>{{ r.source_name || '?' }} ➡️ {{ r.target_name || '?' }}</strong>
                  <div class="rel-text" v-if="r.relation">关系: {{ r.relation }}</div>
                  <small v-if="r.evidence">📖 依据: {{ r.evidence }}</small>
                </div>
              </div>
            </div>
          </div>

          <div v-if="agentKey === 'casting'">
            <div v-if="parsedStructuredContent.choices?.length" class="sub-section">
              <div v-for="(c, idx) in parsedStructuredContent.choices" :key="idx" class="data-item">
                <strong>🎭 {{ c.character_name || '读取中...' }}</strong> 
                <span v-if="c.screen_type" class="text-blue"> -> {{ c.screen_type }}</span>
                <div class="makeup" v-if="c.costume_or_makeup?.length">🎨 妆造: {{ c.costume_or_makeup.join(', ') }}</div>
              </div>
            </div>
          </div>

          <div v-if="agentKey === 'critic' || agentKey === 'continuity_critic'">
            <div v-if="'passed' in parsedStructuredContent" class="review-status" :class="{ 'pass': parsedStructuredContent.passed === true, 'fail': parsedStructuredContent.passed === false }">
              审查结果: {{ parsedStructuredContent.passed ? '✅ PASSED' : '❌ REJECTED' }}
            </div>
            <div v-if="parsedStructuredContent.error_msg" class="error-msg-box">
              🎯 修复指令: {{ parsedStructuredContent.error_msg }}
            </div>
            <div v-if="parsedStructuredContent.issues?.length" class="sub-section">
              <div v-for="(issue, idx) in parsedStructuredContent.issues" :key="idx" class="issue-card" :class="issue.severity">
                <strong>[{{ issue.severity || 'warning' }}]</strong> {{ issue.issue || '记录中...' }}
                <div class="instruct" v-if="issue.revision_instruction">👉 {{ issue.revision_instruction }}</div>
              </div>
            </div>
          </div>

          <div v-if="agentKey === 'summarizer'">
            <div v-if="parsedStructuredContent.rolling_summary" class="summary-doc">
              <div class="section-tag">📦 本章精简纪要</div>
              <p class="summary-p">{{ parsedStructuredContent.rolling_summary }}<span v-if="agentData.status === 'processing'" class="typing-cursor">_</span></p>
            </div>
            <div v-if="parsedStructuredContent.open_threads?.length" class="sub-section">
              <div class="section-tag">🔮 遗留未解伏笔</div>
              <ul>
                <li v-for="(t, idx) in parsedStructuredContent.open_threads" :key="idx">{{ t }}</li>
              </ul>
            </div>
          </div>

        </div>

        <div v-else class="fallback-view">
          <div class="streaming-loading-dots">数据流接入中，准备构建UI...</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 保持所有原有精美样式 */
.agent-panel {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  height: 150px;      /* 设定一个你觉得合适的固定高度 */
  flex-shrink: 0;     /* 防止在父容器里被 Flexbox 强制挤压变形 */
}
.agent-panel.is-active {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.12);
}
.agent-header {
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  font-weight: 600;
}
.agent-status.processing { color: #2563eb; animation: blink 1.5s infinite; }
.agent-status.done { color: #16a34a; }
.agent-status.idle { color: #64748b; }

.agent-body {
  padding: 12px;
  flex: 1;
  overflow-y: auto;
  font-size: 0.825rem;
  line-height: 1.6;
}

.reasoning-box {
  background: #fdf6ec;
  border-left: 3px solid #e6a23c;
  padding: 8px 10px;
  margin-bottom: 12px;
  border-radius: 0 6px 6px 0;
}
.reasoning-label { font-weight: bold; color: #b78135; margin-bottom: 2px; font-size: 0.75rem; }
.reasoning-text { color: #666; font-style: italic; white-space: pre-wrap; }

.sub-section { margin-bottom: 14px; }
.section-tag {
  font-size: 0.75rem;
  font-weight: bold;
  color: #475569;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  margin-bottom: 6px;
}
.data-item {
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 6px;
}
.char-tag {
  display: inline-block;
  background: #eff6ff;
  color: #1e40af;
  padding: 2px 8px;
  border-radius: 20px;
  margin-right: 4px;
  margin-bottom: 4px;
  font-weight: 500;
}
.mini-tag {
  font-size: 0.7rem;
  background: #f0fdf4;
  color: #166534;
  padding: 1px 4px;
  border-radius: 4px;
  margin-right: 4px;
}
.fact-card {
  background: #fff1f0;
  border-left: 3px solid #f5222d;
  padding: 6px 8px;
  margin-bottom: 4px;
}
.badge { font-size: 0.7rem; background: #e0f2fe; color: #0369a1; padding: 1px 4px; border-radius: 4px; float: right; }

.review-status { padding: 6px; border-radius: 6px; font-weight: bold; text-align: center; margin-bottom: 8px; }
.review-status.pass { background: #f0fdf4; color: #15803d; }
.review-status.fail { background: #fef2f2; color: #b91c1c; }
.error-msg-box { background: #fff7ed; border: 1px dashed #ea580c; color: #c2410c; padding: 8px; border-radius: 6px; margin-bottom: 10px; }

.issue-card { padding: 6px; border-radius: 4px; margin-bottom: 4px; font-size: 0.75rem; }
.issue-card.blocker { background: #fef2f2; border-left: 3px solid #dc2626; }
.issue-card.warning { background: #fffbeb; border-left: 3px solid #d97706; }

.summary-p { background: #fafafa; border: 1px solid #e2e8f0; padding: 10px; border-radius: 6px; text-indent: 2em; color: #334155; }
.empty-text { text-align: center; color: #94a3b8; padding: 20px 0; }
.streaming-loading-dots { font-size: 0.75rem; color: #3b82f6; text-align: center; padding: 20px 0; animation: pulse 2s infinite; }

.typing-cursor {
  display: inline-block;
  width: 6px;
  height: 12px;
  background-color: #334155;
  margin-left: 2px;
  animation: blink 1s step-end infinite;
}

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
</style>