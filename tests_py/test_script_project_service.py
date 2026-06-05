import json
import tempfile
import unittest
from pathlib import Path

from app.models.request import ConvertProjectRequest
from app.services.script_project_service import ScriptProjectService


class ScriptProjectServiceTests(unittest.TestCase):
    def test_lists_metadata_projects_and_loads_split_units(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = root / "book_a"
            project.mkdir()
            (project / "chapter_001_001.txt").write_text("第一章\n\n" + "甲推门。\n\n" * 800, encoding="utf-8")
            metadata = {
                "book_title": "测试书",
                "total_char_count": 200,
                "chapters": [
                    {
                        "logical_index": 1,
                        "original_title": "第一章 测试",
                        "is_chunked": False,
                        "file_path": "./chapter_001_001.txt",
                    }
                ],
            }
            (project / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False),
                encoding="utf-8",
            )

            service = ScriptProjectService(project_root=root, output_root=root / "out")
            projects = service.list_projects()
            self.assertEqual(projects[0]["book_title"], "测试书")

            request = ConvertProjectRequest(
                user_id="u",
                thread_id="t",
                project_path="book_a",
                max_chunk_chars=2000,
            )
            units = service._load_units(project, metadata, request)
            self.assertGreater(len(units), 1)
            self.assertEqual(units[0].logical_title, "第一章 测试")


if __name__ == "__main__":
    unittest.main()
