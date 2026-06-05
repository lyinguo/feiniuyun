"""Prompt construction for the screenplay adaptation pipeline."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.services.chapter_splitter import Chapter


SYSTEM_PROMPT = """你是资深中文编剧和剧本改编顾问。
你的任务是把小说章节改编成可继续人工打磨的结构化剧本初稿。

硬性要求：
1. 只能输出一个 JSON object，不要输出 Markdown，不要解释。
2. 不要编造和原文完全无关的新主线。
3. 心理描写要尽量转成可拍摄的动作、调度、道具、对白或视觉提示。
4. 每场戏必须有 purpose 和 conflict。
5. characters 字段使用人物姓名，后端会统一映射成稳定 ID。
6. 如果信息不确定，写“待确认”，不要假装确定。
"""


def build_chapter_messages(
    *,
    project: Dict[str, Any],
    chapter: Chapter,
    scene_density: int,
    short_term_memory: List[Dict[str, Any]],
    long_term_memory: Dict[str, Any],
    tool_context: Dict[str, Any],
) -> list[dict[str, str]]:
    """Build OpenAI-compatible messages as dictionaries."""

    contract = {
        "chapter_summary": "string，本章剧情摘要，80-180 字",
        "characters": [
            {
                "name": "人物名",
                "role_hint": "主角/反派/配角/待定",
                "traits": ["表演或性格关键词"],
                "goals": ["本章目标或长期目标"],
            }
        ],
        "locations": [
            {
                "name": "地点名",
                "visual_identity": "可拍摄的空间/美术特征",
            }
        ],
        "canon_facts": ["本章确认且后续不能随意推翻的事实"],
        "unresolved_threads": [
            {
                "description": "伏笔、悬念或未解决问题",
                "status": "open",
            }
        ],
        "scenes": [
            {
                "title": "场景标题",
                "source_span": "对应原文范围，例如 开头/中段/结尾 或 段落 1-3",
                "slugline": {
                    "location": "地点名",
                    "time": "dawn/morning/noon/afternoon/evening/night/unknown",
                    "space": "interior/exterior/unknown",
                },
                "purpose": "这场戏的戏剧功能",
                "conflict": "这场戏的冲突或压力",
                "characters": ["人物名"],
                "action": ["可拍摄动作，避免大段心理旁白"],
                "dialogue": [
                    {
                        "speaker": "人物名",
                        "line": "对白",
                        "subtext": "潜台词",
                    }
                ],
                "visual_notes": ["镜头、道具、声音、光线等提示"],
                "continuity": {
                    "setup": ["本场埋下的伏笔"],
                    "payoff": ["本场回收的伏笔"],
                    "short_term_context": ["与最近章节的衔接点"],
                },
                "revision_note": "给作者的下一轮修改建议",
            }
        ],
        "chapter_revision_notes": ["本章整体改编风险或人工修改建议"],
    }

    user_payload = {
        "project": project,
        "chapter": {
            "chapter_id": chapter.chapter_id,
            "index": chapter.index,
            "title": chapter.title,
            "text": chapter.text,
        },
        "target_scene_count": scene_density,
        "short_term_memory": short_term_memory,
        "long_term_memory": {
            "logline": long_term_memory.get("logline", ""),
            "canon_facts": long_term_memory.get("canon_facts", [])[-30:],
            "characters": list(long_term_memory.get("characters", {}).values())[-50:],
            "locations": list(long_term_memory.get("locations", {}).values())[-50:],
            "unresolved_threads": long_term_memory.get("unresolved_threads", [])[-30:],
        },
        "tool_context": tool_context,
        "required_json_contract": contract,
    }

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False),
        },
    ]
