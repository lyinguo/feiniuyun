# 剧本 YAML Schema

本文定义 AI 小说转剧本工具输出的 YAML 结构。Schema 面向“小说章节 -> 剧本初稿 -> 作者继续打磨”的流程，优先保证可编辑、可追溯、可分批生成。

## 顶层结构

```yaml
schema_version: "1.0"
project: {}
source: {}
memory: {}
characters: []
locations: []
script: {}
tooling: {}
review_notes: {}
```

## 字段定义

### schema_version

类型：`string`

当前版本为 `"1.0"`。后续字段调整时通过版本号保持兼容。

### project

```yaml
project:
  title: "作品名"
  source_type: "novel"
  target_format: "web_series"
  adaptation_tone: "现实感、强冲突、可拍摄"
  language: "zh-CN"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 改编项目名。 |
| `source_type` | string | 是 | 原始文本类型，当前固定为 `novel`。 |
| `target_format` | string | 是 | 目标形态，如 `web_series`、`film`、`stage`、`audio_drama`。 |
| `adaptation_tone` | string | 是 | 改编语气和创作约束。 |
| `language` | string | 是 | 输出语言，默认 `zh-CN`。 |

设计原因：同一部小说可能改成短剧、电影或广播剧，顶层必须记录目标形态，否则后续场景密度、对白比例和视觉说明无法稳定解释。

### source

```yaml
source:
  chapter_count: 3
  character_count: 12000
  detected_chaptering: "heading"
  minimum_requirement_met: true
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `chapter_count` | number | 是 | 识别出的章节数，题目要求应大于等于 3。 |
| `character_count` | number | 是 | 原始文本字符数，用于估算规模。 |
| `detected_chaptering` | string | 是 | `heading` 表示按章节标题识别，`auto_by_length` 表示自动分段。 |
| `minimum_requirement_met` | boolean | 是 | 是否满足“3 章以上”的输入要求。 |

设计原因：长篇小说处理时，输入规模和分章方式会直接影响质量。把识别结果写入 YAML，便于作者发现自动分章是否需要人工修正。

### memory

```yaml
memory:
  short_term:
    window_chapters: 2
    final_active_characters: ["char_001"]
    final_recent_chapters: []
  long_term:
    logline: "一句话故事概览"
    canon_facts: []
    character_arcs: []
    unresolved_threads: []
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `short_term.window_chapters` | number | 是 | 生成时保留最近几章作为局部上下文。 |
| `short_term.final_active_characters` | string[] | 是 | 末尾短期窗口里的活跃人物 ID。 |
| `short_term.final_recent_chapters` | object[] | 是 | 最近章节摘要，用于继续生成下一批章节。 |
| `long_term.logline` | string | 是 | 全局故事概览。 |
| `long_term.canon_facts` | object[] | 是 | 已确认的章节事实，不能在后续随意改写。 |
| `long_term.character_arcs` | object[] | 是 | 人物弧线状态和待明确问题。 |
| `long_term.unresolved_threads` | object[] | 是 | 未解决线索、悬念和伏笔。 |

设计原因：长小说不能一次性全部塞进模型上下文。短期记忆解决“最近两三章发生了什么”，长期记忆解决“全书设定、人物、伏笔不能乱”。两者分开，后续可以按章节批处理，也能在断点续写时恢复上下文。

### characters

```yaml
characters:
  - id: "char_001"
    name: "林越"
    role: "主角候选"
    first_seen: "ch001"
    appearances: ["ch001", "ch002"]
    traits: ["待打磨"]
    goals: ["待确认"]
    relationships: []
    key_scenes: ["ch001_s001"]
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 人物唯一 ID。 |
| `name` | string | 是 | 原文人物名。 |
| `role` | string | 是 | 主角候选、配角候选等。 |
| `first_seen` | string | 是 | 首次出现章节。 |
| `appearances` | string[] | 是 | 出现过的章节。 |
| `traits` | string[] | 是 | 性格或表演关键词。 |
| `goals` | string[] | 是 | 人物目标。 |
| `relationships` | object[] | 是 | 与其他人物的关系。 |
| `key_scenes` | string[] | 是 | 关键场景 ID。 |

设计原因：剧本中场景只引用人物 ID，不反复复制人物设定。这样可以避免长篇改编里人物名漂移，也方便作者集中修改人物小传。

### locations

