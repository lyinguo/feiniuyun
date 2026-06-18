<script setup>
// 引入格式化工具
import { formatMemoryLines } from '@/utils/scriptParsers'

const props = defineProps({
  displayData: {
    type: Object,
    required: true
  }
})
</script>

<template>
    <div class="ai-card new-memory-card">
      <div class="ai-card__header">
        🆕 本章节新长期记忆 (代码层提取自动打标)
        <span class="advanced-badge">Metadata Extract</span>
      </div>
      
      <div class="ai-card__body new-memory-container">
        
        <div class="memory-meta-box character-meta">
          <div class="meta-box__title">👤 抓取新出场/变化人物</div>
          <div class="meta-box__content">
            <template v-if="formatMemoryLines(displayData.newCharacters).length > 0">
              <div 
                v-for="(line, idx) in formatMemoryLines(displayData.newCharacters)" 
                :key="idx" 
                class="meta-capsule-item"
              >
                <span class="meta-bullet-icon">✦</span>
                <p class="meta-capsule-text">{{ line }}</p>
              </div>
            </template>
            <div v-else-if="displayData.isStreaming" class="meta-status-loading">
              <span class="pulse-dot"></span> 正在实时分析人物设定变化...
            </div>
            <div v-if="displayData.isStreaming && formatMemoryLines(displayData.newCharacters).length > 0" class="meta-status-loading mini-loading">
              <span class="pulse-dot"></span> AI 正在持续抓取并生成新设定...
            </div>
            <div v-else class="empty-state">本章未提取到新出场人物...</div>
          </div>
        </div>

        <div class="memory-meta-box location-meta">
          <div class="meta-box__title">📍 抓取新登场重要场所</div>
          <div class="meta-box__content">
            <template v-if="formatMemoryLines(displayData.newLocations).length > 0">
              <div 
                v-for="(line, idx) in formatMemoryLines(displayData.newLocations)" 
                :key="idx" 
                class="meta-capsule-item"
              >
                <span class="meta-bullet-icon">✦</span>
                <p class="meta-capsule-text">{{ line }}</p>
              </div>
            </template>
            <div v-else-if="displayData.isStreaming && formatMemoryLines(displayData.newLocations).length === 0" class="meta-status-loading">
              <span class="pulse-dot blue"></span> 正在实时提取地理场所空间...
            </div>
            <div v-else class="empty-state">本章未提取到新核心场所...</div>
            <div v-if="displayData.isStreaming && formatMemoryLines(displayData.newLocations).length > 0" class="meta-status-loading mini-loading">
              <span class="pulse-dot blue"></span> AI 正在实时扩展地理勘查树...
            </div>
          </div>
        </div>

      </div>
    </div>
  </template>
<style>
/* 引入并让它对所有子组件生效 */
@import './ai-dashboard-theme.css';
</style>