(function () {
  "use strict";

  const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

  const sampleNovel = `《雨灯档案》

第一章 雨夜的信

雨夜里，旧城派出所的灯坏了一半。林越推开档案室的门，看见阿岚正站在窗边，手里攥着一封没有署名的信。

阿岚低声说：“他们没有把案子结掉，只是把名字藏起来了。”

林越拿起信，纸面被雨水洇开，只剩下“南桥仓库”和“名单”两个词。他想起三年前失踪的父亲，胸口像被旧钉子顶住。

走廊传来脚步声。值班警员老周提醒：“今晚别去南桥，那边有人盯着。”

林越却把信塞进外套：“如果名单是真的，我必须去。”

第二章 南桥仓库

南桥仓库靠着河，铁门被风吹得来回撞。林越和阿岚穿过积水，发现门口有新鲜轮胎印。

阿岚问道：“你确定要进去？这可能是陷阱。”

林越没有回答。他在仓库深处看见一排旧货柜，其中一个货柜上刻着父亲的警号。货柜里没有尸体，只有一台还亮着红灯的录音机。

录音机里传出男人的声音：“别相信档案，真正的名单在北站。”

灯忽然灭了。黑暗中有人喊：“把录音机留下！”

第三章 北站清晨

清晨的北站广场空得像一张白纸。林越把录音机交给老周，老周的手却抖了一下。

阿岚看见老周袖口沾着仓库里的红漆，立刻拦住林越：“他昨晚去过南桥。”

老周沉默很久，终于说道：“你父亲不是失踪，是被自己人送走的。名单会害死所有还活着的人。”

远处第一班车进站，广播声盖住了雨声。林越望向检票口，一个戴黑帽的女人递来一张车票。

女人说：“想知道真相，就上车。”`;

  const FORMAT_PROMPTS = {
    web_series: `【短剧形态改编指引】
- 开场 15 秒内必须抛出强钩子或冲突，先抓人再交代背景。
- 节奏快、场景短，每场只服务一个明确目标，避免大段铺垫。
- 每集结尾留下强悬念或反转，制造追看欲。
- 对白口语化、信息密度高，尽量把冲突和心理外化为动作。`,
    film: `【电影形态改编指引】
- 按三幕结构组织：建置—对抗—结局，关注主角整体弧光。
- 重视视听语言与场面调度，允许更长的情绪铺陈与留白。
- 主题统一，关键转折点（激励事件、中点、低谷）清晰可辨。
- 对白精炼，多用潜台词和视觉信息表达，少用直白旁白。`,
    stage: `【舞台剧形态改编指引】
- 时空相对集中，减少频繁转场，善用同一场景内人物的进出场。
- 以对白和人物正面交锋驱动剧情，强调台词的戏剧张力。
- 用舞台调度、灯光、道具提示替代影视镜头语言。
- 可适度保留独白/旁白，注意现场表演的连贯与节奏。`,
    audio_drama: `【广播剧形态改编指引】
- 一切信息靠声音传达：对白、旁白、音效与环境声。
- 每个角色声音特征鲜明，不能依赖视觉区分人物。
- 用音效和台词交代地点、动作与时间，减少纯视觉描写。
- 适当用旁白衔接场景，控制信息节奏，便于聆听理解。`
  };

  const els = {
    novelInput: document.querySelector("#novelInput"),
    fileInput: document.querySelector("#fileInput"),
    sampleBtn: document.querySelector("#sampleBtn"),
    clearBtn: document.querySelector("#clearBtn"),
    convertBtn: document.querySelector("#convertBtn"),
    copyBtn: document.querySelector("#copyBtn"),
    downloadBtn: document.querySelector("#downloadBtn"),
    userIdInput: document.querySelector("#userIdInput"),
    threadIdInput: document.querySelector("#threadIdInput"),
    titleInput: document.querySelector("#titleInput"),
    toneInput: document.querySelector("#toneInput"),
    densityRange: document.querySelector("#densityRange"),
    densityValue: document.querySelector("#densityValue"),
    episodeSize: document.querySelector("#episodeSize"),
    shortWindow: document.querySelector("#shortWindow"),
    chapterCount: document.querySelector("#chapterCount"),
    charCount: document.querySelector("#charCount"),
    statusText: document.querySelector("#statusText"),
    warningList: document.querySelector("#warningList"),
    chapterList: document.querySelector("#chapterList"),
    memoryList: document.querySelector("#memoryList"),
    scenePreview: document.querySelector("#scenePreview"),
    yamlOutput: document.querySelector("#yamlOutput"),
    statsLine: document.querySelector("#statsLine"),
    chapterSelect: document.querySelector("#chapterSelect"),
    formatPromptInput: document.querySelector("#formatPromptInput"),
    resetPromptBtn: document.querySelector("#resetPromptBtn")
  };

  let latestResult = null;
  let parseTimer = null;
  let abortController = null;
  let currentEpubFolder = "";
  let isEpubMode = false;      
  let epubChapterCount = 0;
  const promptState = { ...FORMAT_PROMPTS };
  let currentFormat = "web_series";

  function init() {
    els.novelInput.addEventListener("input", queueParse);
    els.userIdInput.addEventListener("input", queueParse);
    els.threadIdInput.addEventListener("input", queueParse);
    els.sampleBtn.addEventListener("click", loadSample);
    els.clearBtn.addEventListener("click", clearAll);
    els.convertBtn.addEventListener("click", convert);
    els.copyBtn.addEventListener("click", copyYaml);
    els.downloadBtn.addEventListener("click", downloadYaml);
    els.fileInput.addEventListener("change", handleFile);
    els.densityRange.addEventListener("input", () => {
      els.densityValue.textContent = els.densityRange.value;
    });
    els.chapterSelect.addEventListener("change", loadEpubChapter);
    initFormatPrompt();
    checkBackend();
    queueParse();
  }

  function initFormatPrompt() {
    const checked = document.querySelector("[name='targetFormat']:checked");
    currentFormat = checked ? checked.value : "web_series";
    els.formatPromptInput.value = promptState[currentFormat];
    document.querySelectorAll("[name='targetFormat']").forEach((radio) => {
      radio.addEventListener("change", onFormatChange);
    });
    els.formatPromptInput.addEventListener("input", () => {
      promptState[currentFormat] = els.formatPromptInput.value;
    });
    els.resetPromptBtn.addEventListener("click", resetCurrentPrompt);
  }

  function onFormatChange() {
    promptState[currentFormat] = els.formatPromptInput.value;
    const checked = document.querySelector("[name='targetFormat']:checked");
    currentFormat = checked ? checked.value : currentFormat;
    els.formatPromptInput.value = promptState[currentFormat];
  }

  function resetCurrentPrompt() {
    promptState[currentFormat] = FORMAT_PROMPTS[currentFormat];
    els.formatPromptInput.value = promptState[currentFormat];
  }

  async function loadEpubChapter(event) {
    const fileName = event.target.value;
    if (!fileName) return; // 如果选了默认的"--选择--"就没反应

    els.novelInput.value = "正在加载章节内容，请稍候...";
    
    try {
      const response = await fetch(`${API_BASE}/api/get-chapter?folder=${encodeURIComponent(currentEpubFolder)}&file_name=${encodeURIComponent(fileName)}`);
      const json = await response.json();
      
      if (json.status === 'success') {
        els.novelInput.value = json.content; // 把请求到的文本塞进输入框！
      } else {
        els.novelInput.value = "加载失败：" + json.message;
      }
    } catch (err) {
      els.novelInput.value = "请求失败：" + err.message;
    }
  }

  async function checkBackend() {
    try {
      const response = await fetch(`${API_BASE}/api/health`);
      const payload = await response.json();
      const configured = Boolean(payload.data && payload.data.llm_configured);
      setStatus(configured ? "后端已连接，大模型已配置。" : "后端已连接，但还没有配置 LLM_API_KEY。");
    } catch (_) {
      setStatus("未连接 Python 后端：请运行 uvicorn app.main:app --reload --port 8000。");
    }
  }

  function queueParse() {
    window.clearTimeout(parseTimer);
    parseTimer = window.setTimeout(updateInputPreview, 120);
  }

  function updateInputPreview() {
    if (isEpubMode) {
      const warnings = [];
      if (epubChapterCount < 3) warnings.push("题目要求 3 章以上；当前章节数不足。");
      if (!els.userIdInput.value.trim()) warnings.push("User ID 不能为空。");
      if (!els.threadIdInput.value.trim()) warnings.push("Thread ID 不能为空。");

      els.convertBtn.disabled = warnings.length > 0 || epubChapterCount === 0;
      renderWarnings(warnings);
      return; // 🌟 拦截成功，直接退出，不执行下面的拆分代码
    }
    const text = els.novelInput.value;
    const chapters = splitChapters(text);
    els.chapterCount.textContent = String(chapters.length);
    els.charCount.textContent = String(text.trim().length);

    const warnings = [];
    if (text.trim() && chapters.length < 3) warnings.push("题目要求 3 章以上；当前章节数不足。");
    if (!els.userIdInput.value.trim()) warnings.push("User ID 不能为空。");
    if (!els.threadIdInput.value.trim()) warnings.push("Thread ID 不能为空。");

    els.convertBtn.disabled = warnings.length > 0 || !text.trim();
    renderChapterList(chapters);
    renderWarnings(warnings);
  }

  async function handleFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    // --- 新增：如果是 EPUB 文件，走后端接口 ---
    if (file.name.endsWith('.epub')) {
        els.novelInput.value = "正在上传并让后端解析 EPUB 文件，请稍候...";
        
        const formData = new FormData();
        formData.append('file', file);

        fetch('/api/parse-epub', { 
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            console.log("后端返回的数据:", data); 

            if (data.status === 'success') {
                const info = data.data; 
                
                // 🌟 保存当前书本文件夹名字，供等下请求章节用
                currentEpubFolder = data.folder_name; 
                isEpubMode = true;
                epubChapterCount = info.chapters ? info.chapters.length : 0;
                // 统计信息展示
                els.novelInput.value = 
                    `✅ EPUB 处理成功！\n\n` +
                    `📖 书名：《${info.book_title || '未知书名'}》\n` +
                    `📑 总章节：${info.chapters ? info.chapters.length : 0} 章\n` +
                    `🔤 总字数：约 ${info.total_char_count || 0} 字\n` +
                    `🤖 估算消耗：${info.total_estimated_tokens || 0} Tokens\n\n` +
                    `👉 请在右上角下拉菜单中选择你要预览的具体章节！`;
                
                const mappedChapters = (info.chapters || []).map(ch => ({
                    title: ch.original_title, 
                    text: { length: ch.total_char_count || ch.char_count || 0 },  
                    auto: false 
                }));

                // 🌟 生成下拉菜单的内容，并让它显示出来
                const optionsHtml = mappedChapters.map(ch => {
                    // 我们把 file_path (如 "./chapter_001.txt") 存在 value 里
                    // 我们把标题存在 option 标签中间显示
                    const originalChapter = info.chapters.find(c => c.original_title === ch.title);
                    return `<option value="${originalChapter.file_path}">${ch.title}</option>`;
                }).join("");
                
                els.chapterSelect.innerHTML = '<option value="">-- 选择章节预览 --</option>' + optionsHtml;
                els.chapterSelect.style.display = 'inline-block';

                els.chapterCount.textContent = String(mappedChapters.length);
                els.charCount.textContent = String(info.total_char_count || 0);

                renderChapterList(mappedChapters);

                const warnings = [];
                if (mappedChapters.length > 0 && mappedChapters.length < 3) warnings.push("题目要求 3 章以上；当前章节数不足。");
                if (!els.userIdInput.value.trim()) warnings.push("User ID 不能为空。");
                if (!els.threadIdInput.value.trim()) warnings.push("Thread ID 不能为空。");
                
                els.convertBtn.disabled = warnings.length > 0 || mappedChapters.length === 0;
                renderWarnings(warnings);
            } else {
                els.novelInput.value = "❌ 解析失败：" + data.message;
            }
        })
        .catch(err => {
            els.novelInput.value = "❌ 网络请求失败：" + err.message;
        });
        
        return; // 结束，不往下走纯文本解析逻辑了
    }
    setStatus(`正在读取 ${file.name} ...`);
    try {
      const result = await readNovelFile(file);
      els.novelInput.value = result.text;
      isEpubMode = false;
      els.chapterSelect.style.display = 'none';

      setStatus(`已导入小说：${file.name}${result.encoding ? `（${result.encoding}）` : ""}。`);
      queueParse();
    } catch (error) {
      setStatus(`文件读取失败：${error.message}`);
    } finally {
      event.target.value = "";
    }
  }

  async function readNovelFile(file) {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    if (!bytes.length) return { text: "", encoding: "empty" };

    const utf8 = tryDecode(bytes, "utf-8", true);
    if (utf8.ok) return { text: stripBom(utf8.text), encoding: "utf-8" };

    const fallbackEncodings = ["gb18030", "gbk", "big5"];
    let best = null;
    fallbackEncodings.forEach((encoding) => {
      const decoded = tryDecode(bytes, encoding, false);
      if (!decoded.ok) return;
      const score = scoreDecodedText(decoded.text);
      if (!best || score > best.score) {
        best = { text: decoded.text, encoding, score };
      }
    });

    if (best) return { text: stripBom(best.text), encoding: best.encoding };

    const fallback = new TextDecoder("utf-8").decode(bytes);
    return { text: stripBom(fallback), encoding: "utf-8 fallback" };
  }

  function tryDecode(bytes, encoding, fatal) {
    try {
      return {
        ok: true,
        text: new TextDecoder(encoding, { fatal }).decode(bytes)
      };
    } catch (_) {
      return { ok: false, text: "" };
    }
  }

  function scoreDecodedText(text) {
    const sample = text.slice(0, 5000);
    const chinese = (sample.match(/[\u4e00-\u9fff]/g) || []).length;
    const replacement = (sample.match(/\uFFFD/g) || []).length;
    const controls = (sample.match(/[\x00-\x08\x0E-\x1F]/g) || []).length;
    return chinese * 3 - replacement * 20 - controls * 10 + Math.min(sample.length, 500);
  }

  function stripBom(text) {
    return String(text || "").replace(/^\uFEFF/, "");
  }

  function loadSample() {
    els.novelInput.value = sampleNovel;
    els.titleInput.value = "雨灯档案";
    queueParse();
    setStatus("已加载三章示例小说。");
  }

  function clearAll() {
    if (abortController) abortController.abort();
    els.novelInput.value = "";
    els.yamlOutput.value = "";
    latestResult = null;
    els.copyBtn.disabled = true;
    els.downloadBtn.disabled = true;
    renderMemory(null);
    renderScenes(null);

    isEpubMode = false;
    epubChapterCount = 0;
    els.chapterSelect.style.display = 'none'; 
    els.chapterSelect.innerHTML = '<option value="">-- 选择章节预览 --</option>';

    Object.assign(promptState, FORMAT_PROMPTS);
    els.formatPromptInput.value = promptState[currentFormat];

    queueParse();
    setStatus("已清空工作台。");
  }

  async function convert() {
    const payload = buildPayload();
    abortController = new AbortController();
    els.convertBtn.disabled = true;
    setStatus("正在调用 Python 后端和真实大模型，请稍候 ...");

    try {
      const response = await fetch(`${API_BASE}/api/scripts/convert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: abortController.signal
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || body.message || `HTTP ${response.status}`);
      }

      latestResult = body.data;
      els.yamlOutput.value = latestResult.yaml || "";
      els.copyBtn.disabled = !latestResult.yaml;
      els.downloadBtn.disabled = !latestResult.yaml;
      renderWarnings(latestResult.diagnostics || []);
      renderMemory(latestResult);
      renderScenes(latestResult);
      renderStats(latestResult.stats || {});
      setStatus("后端已生成剧本 YAML。");
    } catch (error) {
      if (error.name === "AbortError") {
        setStatus("请求已取消。");
      } else {
        setStatus(`生成失败：${error.message}`);
        renderWarnings([error.message]);
      }
    } finally {
      abortController = null;
      queueParse();
    }
  }

  function buildPayload() {
    const target = document.querySelector("[name='targetFormat']:checked");
    return {
      user_id: els.userIdInput.value.trim(),
      thread_id: els.threadIdInput.value.trim(),
      novel_text: els.novelInput.value,
      title: els.titleInput.value.trim() || null,
      target_format: target ? target.value : "web_series",
      adaptation_tone: els.toneInput.value.trim() || "现实感、强冲突、可拍摄",
      scene_density: Number(els.densityRange.value),
      chapters_per_episode: Number(els.episodeSize.value),
      short_term_window: Number(els.shortWindow.value)
    };
  }

  async function copyYaml() {
    if (!els.yamlOutput.value) return;
    await navigator.clipboard.writeText(els.yamlOutput.value);
    setStatus("YAML 已复制到剪贴板。");
  }

  function downloadYaml() {
    if (!els.yamlOutput.value) return;
    const blob = new Blob([els.yamlOutput.value], { type: "text/yaml;charset=utf-8" });
    const link = document.createElement("a");
    const title = (els.titleInput.value.trim() || "novel_script").replace(/[\\/:*?"<>|]/g, "_");
    link.href = URL.createObjectURL(blob);
    link.download = `${title}.script.yaml`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    setStatus("YAML 文件已下载。");
  }

  function splitChapters(rawText) {
    const text = String(rawText || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
    if (!text) return [];
    const lines = text.split("\n");
    const markers = [];
    const pattern = /^\s*(?:#{1,3}\s*)?((?:第\s*[零〇一二两三四五六七八九十百千万\d]+\s*[章节回幕卷部](?:\s*[^\n]{0,40})?)|(?:chapter\s+\d+(?:[:：\s-][^\n]{0,40})?))\s*$/i;

    lines.forEach((line, index) => {
      const trimmed = line.trim();
      if (trimmed.length <= 80 && pattern.test(trimmed)) {
        markers.push({ line: index, title: trimmed.replace(/^#{1,3}\s*/, "") });
      }
    });

    if (markers.length >= 2) {
      return markers.map((marker, index) => {
        const endLine = markers[index + 1] ? markers[index + 1].line : lines.length;
        return {
          index: index + 1,
          title: marker.title,
          text: lines.slice(marker.line + 1, endLine).join("\n").trim(),
          auto: false
        };
      }).filter((chapter) => chapter.text);
    }

    const size = 3500;
    const chunks = [];
    for (let offset = 0; offset < text.length; offset += size) {
      chunks.push({
        index: chunks.length + 1,
        title: `自动分章 ${chunks.length + 1}`,
        text: text.slice(offset, offset + size),
        auto: true
      });
    }
    return chunks;
  }

  function renderChapterList(chapters) {
    if (!chapters.length) {
      els.chapterList.innerHTML = '<li class="empty">导入小说后显示章节识别结果。</li>';
      return;
    }
    els.chapterList.innerHTML = chapters.slice(0, 80).map((chapter) => {
      const tag = chapter.auto ? '<span class="tag">自动</span>' : "";
      return `<li><span>${escapeHtml(chapter.title)}</span>${tag}<small>${chapter.text.length} 字</small></li>`;
    }).join("");
  }

  function renderWarnings(warnings) {
    if (!warnings || !warnings.length) {
      els.warningList.innerHTML = '<li class="ok">当前没有阻断性提醒。</li>';
      return;
    }
    els.warningList.innerHTML = warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("");
  }

  function renderMemory(result) {
    if (!result || !result.memory_snapshot) {
      els.memoryList.innerHTML = '<li class="empty">生成后显示该 user/thread 的短期记忆与长期故事圣经。</li>';
      return;
    }

    const memory = result.memory_snapshot;
    const recent = (memory.short_term.recent_chapters || []).map((item) => `${item.chapter_id} ${item.title}`).join(" / ");
    const longTerm = memory.long_term || {};
    els.memoryList.innerHTML = [
      `<li><strong>短期窗口</strong><span>${escapeHtml(recent || "无")}</span></li>`,
      `<li><strong>长期事实</strong><span>${(longTerm.canon_facts || []).length} 条</span></li>`,
      `<li><strong>人物/地点</strong><span>${Object.keys(longTerm.characters || {}).length} 人物 · ${Object.keys(longTerm.locations || {}).length} 地点</span></li>`,
      `<li><strong>悬念线程</strong><span>${(longTerm.unresolved_threads || []).length} 条</span></li>`
    ].join("");
  }

  function renderScenes(result) {
    const episodes = result && result.script && result.script.script && result.script.script.episodes;
    if (!episodes || !episodes.length) {
      els.scenePreview.innerHTML = '<li class="empty">后端生成后显示前若干场戏预览。</li>';
      return;
    }

    const scenes = episodes.flatMap((episode) => episode.acts || []).flatMap((act) => act.scenes || []).slice(0, 80);
    els.scenePreview.innerHTML = scenes.map((scene) => {
      return `<li>
        <strong>${escapeHtml(scene.scene_id)} · ${escapeHtml(scene.title)}</strong>
        <span>${escapeHtml(scene.slugline.location)} / ${escapeHtml(scene.slugline.time)} / ${escapeHtml(scene.purpose)}</span>
        <small>人物：${escapeHtml((scene.characters || []).join(", ") || "待定")}</small>
      </li>`;
    }).join("");
  }

  function renderStats(stats) {
    els.statsLine.textContent = `${stats.scene_count || 0} 场戏 · ${stats.character_count || 0} 人物 · ${stats.location_count || 0} 地点 · ${stats.model_call_count || 0} 次模型调用`;
  }

  function setStatus(message) {
    els.statusText.textContent = message;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  init();
})();