```yaml
locations:
  - id: "loc_001"
    name: "南桥仓库"
    first_seen: "ch002"
    visual_identity: "南桥仓库需要在美术设定中明确时代、材质和空间关系。"
    key_scenes: []
```

设计原因：地点单独建表后，场景可以稳定引用地点名称，也方便后续做美术、置景、预算和拍摄计划。

### script

```yaml
script:
  format: "episode_act_scene"
  episodes:
    - episode_id: "ep_001"
      title: "第1集：雨夜的信"
      source_chapters: [1, 2, 3]
      dramatic_goal: "本集戏剧目标"
      acts:
        - act_id: "ep_001_act_001"
          title: "第一章 雨夜的信"
          source_chapter: 1
          dramatic_function: "建立人物、目标与当前处境"
          chapter_summary: "章节摘要"
          carried_memory: {}
          scenes: []
```

`scene` 结构：

```yaml
scene_id: "ch001_s001"
source_ref:
  chapter_index: 1
  chapter_title: "第一章 雨夜的信"
  sentence_start: 1
  sentence_end: 5
slugline:
  location: "档案室"
  time: "night"
  space: "interior"
title: "第1场：雨夜里的信"
purpose: "建立场景处境并抛出行动目标"
conflict: "人物必须冒险调查"
characters: ["char_001", "char_002"]
action:
  - "林越推开档案室的门。"
dialogue:
  - speaker: "char_002"
    line: "他们没有把案子结掉，只是把名字藏起来了。"
    subtext: "追问信息"
visual_notes:
  - "保留原文中的天气、光影或触觉细节作为镜头气氛。"
continuity:
  setup: []
  payoff: []
  short_term_context: []
revision_note: "保留原文对白并转为剧本对白，建议下一轮强化潜台词。"
```

设计原因：

1. `episode -> act -> scene` 符合剧本开发的常用层级，短剧和长剧都能扩展。
2. `source_ref` 保留小说来源，作者可以回查某场戏对应原文哪一章、哪一段。
3. `slugline` 使用地点、时间、内外景，方便后续转成标准剧本格式。
4. `purpose` 和 `conflict` 强迫每场戏有戏剧功能，避免只把小说段落机械拆开。
5. `continuity` 记录伏笔和回收，服务长篇连贯性。

### review_notes

```yaml
review_notes:
  warnings: []
  next_revision: []
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `warnings` | string[] | 是 | 自动转换时发现的风险。 |
| `next_revision` | string[] | 是 | 建议作者下一轮人工打磨的事项。 |

设计原因：AI 生成的是初稿，不应假装已经完成。把不确定性、误识别和下一步修改建议放进结构化字段，作者能更快进入二次创作。

### tooling

```yaml
tooling:
  local_tools:
    - "screenplay_yaml_schema"
    - "chapter_text_stats"
  mcp:
    enabled: false
    tools: []
    error: null
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `local_tools` | string[] | 否 | 本次生成注入模型上下文的本地工具。 |
| `mcp.enabled` | boolean | 否 | 是否启用 MCP 工具元数据接入。 |
| `mcp.tools` | object[] | 否 | MCP 工具名称和描述。 |
| `mcp.error` | string/null | 否 | MCP 工具加载错误。 |

设计原因：真实 AI 应用往往不是单纯 prompt，而会结合本地工具、Schema 工具、知识库或 MCP 工具。把 tooling 写入输出，方便复盘“这次生成使用了哪些辅助能力”。该字段不影响剧本主体编辑。

## 校验规则

1. `schema_version` 必须存在。
2. `source.chapter_count` 应大于等于 3。
3. `characters[*].id`、`locations[*].id`、`scene.scene_id` 在各自范围内必须唯一。
4. `scene.characters[*]` 应能在 `characters[*].id` 中找到。
5. `scene.source_ref.chapter_index` 应落在 `1..source.chapter_count`。
6. `dialogue[*].speaker` 应为空、`待定人物`，或能在 `characters[*].id` 中找到。
7. `review_notes.warnings` 即使为空也应输出，便于前端和后续流水线读取。

## 为什么选 YAML

YAML 比纯文本剧本更适合机器继续处理，也比 JSON 更适合作者阅读和手改。它可以直接承载数组、对象、章节引用和人物 ID；同时 diff 友好，便于版本管理。对本题而言，YAML 不是展示格式，而是“AI 初稿”和“人工改稿”之间的交换格式。
