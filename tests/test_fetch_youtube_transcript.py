import importlib.util
import pathlib
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "fetch_youtube_transcript.py"


def load_module():
    if not SCRIPT_PATH.exists():
        return types.SimpleNamespace()

    spec = importlib.util.spec_from_file_location("fetch_youtube_transcript", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeTranscript:
    def __init__(self, language_code, language, is_generated=False):
        self.language_code = language_code
        self.language = language
        self.is_generated = is_generated


class FetchYouTubeTranscriptTests(unittest.TestCase):
    def test_parse_video_id_supports_urls_and_ids(self):
        module = load_module()
        self.assertTrue(hasattr(module, "parse_video_id"))

        cases = {
            "dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=43": "dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ": "dQw4w9WgXcQ",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(module.parse_video_id(raw), expected)

    def test_pick_default_transcript_prefers_first_available_original_track(self):
        module = load_module()
        self.assertTrue(hasattr(module, "pick_default_transcript"))

        transcripts = [
            FakeTranscript(language_code="ja", language="Japanese"),
            FakeTranscript(language_code="en", language="English", is_generated=True),
        ]

        picked = module.pick_default_transcript(transcripts)
        self.assertEqual(picked.language_code, "ja")
        self.assertEqual(picked.language, "Japanese")

    def test_merge_snippets_groups_text_into_time_window_blocks(self):
        module = load_module()
        self.assertTrue(hasattr(module, "merge_snippets"))

        snippets = [
            {"text": "Hello there.", "start": 0.0, "duration": 4.0},
            {"text": "This is still the first thought.", "start": 8.0, "duration": 4.0},
            {"text": "We can keep going.", "start": 18.0, "duration": 3.0},
            {"text": "This should land in the next block.", "start": 33.0, "duration": 3.0},
            {"text": "Another line follows.", "start": 39.0, "duration": 3.0},
        ]

        blocks = module.merge_snippets(snippets, target_window=30.0)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["timestamp"], "0:00")
        self.assertIn("Hello there.", blocks[0]["text"])
        self.assertIn("We can keep going.", blocks[0]["text"])
        self.assertEqual(blocks[1]["timestamp"], "0:33")
        self.assertIn("This should land in the next block.", blocks[1]["text"])

    def test_analyze_snippets_detects_bilingual_mixing(self):
        module = load_module()
        self.assertTrue(hasattr(module, "analyze_snippets"))

        snippets = module.normalize_snippets(
            [
                {"text": "这一天 The other day 我正在和这条鱼 I was having a stare down", "start": 0.0, "duration": 4.0},
                {"text": "大眼瞪小眼 with this fish", "start": 4.0, "duration": 4.0},
            ]
        )

        analysis = module.analyze_snippets(snippets)
        self.assertFalse(analysis["has_meaningful_punctuation"])
        self.assertTrue(analysis["needs_language_choice"])

    def test_prepare_snippets_english_only_strips_chinese_text(self):
        module = load_module()
        self.assertTrue(hasattr(module, "prepare_snippets"))

        snippets = module.normalize_snippets(
            [
                {"text": "这一天 The other day 我正在和这条鱼 I was having a stare down 大眼瞪小眼 with this fish.", "start": 0.0, "duration": 4.0},
            ]
        )
        prepared = module.prepare_snippets(snippets, language_mode="english-only")
        self.assertEqual(prepared[0]["display_text"], "The other day I was having a stare down with this fish.")

    def test_render_markdown_bilingual_lines_have_no_blank_line_between_languages(self):
        module = load_module()
        self.assertTrue(hasattr(module, "render_markdown"))

        rendered = module.render_markdown(
            [
                {
                    "timestamp": "0:01",
                    "text": "这一天 我正在和这条鱼 大眼瞪小眼。\nThe other day I was having a stare down with this fish.",
                }
            ]
        )

        self.assertEqual(
            rendered,
            "`0:01`\n这一天 我正在和这条鱼 大眼瞪小眼。\nThe other day I was having a stare down with this fish.",
        )

    def test_merge_snippets_uses_speaker_mode_for_the_whole_transcript(self):
        module = load_module()
        self.assertTrue(hasattr(module, "merge_snippets"))

        snippets = [
            {"text": "First speaker opens the topic.", "start": 0.0, "duration": 4.0},
            {"text": "Keeps talking for a bit.", "start": 18.0, "duration": 3.0},
            {"text": "Still the same speaker after a long pause.", "start": 39.0, "duration": 4.0},
            {"text": "This is still the same person speaking.", "start": 58.0, "duration": 4.0},
            {"text": ">> Second speaker cuts in here.", "start": 66.0, "duration": 3.0},
            {"text": "Adds one more point.", "start": 72.0, "duration": 3.0},
        ]

        blocks = module.merge_snippets(snippets, target_window=30.0)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["timestamp"], "0:00")
        self.assertEqual(
            blocks[0]["text"],
            "First speaker opens the topic. Keeps talking for a bit. Still the same speaker after a long pause. This is still the same person speaking.",
        )
        self.assertEqual(blocks[1]["timestamp"], "1:06")
        self.assertEqual(
            blocks[1]["text"],
            "Second speaker cuts in here. Adds one more point.",
        )

    def test_merge_snippets_time_mode_waits_for_sentence_end(self):
        module = load_module()
        self.assertTrue(hasattr(module, "merge_snippets"))

        snippets = [
            {"text": "This is one long sentence that keeps going", "start": 0.0, "duration": 4.0},
            {"text": "without a natural ending for quite a while", "start": 14.0, "duration": 4.0},
            {"text": "and it should not be split right at thirty seconds", "start": 31.0, "duration": 4.0},
            {"text": "because the sentence is still continuing.", "start": 46.0, "duration": 4.0},
            {"text": "Here is a second sentence.", "start": 58.0, "duration": 4.0},
        ]

        blocks = module.merge_snippets(snippets, target_window=30.0)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["timestamp"], "0:00")
        self.assertEqual(
            blocks[0]["text"],
            "This is one long sentence that keeps going without a natural ending for quite a while and it should not be split right at thirty seconds because the sentence is still continuing.",
        )
        self.assertEqual(blocks[1]["timestamp"], "0:58")
        self.assertEqual(blocks[1]["text"], "Here is a second sentence.")

    def test_merge_snippets_hard_splits_unpunctuated_transcript_without_speaker_markers(self):
        module = load_module()
        self.assertTrue(hasattr(module, "merge_snippets"))

        snippets = module.normalize_snippets(
            [
                {"text": "this transcript has no punctuation at all", "start": 0.0, "duration": 4.0},
                {"text": "and it keeps going without sentence boundaries", "start": 16.0, "duration": 4.0},
                {"text": "so faithful mode should split on time", "start": 33.0, "duration": 4.0},
                {"text": "instead of waiting forever", "start": 45.0, "duration": 4.0},
            ]
        )

        blocks = module.merge_snippets(snippets, target_window=30.0)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["timestamp"], "0:00")
        self.assertEqual(blocks[1]["timestamp"], "0:33")

    def test_render_markdown_uses_timestamp_then_paragraph(self):
        module = load_module()
        self.assertTrue(hasattr(module, "render_markdown"))

        rendered = module.render_markdown(
            [
                {"timestamp": "0:00", "text": "First block."},
                {"timestamp": "0:33", "text": "Second block."},
            ]
        )

        self.assertEqual(rendered, "`0:00`\nFirst block.\n\n`0:33`\nSecond block.")


if __name__ == "__main__":
    unittest.main()
