<script setup>
import { ref } from 'vue'
import { useNovelStore } from '@/stores/novelStore'
import { parseEpub } from '@/api/backend'

const store = useNovelStore()
const fileInput = ref(null)

// 触发隐藏的原生 file input
function pickFile() {
  fileInput.value?.click()
}

// 选择文件后：调用后端解析 EPUB，结果规范化后写入 store
async function handleFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return

  store.isLoading = true
  store.errorMessage = ''
  try {
    // resp: { status, message, data: <book_metadata>, folder_name }
    const resp = await parseEpub(file)
    store.setNovelFromMetadata(resp.data, resp.folder_name)
  } catch (err) {
    store.errorMessage = err.message ?? '上传失败'
  } finally {
    store.isLoading = false
    event.target.value = '' // 允许重复选择同一文件
  }
}

// —— 仅用于脱离后端预览界面布局，联调时可删除 ——
// 注意：演示数据没有真实文件，点「生成剧本」会因 get-chapter 找不到文件而报错。
function loadDemoData() {
  store.setNovelFromMetadata(
    {
      book_title: '示例小说',
      total_char_count: 128000,
      total_estimated_tokens: 153600,
      chapters: [
        {
          logical_index: 1,
          original_title: '第一章 风起',
          total_char_count: 4200,
          is_chunked: false,
          file_path: './chapter_001_001.txt',
        },
        {
          logical_index: 2,
          original_title: '第二章 暗涌',
          total_char_count: 95000,
          is_chunked: true,
          chunks: [
            { sub_index: 1, file_path: './chapter_002_001.txt' },
            { sub_index: 2, file_path: './chapter_002_002.txt' },
          ],
        },
      ],
    },
    'demo-book',
  )
}
</script>

<template>
  <section class="uploader">
    <button class="btn btn--primary" :disabled="store.isLoading" @click="pickFile">
      {{ store.isLoading ? '解析中…' : '上传小说' }}
    </button>
    <!-- 隐藏的原生文件选择框；后端 parse-epub 仅处理 EPUB -->
    <input
      ref="fileInput"
      type="file"
      accept=".epub"
      class="uploader__input"
      @change="handleFileChange"
    />

    <!-- 书名 / 字数统计信息 -->
    <div class="uploader__info">
      <template v-if="store.bookInfo.title">
        <span class="uploader__title">《{{ store.bookInfo.title }}》</span>
        <span class="uploader__meta">
          共 {{ store.bookInfo.chapterCount }} 章 ·
          {{ store.bookInfo.totalCharCount.toLocaleString() }} 字
        </span>
      </template>
      <span v-else class="uploader__placeholder">尚未上传小说</span>
    </div>

    <button class="uploader__demo" @click="loadDemoData">载入演示数据</button>

    <p v-if="store.errorMessage" class="uploader__error">{{ store.errorMessage }}</p>
  </section>
</template>

<style scoped>
.uploader {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.uploader__input {
  display: none;
}
.uploader__info {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}
.uploader__title {
  font-weight: 600;
}
.uploader__meta {
  font-size: 0.8rem;
  color: var(--color-text-muted);
}
.uploader__placeholder {
  font-size: 0.85rem;
  color: var(--color-text-muted);
}
.uploader__demo {
  font-size: 0.8rem;
  color: var(--color-text-muted);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}
.uploader__error {
  margin-left: auto;
  font-size: 0.8rem;
  color: var(--color-danger);
}
</style>
