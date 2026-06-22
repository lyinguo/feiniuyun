// src/services/agentSseService.js

// 声明一个全局的控制器，用于随时强行掐断网络请求
let controller = null

/**
 * 启动多智能体流式请求
 * @param {Object} payload - 发送给后端的参数 (例如 folderName / project_path)
 * @param {Function} onMessageCallback - 接收到完整 JSON 后的回调函数
 */
export async function startAgentStream(payload, onMessageCallback) {
  // 1. 初始化熔断器
  controller = new AbortController()

  try {
    const sseUrl = 'http://localhost:8000/api/scripts/convert-project-stream'
    const requestBody = {
      user_id: payload.user_id || "default_user", 
      thread_id: payload.thread_id || "default_thread",
      project_path: payload.project_path 
    }
    // console.log("🚀 发送给后端的数据包:", requestBody)
    // 2. 发起 Fetch 请求 (注意替换为你新版 FastAPI 的真实路由)
    const response = await fetch(sseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // 注意：根据你之前后端的 ConvertProjectRequest 调整这里的字段名
      body: JSON.stringify(requestBody),
      signal: controller.signal // 绑定熔断器
    })

    if (!response.ok) {
      throw new Error(`HTTP 状态码异常: ${response.status}`)
    }

    // 3. 获取可读数据流
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = '' // 🌟 核心：用于拼接被网络切断的半截 JSON

    // 4. 开始抽水循环
    while (true) {
      const { done, value } = await reader.read()
      
      // 后端完全跑完，关闭流
      if (done) break

      // 将二进制数据解码为文本，拼接到缓存池中
      buffer += decoder.decode(value, { stream: true })
      
      // SSE 协议标准：每条消息以两个换行符 \n\n 结束
      const lines = buffer.split('\n\n')
      
      // 🌟 核心防断层逻辑：
      // split 切割后，数组的最后一项可能是不完整的半截字符串。
      // 我们把它 pop 出来，重新塞回 buffer 里，留到下一轮接收时继续拼接！
      buffer = lines.pop()

      // 遍历所有完整的消息行
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          // 剔除 'data: ' 前缀，拿到纯 JSON 字符串
          const jsonStr = line.substring(6).trim()
          if (!jsonStr) continue

          try {
            // 解析为 JSON 对象
            const data = JSON.parse(jsonStr)
            
            // 🌟 完美移交：把干净的数据扔给 useAgentStream 里的分发器
            onMessageCallback(data)
            
          } catch (e) {
            console.error('🚨 [SSE 解析错误] 无法解析的残片:', jsonStr, e)
          }
        }
      }
    }
  } catch (err) {
    // 5. 异常处理分支
    if (err.name === 'AbortError') {
      console.log('🛑 [网络层] 用户手动触发熔断，已强行终止新引擎流式请求。')
    } else {
      console.error('💥 [网络层] SSE 流异常崩溃:', err)
      // 如果真的断网了，手动模拟一个 error 事件发给上层，让 UI 显示报错红条
      onMessageCallback({ 
        event: 'error', 
        message: '网络连接异常，请检查后端服务: ' + err.message 
      })
    }
  } finally {
    controller = null
  }
}

/**
 * 手动停止当前的流式请求
 */
export async function closeAgentStream() {
  if (controller) {
    controller.abort() // 发出终止信号
    controller = null
  }
}