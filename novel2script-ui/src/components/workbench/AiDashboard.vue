<script setup>
import { ref, watch, nextTick } from 'vue'
import { 
  parseStreamingJson, 
  getCharacterStyle, 
  formatMemoryLines,
  parseAndGroupMemory, 
  convertToTxtFormat, 
  convertToYamlFormat 
} from '@/utils/scriptParsers'
// 导入你的四大模块
import MemoryMatrix from './ai-dashboard-modules/MemoryMatrix.vue'
import StoryProgress from './ai-dashboard-modules/StoryProgress.vue'
import ScriptViewer from './ai-dashboard-modules/ScriptViewer.vue'
import MemoryExtractor from './ai-dashboard-modules/MemoryExtractor.vue'

// 1. 规范接收最新的五宫格数据模型（包含老前情提要 oldStoryProgress 与新概述 newStoryProgress）
const props = defineProps({
  displayData: {
    type: Object,
    required: true,
    default: () => ({
      isStreaming: false,
      script: '',
      reasoningText: '',
      oldStoryProgress: '', 
      newStoryProgress: '', 
      retrievedCharacters: '',
      retrievedLocations: '',
      newCharacters: '',
      newLocations: ''
    })
  },
  errorMessage: {
    type: String,
    default: ''
  }
})
</script>

<template>
  <div class="ai-dashboard">
    <div v-if="errorMessage" class="error-banner">
      🚨 引擎报错: {{ errorMessage }}
    </div>
    <MemoryMatrix :displayData="displayData" />
    <StoryProgress :displayData="displayData" />
    <ScriptViewer :displayData="displayData" />
    <MemoryExtractor :displayData="displayData" />
  </div>
</template>

<style>
@import './ai-dashboard-modules/ai-dashboard-theme.css';
</style>