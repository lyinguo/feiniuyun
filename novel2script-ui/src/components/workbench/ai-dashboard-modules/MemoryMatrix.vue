<script setup>
import { ref } from 'vue'
// 引入你抽离出来的纯数据处理函数 (如果在 utils 里的话)
import { parseAndGroupMemory } from '@/utils/scriptParsers'

// 接收父组件传来的数据
const props = defineProps({
  displayData: {
    type: Object,
    required: true
  }
})

const activeEntityKey = ref(null) // 点击锁定的 key
const hoverEntityKey = ref(null)  // 🌟 新增：鼠标悬停的 key
const popoverStyle = ref({ top: '0px', left: '0px' })
// 🌟 精准物理坐标与边界拦截引擎
const calculatePopoverPosition = (event, isClick = false) => {
  const rect = event.currentTarget.getBoundingClientRect()
  const popoverWidth = 420 // 我们在 CSS 里定义的弹窗固定宽度
  const padding = 12       // 距离浏览器最右侧的安全呼吸间距
  // 计算最理想的左对齐坐标
  let targetLeft = rect.left + window.scrollX
  // 🚨【黄金边界拦截】：如果当前卡片太靠右，理想坐标 + 弹窗宽度超出了浏览器视口总宽度...
  if (rect.left + popoverWidth > window.innerWidth - padding) {
    // 降维打击：直接切换为“右对齐模式”，让弹窗的右边和卡片的右边对齐！
    targetLeft = rect.right + window.scrollX - popoverWidth
    // 如果左边又被挤到屏幕外面去了（比如屏幕太小），强制将其钉在安全边界
    if (targetLeft < padding) targetLeft = padding
  }
  popoverStyle.value = {
    top: `${rect.bottom + window.scrollY + 6}px`,
    left: `${targetLeft}px`
  }
}
// 🌟 1. 鼠标移入事件
const handleMouseEnter = (event, key) => {
  if (activeEntityKey.value) return // 如果已经有卡片被点击锁定了，悬停不生效
  hoverEntityKey.value = key
  calculatePopoverPosition(event)
}
// 🌟 2. 鼠标移出事件
const handleMouseLeave = () => {
  hoverEntityKey.value = null
}
// 🌟 3. 点击锁定事件
const toggleEntityPopover = (event, key) => {
  if (activeEntityKey.value === key) {
    activeEntityKey.value = null
    return
  }
  // 点击时，先清除悬停状态，全力转为锁定状态
  hoverEntityKey.value = null
  activeEntityKey.value = key
  calculatePopoverPosition(event, true)
}
// 🌟 4. 空白点击收起维持不变
if (typeof window !== 'undefined') {
  window.addEventListener('click', (e) => {
    if (!e.target.closest('.entity-block-card') && !e.target.closest('.entity-tooltip-popover')) {
      activeEntityKey.value = null
    }
  })
}
</script>

<template>
    <!-- 🧠 长期记忆卡片：全新重构的独立状态状态锁看板 -->
    <div class="ai-card memory-card">
      <div class="ai-card__header">
        <span>🧠 长期记忆 (ChromaDB 历史 RAG 召回看板)</span>
        <span class="advanced-badge font-orange">RAG Matrix</span>
      </div>
      
      <div class="ai-card__body memory-matrix-container">
        
        <!-- 【左翼】：历史人物设定矩阵 -->
        <div class="memory-meta-box character-matrix">
          <div class="matrix-box__title">💡 历史人物设定：</div>
          <div class="matrix-box__content">
            <template v-if="displayData.retrievedCharacters">
              <div class="matrix-grid">
                <div 
                  v-for="(item, idx) in parseAndGroupMemory(displayData.retrievedCharacters)" 
                  :key="idx" 
                  class="entity-block-card"
                  :class="{ 'is-active-card': activeEntityKey === `char-${idx}` }"
                  @mouseenter="handleMouseEnter($event, `char-${idx}`)"
                  @mouseleave="handleMouseLeave"
                  @click.stop="toggleEntityPopover($event, `char-${idx}`)"
                >
                  <span class="entity-name-text">👤 {{ item.name }}</span>
                  <span class="entity-count-badge">{{ item.details.length }} 条</span>
                  
                  <!-- 🌟【物理穿梭舱】：通过 Teleport 把弹窗强行挂到 Body 下，彻底免疫外层隐藏 Bug -->
                  <Teleport to="body">
                    <div 
                      v-if="activeEntityKey === `char-${idx}` || hoverEntityKey === `char-${idx}`"
                      class="entity-tooltip-popover"
                      :style="popoverStyle"
                      @click.stop
                    >
                      <div class="tooltip-header">📌 关于 [{{ item.name }}] 的历史 RAG 召回记录：</div>
                      <div class="tooltip-body-scroll">
                        <div v-for="(detail, dIdx) in item.details" :key="dIdx" class="tooltip-detail-item">
                          <span class="tooltip-bullet">►</span> {{ detail }}
                        </div>
                      </div>
                    </div>
                  </Teleport>

                </div>
              </div>
            </template>
            <div v-else-if="displayData.isStreaming" class="empty-state">等待引擎调取向量库人物数据...</div>
            <div v-else class="empty-state">该章节暂无历史人物记忆...</div>
          </div>
        </div>

        <!-- 【右翼】：历史地理场所矩阵 -->
        <div class="memory-meta-box location-meta">
          <div class="matrix-box__title">💡 历史地理场所：</div>
          <div class="matrix-box__content">
            <template v-if="displayData.retrievedLocations">
              <div class="matrix-grid">
                <div 
                  v-for="(item, idx) in parseAndGroupMemory(displayData.retrievedLocations)" 
                  :key="idx" 
                  class="entity-block-card location-theme"
                  :class="{ 'is-active-card-loc': activeEntityKey === `loc-${idx}` }"
                  @mouseenter="handleMouseEnter($event, `loc-${idx}`)"
                  @mouseleave="handleMouseLeave"
                  @click.stop="toggleEntityPopover($event, `loc-${idx}`)"
                >
                  <span class="entity-name-text">📍 {{ item.name }}</span>
                  <span class="entity-count-badge">{{ item.details.length }} 条</span>
                  
                  <!-- 🌟【物理穿梭舱】：地理场所弹窗传送 -->
                  <Teleport to="body">
                    <div 
                      v-if="activeEntityKey === `loc-${idx}` || hoverEntityKey === `loc-${idx}`"
                      class="entity-tooltip-popover"
                      :style="popoverStyle"
                      @click.stop
                    >
                      <div class="tooltip-header">📌 关于 [{{ item.name }}] 的历史勘查记录：</div>
                      <div class="tooltip-body-scroll">
                        <div v-for="(detail, dIdx) in item.details" :key="dIdx" class="tooltip-detail-item">
                          <span class="tooltip-bullet">►</span> {{ detail }}
                        </div>
                      </div>
                    </div>
                  </Teleport>

                </div>
              </div>
            </template>
            <div v-else-if="displayData.isStreaming" class="empty-state">等待引擎调取向量库地理数据...</div>
            <div v-else class="empty-state">该章节暂无历史场所记忆...</div>
          </div>
        </div>

      </div>
    </div>
</template>

<style>
/* 引入并让它对所有子组件生效 */
@import './ai-dashboard-theme.css';
</style>