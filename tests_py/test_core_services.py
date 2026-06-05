import unittest

from app.services.chapter_splitter import ChapterSplitter
from app.services.llm_output_parser import parse_json_object
from app.services.schema_validator import ScreenplaySchemaValidator
from app.services.yaml_builder import to_yaml


class CoreServiceTests(unittest.TestCase):
    def test_chapter_splitter_detects_three_chapters(self):
        text = """第一章 开端
甲推开门。

第二章 转折
乙发现线索。

第三章 选择
甲必须离开。"""
        chapters = ChapterSplitter().split(text)
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0].title, "第一章 开端")
        self.assertFalse(chapters[0].auto_generated)

    def test_chapter_splitter_accepts_single_heading(self):
        text = """第一章 开端
甲推开门。"""
        chapters = ChapterSplitter().split(text)
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].title, "第一章 开端")
        self.assertFalse(chapters[0].auto_generated)

    def test_parse_json_object_accepts_fenced_json(self):
        data = parse_json_object('```json\n{"ok": true, "items": [1]}\n```')
        self.assertTrue(data["ok"])
        self.assertEqual(data["items"], [1])

    def test_yaml_builder_outputs_schema_version(self):
        yaml_text = to_yaml({"schema_version": "1.0", "items": ["a"]})
        self.assertIn("schema_version", yaml_text)
        self.assertIn("items", yaml_text)

    def test_schema_validator_checks_references(self):
        script = {
            "schema_version": "1.0",
            "project": {"title": "T"},
            "source": {"chapter_count": 3},
            "memory": {},
            "characters": [{"id": "char_001", "name": "甲"}],
            "locations": [{"id": "loc_001", "name": "门口"}],
            "script": {
                "episodes": [
                    {
                        "acts": [
                            {
                                "scenes": [
                                    {
                                        "scene_id": "ch001_s001",
                                        "source_ref": {"chapter_index": 1},
                                        "slugline": {"location_id": "loc_001"},
                                        "characters": ["char_001"],
                                        "dialogue": [{"speaker": "char_001", "line": "走。"}],
                                        "purpose": "建立目标",
                                        "conflict": "必须离开",
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
        }
        report = ScreenplaySchemaValidator().validate(script)
        self.assertTrue(report.valid)

    def test_schema_validator_allows_single_chapter_processing(self):
        script = {
            "schema_version": "1.0",
            "project": {"title": "T"},
            "source": {"chapter_count": 1},
            "memory": {},
            "characters": [{"id": "char_001", "name": "甲"}],
            "locations": [{"id": "loc_001", "name": "门口"}],
            "script": {
                "episodes": [
                    {
                        "acts": [
                            {
                                "scenes": [
                                    {
                                        "scene_id": "ch001_s001",
                                        "source_ref": {"chapter_index": 1},
                                        "slugline": {"location_id": "loc_001"},
                                        "characters": ["char_001"],
                                        "dialogue": [{"speaker": "char_001", "line": "走。"}],
                                        "purpose": "建立目标",
                                        "conflict": "必须离开",
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
        }
        report = ScreenplaySchemaValidator().validate(script)
        self.assertTrue(report.valid)
        self.assertTrue(report.warnings)


if __name__ == "__main__":
    unittest.main()
