"""Demo runner for the LangGraph screenplay workflow.

Run with:
    python -m app.agent.script_graph.demo --input samples/sample_novel.txt

This demo calls the real configured LLM provider. Make sure .env contains a
valid API key and model configuration before running it.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from app.agent.script_graph.workflow import run_chapters
from app.services.chapter_splitter import chapter_splitter
from app.services.yaml_builder import to_yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the novel-to-script LangGraph demo.")
    parser.add_argument(
        "--input",
        default="samples/sample_novel.txt",
        help="Novel text file path.",
    )
    parser.add_argument(
        "--output",
        default="data/script_graph_demo_output.yaml",
        help="Output YAML path.",
    )
    parser.add_argument(
        "--scene-density",
        type=int,
        default=3,
        help="Target scene density per chapter.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Max retry count after critic failure.",
    )
    parser.add_argument(
        "--chapter-limit",
        type=int,
        default=0,
        help="Only run the first N chapters. 0 means all chapters.",
    )
    return parser.parse_args()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    args = parse_args()

    input_path = Path(args.input)
    text = input_path.read_text(encoding="utf-8")
    chapters = chapter_splitter.split(text)
    if args.chapter_limit > 0:
        chapters = chapters[: args.chapter_limit]

    if len(chapters) < 3:
        raise SystemExit("Demo requires at least 3 chapters, matching the project requirement.")

    logging.info("Demo loaded %d chapters from %s", len(chapters), input_path)
    result = await run_chapters(
        chapters,
        scene_density=args.scene_density,
        max_retries=args.max_retries,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_yaml(result), encoding="utf-8")

    logging.info(
        "Demo completed: chapters=%d characters=%d settings=%d output=%s",
        len(result["chapters"]),
        len(result["global_characters"]),
        len(result["global_settings"]),
        output_path,
    )


if __name__ == "__main__":
    asyncio.run(main())

