<script setup>
import { computed, inject } from 'vue'

const props = defineProps({
  chapterText: {
    type: String,
    required: true
  }
})

// 接收父组件广播过来的高亮区间
const activeSourceRange = inject('activeSourceRange')

// 将整坨文本按换行符切分成数组（完全复刻后端的切分逻辑，确保段落号 100% 对齐）
const parsedParagraphs = computed(() => {
  if (!props.chapterText) return []
  return props.chapterText
    .split('\n')
    .map(p => p.trim())
    .filter(p => p.length > 0) // 过滤空行
})

// 核心计算逻辑：判断当前段落是否在悬停区间内
const isHighlighted = (index) => {
  const range = activeSourceRange?.value
  if (!range || range.length !== 2) return false
  
  // 智能提取数字：无论后端传的是 'p_2' 还是 'c1_p2'，我们只抠出最后的纯数字
  const extractNum = (str) => parseInt(str.split('_').pop().replace(/\D/g, ''))
  
  const startNum = extractNum(range[0])
  const endNum = extractNum(range[1])
  const currentNum = index + 1 // 索引从0开始，段落号从1开始
  
  return currentNum >= startNum && currentNum <= endNum
}
</script>

<template>
  <div class="preview-panel novel-panel">
    <div class="panel-header">小说原文</div>
    <div class="panel-content">
      <div v-if="parsedParagraphs.length > 0" class="text-content novel-text">
        <p 
          v-for="(para, index) in parsedParagraphs" 
          :key="index"
          :id="`novel-p-${index + 1}`" 
          class="novel-paragraph"
          :class="{ 'is-highlighted': isHighlighted(index) }"
        >
          {{ para }}
        </p>
      </div>
      <div v-else class="empty-state">等待在左侧章节树选中章节...</div>
    </div>
  </div>
</template>

<style scoped>
/* 原有的面板样式保持不变 */
.preview-panel {
  flex: 1; 
  display: flex;
  flex-direction: column;
  background: #fff;
}
.novel-panel {
  border-right: 1px solid #e0e0e0; 
}
.panel-header {
  padding: 0.75rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 600;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}
.panel-content {
  padding: 1.25rem;
  overflow-y: auto;
}
.text-content {
  line-height: 1.8;
}
.empty-state {
  color: #bfbfbf;
  font-style: italic;
  font-size: 0.82rem;
}

/* 🌟 新增的段落与呼吸灯高亮样式 */
.novel-paragraph {
  margin: 0 0 0.4rem 0; /* 将底侧外边距缩小到 0.4rem (约 6px) */
  word-break: break-word;
  transition: all 0.3s ease; 
  padding: 2px 10px; /* 缩小上下内边距，保持左右内边距不变 */
  border-radius: 4px;
  border-left: 4px solid transparent; 
}

/* 高亮触发时的样式 */
.is-highlighted {
  background-color: rgba(255, 193, 7, 0.15); /* 淡淡的暖黄色护眼高亮 */
  border-left: 4px solid #ffc107; /* 左侧加一条明显的提示线 */
  transform: translateX(4px); /* 微微向右浮动，增加立体感 */
}
</style>