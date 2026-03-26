import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
EXAMPLE_CONFIG_PATH = ROOT / "setup_notion_config.example.json"


def load_script(module_name: str, filename: str):
    script_path = SCRIPTS_DIR / filename
    if not script_path.exists():
        return None

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None

    original_sys_path = list(sys.path)
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module


class ExampleConfigTests(unittest.TestCase):
    def test_example_config_exists_with_expected_keys(self):
        self.assertTrue(EXAMPLE_CONFIG_PATH.exists())

        payload = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            set(payload.keys()),
            {
                "notion_token",
                "database_id",
                "title_property",
                "channel_property",
                "link_property",
                "status_property",
                "default_status",
            },
        )

    def test_example_config_is_not_a_real_secret(self):
        payload = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertNotEqual(payload["notion_token"], "")
        self.assertIn("your_", payload["notion_token"])


class SaveToNotionTests(unittest.TestCase):
    def test_default_config_path_is_repo_local_hidden_file(self):
        module = load_script("save_youtube_transcript_to_notion", "save_youtube_transcript_to_notion.py")
        self.assertIsNotNone(module)

        self.assertEqual(
            pathlib.Path(module.DEFAULT_CONFIG_PATH),
            ROOT / ".youtube-transcript-notion.json",
        )

    def test_load_config_reads_repo_local_hidden_file(self):
        module = load_script("save_youtube_transcript_to_notion", "save_youtube_transcript_to_notion.py")
        self.assertIsNotNone(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / ".youtube-transcript-notion.json"
            payload = {
                "notion_token": "secret-token",
                "database_id": "database-123",
                "title_property": "Name",
                "channel_property": "Channel",
                "link_property": "Source URL",
            }
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            self.assertEqual(module.load_config(str(config_path)), payload)

    def test_load_config_missing_file_includes_example_copy_hint(self):
        module = load_script("save_youtube_transcript_to_notion", "save_youtube_transcript_to_notion.py")
        self.assertIsNotNone(module)

        missing_path = str(ROOT / "tests" / "does-not-exist-notion-config.json")
        with self.assertRaises(module.NotionSaveError) as ctx:
            module.load_config(missing_path)

        message = str(ctx.exception)
        self.assertIn("setup_notion_config.example.json", message)
        self.assertIn(".youtube-transcript-notion.json", message)

    def test_ensure_database_properties_creates_missing_channel_and_link(self):
        module = load_script("save_youtube_transcript_to_notion", "save_youtube_transcript_to_notion.py")
        self.assertIsNotNone(module)

        calls = []

        def fake_notion_request(method, path, token, payload=None):
            calls.append((method, path, token, payload))
            self.assertEqual(method, "PATCH")
            self.assertEqual(path, "/databases/database-123")
            self.assertEqual(token, "secret-token")
            return {
                "properties": {
                    "Name": {"type": "title"},
                    "Channel": {"type": "rich_text"},
                    "Source URL": {"type": "url"},
                }
            }

        original_request = module.notion_request
        try:
            module.notion_request = fake_notion_request
            schema_props = module.ensure_database_properties(
                "database-123",
                "secret-token",
                {
                    "title_property": "Name",
                    "channel_property": "Channel",
                    "link_property": "Source URL",
                },
                {
                    "Name": {"type": "title"},
                },
            )
        finally:
            module.notion_request = original_request

        self.assertEqual(
            calls[0][3],
            {
                "properties": {
                    "Channel": {"rich_text": {}},
                    "Source URL": {"url": {}},
                }
            },
        )
        self.assertEqual(schema_props["Channel"]["type"], "rich_text")
        self.assertEqual(schema_props["Source URL"]["type"], "url")

    def test_ensure_database_properties_rejects_missing_title_property(self):
        module = load_script("save_youtube_transcript_to_notion", "save_youtube_transcript_to_notion.py")
        self.assertIsNotNone(module)

        with self.assertRaises(module.NotionSaveError) as ctx:
            module.ensure_database_properties(
                "database-123",
                "secret-token",
                {
                    "title_property": "Name",
                    "channel_property": "Channel",
                    "link_property": "Source URL",
                },
                {},
            )

        self.assertIn("title_property", str(ctx.exception))

    def test_ensure_database_properties_rejects_missing_status_property(self):
        module = load_script("save_youtube_transcript_to_notion", "save_youtube_transcript_to_notion.py")
        self.assertIsNotNone(module)

        with self.assertRaises(module.NotionSaveError) as ctx:
            module.ensure_database_properties(
                "database-123",
                "secret-token",
                {
                    "title_property": "Name",
                    "channel_property": "Channel",
                    "link_property": "Source URL",
                    "status_property": "Status",
                    "default_status": "Inbox",
                },
                {
                    "Name": {"type": "title"},
                    "Channel": {"type": "rich_text"},
                    "Source URL": {"type": "url"},
                },
            )

        self.assertIn("Status", str(ctx.exception))
        self.assertIn("manually", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
