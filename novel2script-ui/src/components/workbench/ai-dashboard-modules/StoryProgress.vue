<script setup>
const props = defineProps({
  displayData: {
    type: Object,
    required: true
  }
})
</script>

<template>
    <div class="story-progress-container">
      
      <div class="ai-card progress-card input-progress">
        <div class="ai-card__header">
          <span>📖 继承前情提要 <small class="header-sub-tag">Context Input</small></span>
          <span class="pulse-indicator-dot static-gray"></span>
        </div>
        <div class="ai-card__body progress-card-body">
          <div v-if="displayData.oldStoryProgress" class="blueprint-card-inner">
            <div class="blueprint-stamp">LEGACY</div>
            <p class="blueprint-paragraph">{{ displayData.oldStoryProgress }}</p>
          </div>
          <div v-else-if="displayData.isStreaming" class="progress-status-loading">
            <div class="spinner-mini"></div>
            <span>正在精准调取并缝合前情线索...</span>
          </div>
          <div v-else class="empty-state-modern">按针未检测到任何输入提要...</div>
        </div>
      </div>

      <div class="ai-card progress-card output-progress">
        <div class="ai-card__header">
          <span>📝 本章剧本新概述 <small class="header-sub-tag text-green">LLM Output</small></span>
          <span v-if="displayData.isStreaming" class="pulse-indicator-dot breathing-green"></span>
        </div>
        <div class="ai-card__body progress-card-body">
          <div v-if="displayData.newStoryProgress" class="neon-ledger-inner">
            <div class="ledger-glow-bar"></div>
            <p class="ledger-paragraph">{{ displayData.newStoryProgress }}</p>
          </div>
          <div v-else-if="displayData.isStreaming" class="progress-status-loading">
            <div class="shimmer-line"></div>
            <span class="text-italic-light">剧本正文高频解构中，正在实时提炼本章新备忘录...</span>
          </div>
          <div v-else class="empty-state-modern">待本章正文跑完后自动打标生成...</div>
        </div>
      </div>

    </div>
  </template>

<style>
/* 引入并让它对所有子组件生效 */
@import './ai-dashboard-theme.css';
</style>