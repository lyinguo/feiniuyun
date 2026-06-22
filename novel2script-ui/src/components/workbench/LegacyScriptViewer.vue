<script setup>
import { computed } from 'vue'
import { useAgentStore } from '@/stores/agentStore'
import AgentAnalysisPanel from './agents/AgentAnalysisPanel.vue'
import ScreenwriterPanel from './agents/ScreenwriterPanel.vue'

const agentStore = useAgentStore()
const errorMessage = computed(() => agentStore.errorMessage || '')
</script>

<template>
  <div class="langgraph-dashboard preview-panel">
    <div v-if="errorMessage" class="error-banner">
      🚨 引擎异常: {{ errorMessage }}
    </div>

    <div class="dashboard-layout">
      
      <div class="workflow-column col-left">
        <div class="column-header">🧠 前置分析引擎</div>
        <div class="column-body scroll-container">
          <AgentAnalysisPanel title="环境与背景" icon="🌍" agentKey="background" />
          <AgentAnalysisPanel title="人物性格" icon="👤" agentKey="character" />
          <AgentAnalysisPanel title="阵营与关系" icon="🔗" agentKey="relationship" />
          <AgentAnalysisPanel title="选角与造型" icon="🎭" agentKey="casting" />
        </div>
      </div>

      <div class="flow-indicator horizontal">
        <svg viewBox="0 0 24 24" class="animated-arrow-right"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
      </div>

      <div class="workflow-column col-mid">
        <ScreenwriterPanel class="full-height-panel" />
      </div>

      <div class="flow-indicator horizontal">
        <svg viewBox="0 0 24 24" class="animated-arrow-right"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
      </div>

      <div class="workflow-column col-right">
        <div class="column-header">🔍 质量审查与归档</div>
        <div class="column-body scroll-container">
          
          <AgentAnalysisPanel title="剧本评审 (Critic)" icon="🧐" agentKey="critic" />
          
          <div class="flow-indicator vertical">
            <svg viewBox="0 0 24 24" class="animated-arrow-down"><line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline></svg>
          </div>
          
          <AgentAnalysisPanel title="连贯性审查" icon="📏" agentKey="continuity_critic" />
          
          <div class="flow-indicator vertical">
            <svg viewBox="0 0 24 24" class="animated-arrow-down"><line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline></svg>
          </div>
          
          <AgentAnalysisPanel title="故事总结与归档" icon="📦" agentKey="summarizer" />
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* =========== 基础容器 =========== */
.preview-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f1f5f9; /* 替换为更高级的浅灰蓝底色 */
  border-left: 1px solid #e2e8f0;
  overflow: hidden;
}

.error-banner {
  background: #fef2f2;
  color: #dc2626;
  padding: 10px 16px;
  font-size: 0.85rem;
  font-weight: bold;
  border-bottom: 1px solid #fecaca;
}

/* =========== 宏观网格布局 =========== */
.dashboard-layout {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  padding: 16px; /* 给四周留出呼吸感 */
  gap: 8px; /* 栏与箭头之间的间距 */
  overflow: hidden;
}

/* =========== 列布局 (独立滚动控制) =========== */
.workflow-column {
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-radius: 10px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  border: 1px solid #e2e8f0;
  overflow: hidden; /* 防止内部溢出圆角 */
}

/* 灵活分配宽度 */
.col-left { flex: 0 0 24%; }
.col-mid { flex: 1; min-width: 0; } /* 占据剩余全部核心空间 */
.col-right { flex: 0 0 24%; }

/* 吸顶标题栏 */
.column-header {
  padding: 12px 16px;
  font-size: 0.9rem;
  font-weight: bold;
  color: #334155;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

/* 内部滚动区 */
.column-body {
  flex: 1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px; /* 卡片之间的间距 */
  overflow-y: auto;
}

/* 特殊处理主笔面板，让它撑满中栏 */
.full-height-panel {
  height: 100%;
  border: none !important; /* 移除内部自带的边框，使用外层圆角 */
}

/* =========== 动态箭头样式 =========== */
.flow-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8; /* 科技灰 */
}

.flow-indicator.horizontal {
  width: 24px;
}

.flow-indicator.vertical {
  height: 20px;
  margin: -4px 0; /* 让上下卡片稍微紧凑一点 */
}

/* SVG 基础设置 */
svg {
  width: 24px;
  height: 24px;
  stroke: currentColor;
  stroke-width: 2;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* 水平右移动画 */
.animated-arrow-right {
  animation: slideRight 1.5s infinite ease-in-out;
}

/* 垂直下移动画 */
.animated-arrow-down {
  animation: slideDown 1.5s infinite ease-in-out;
}

@keyframes slideRight {
  0% { transform: translateX(-4px); opacity: 0.4; }
  50% { transform: translateX(4px); opacity: 1; }
  100% { transform: translateX(-4px); opacity: 0.4; }
}

@keyframes slideDown {
  0% { transform: translateY(-3px); opacity: 0.4; }
  50% { transform: translateY(3px); opacity: 1; }
  100% { transform: translateY(-3px); opacity: 0.4; }
}

/* 滚动条美化 (可选) */
.scroll-container::-webkit-scrollbar {
  width: 6px;
}
.scroll-container::-webkit-scrollbar-track {
  background: transparent;
}
.scroll-container::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 10px;
}
</style>