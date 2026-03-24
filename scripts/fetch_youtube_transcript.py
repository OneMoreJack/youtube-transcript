#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


DEFAULT_TARGET_WINDOW = 30.0
DEFAULT_MIN_WINDOW = 20.0
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?$")
ANY_SENTENCE_END_RE = re.compile(r"[.!?。！？]")
SPEAKER_MARKER_RE = re.compile(r"^\s*(?:>>\s*)+")
SENTENCE_CHUNK_RE = re.compile(r".*?[.!?][\"')\]]?(?=\s|$)|.+$")
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
PARAGRAPH_TARGET_CHARS = 140
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
ENGLISH_SEGMENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\"“”‘’.,!?;:()\-/\s]*")
CJK_SEGMENT_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff][\u3400-\u4dbf\u4e00-\u9fff0-9，。！？、；：“”‘’（）《》〈〉…—\-\s]*")


class TranscriptToolError(Exception):
    pass


def parse_video_id(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise TranscriptToolError("Expected a YouTube URL or video ID.")

    if VIDEO_ID_RE.fullmatch(value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()

    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/")[0]
        if VIDEO_ID_RE.fullmatch(candidate):
            return candidate

    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_video_id and VIDEO_ID_RE.fullmatch(query_video_id):
            return query_video_id

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            candidate = path_parts[1]
            if VIDEO_ID_RE.fullmatch(candidate):
                return candidate

    raise TranscriptToolError("Could not parse a YouTube video ID from the input.")


def pick_default_transcript(transcripts: Iterable[object]):
    items = list(transcripts)
    if not items:
        raise TranscriptToolError("This video does not expose any original YouTube transcript tracks.")

    for transcript in items:
        if not getattr(transcript, "is_generated", False):
            return transcript

    return items[0]


def format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def cleanup_english_text(text: str) -> str:
    cleaned = normalize_text(text)
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[{])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]}])", r"\1", cleaned)
    return cleaned.strip()


def extract_english_text(text: str) -> str:
    segments = [segment.strip() for segment in ENGLISH_SEGMENT_RE.findall(text) if LATIN_RE.search(segment)]
    return cleanup_english_text(" ".join(segments))


def extract_cjk_text(text: str) -> str:
    segments = [segment.strip() for segment in CJK_SEGMENT_RE.findall(text) if CJK_RE.search(segment)]
    return normalize_text(" ".join(segments))


def clean_snippet_text(text: str) -> tuple[str, bool]:
    speaker_switch = bool(SPEAKER_MARKER_RE.match(text))
    stripped = SPEAKER_MARKER_RE.sub("", text, count=1) if speaker_switch else text
    return normalize_text(stripped), speaker_switch


def merge_snippets(
    snippets: Iterable[dict],
    target_window: float = DEFAULT_TARGET_WINDOW,
    min_window: float = DEFAULT_MIN_WINDOW,
    analysis: dict | None = None,
    language_mode: str = "original",
):
    snippet_list = list(snippets)
    if snippet_list and "original_text" not in snippet_list[0]:
        snippet_list = normalize_snippets(snippet_list)
    if not snippet_list:
        return []

    transcript_analysis = analysis or analyze_snippets(snippet_list)
    prepared_snippets = prepare_snippets(snippet_list, language_mode=language_mode)

    if any(snippet["speaker_switch"] for snippet in prepared_snippets):
        return merge_by_speaker(prepared_snippets, language_mode=language_mode)

    return merge_by_time(
        prepared_snippets,
        target_window=target_window,
        min_window=min_window,
        hard_split=(
            not transcript_analysis["has_meaningful_punctuation"]
            and not transcript_analysis["has_speaker_markers"]
        ),
        language_mode=language_mode,
    )


def normalize_snippets(snippets: Iterable[dict]) -> list[dict]:
    normalized_snippets = []
    for snippet in snippets:
        original_text, speaker_switch = clean_snippet_text(snippet.get("text", ""))
        if not original_text:
            continue
        english_text = extract_english_text(original_text)
        cjk_text = extract_cjk_text(original_text)
        normalized_snippets.append(
            {
                "original_text": original_text,
                "display_text": original_text,
                "english_text": english_text,
                "cjk_text": cjk_text,
                "start": float(snippet["start"]),
                "duration": float(snippet.get("duration", 0.0)),
                "speaker_switch": speaker_switch,
                "is_mixed_language": bool(english_text and cjk_text),
            }
        )
    return normalized_snippets


def analyze_snippets(snippets: list[dict]) -> dict:
    has_meaningful_punctuation = any(ANY_SENTENCE_END_RE.search(snippet["original_text"]) for snippet in snippets)
    needs_language_choice = any(snippet["is_mixed_language"] for snippet in snippets)
    return {
        "has_meaningful_punctuation": has_meaningful_punctuation,
        "needs_language_choice": needs_language_choice,
        "has_speaker_markers": any(snippet["speaker_switch"] for snippet in snippets),
    }


def prepare_snippets(snippets: list[dict], *, language_mode: str) -> list[dict]:
    prepared = []
    for snippet in snippets:
        entry = dict(snippet)
        if language_mode == "english-only":
            entry["display_text"] = snippet["english_text"] or snippet["original_text"]
        else:
            entry["display_text"] = snippet["original_text"]
        prepared.append(entry)
    return prepared


def merge_by_speaker(snippets: list[dict], *, language_mode: str) -> list[dict]:
    blocks = []
    current = []
    block_start = snippets[0]["start"]

    for snippet in snippets:
        if snippet["speaker_switch"] and current:
            blocks.append(build_block(current, block_start, language_mode=language_mode))
            current = []

        if not current:
            block_start = snippet["start"]
        current.append(snippet)

    if current:
        blocks.append(build_block(current, block_start, language_mode=language_mode))

    return blocks


def merge_by_time(
    snippets: list[dict],
    *,
    target_window: float,
    min_window: float,
    hard_split: bool,
    language_mode: str,
) -> list[dict]:
    blocks = []
    current = []
    block_start = snippets[0]["start"]

    for index, snippet in enumerate(snippets):
        if not current:
            block_start = snippet["start"]
        current.append(snippet)

        next_snippet = snippets[index + 1] if index + 1 < len(snippets) else None
        if should_close_time_block(
            current=current,
            next_snippet=next_snippet,
            block_start=block_start,
            target_window=target_window,
            min_window=min_window,
            hard_split=hard_split,
        ):
            blocks.append(build_block(current, block_start, language_mode=language_mode))
            current = []

    if current:
        blocks.append(build_block(current, block_start, language_mode=language_mode))

    return blocks


def should_close_time_block(
    *,
    current: list[dict],
    next_snippet: dict | None,
    block_start: float,
    target_window: float,
    min_window: float,
    hard_split: bool,
) -> bool:
    if next_snippet is None:
        return True

    elapsed = next_snippet["start"] - block_start
    if hard_split and elapsed >= target_window:
        return True

    if elapsed < min_window:
        return False

    combined_text = " ".join(snippet["display_text"] for snippet in current).strip()
    if elapsed >= target_window and bool(SENTENCE_END_RE.search(combined_text)):
        return True

    return False


def split_sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in SENTENCE_CHUNK_RE.finditer(text.strip()) if match.group(0).strip()]


def format_block_text(text: str) -> str:
    sentences = split_sentences(text)
    if len(sentences) <= 1:
        return text.strip()

    paragraphs = []
    current = []
    current_length = 0

    for sentence in sentences:
        projected = current_length + (1 if current else 0) + len(sentence)
        if current and projected > PARAGRAPH_TARGET_CHARS:
            paragraphs.append(" ".join(current).strip())
            current = [sentence]
            current_length = len(sentence)
            continue

        current.append(sentence)
        current_length = projected

    if current:
        paragraphs.append(" ".join(current).strip())

    return "\n\n".join(paragraphs)


def join_snippet_field(snippets: list[dict], field: str, *, english: bool = False) -> str:
    pieces = [snippet.get(field, "").strip() for snippet in snippets if snippet.get(field, "").strip()]
    joined = " ".join(pieces)
    return cleanup_english_text(joined) if english else normalize_text(joined)


def build_block(snippets: list[dict], block_start: float, *, language_mode: str) -> dict:
    if language_mode == "bilingual-lines":
        chinese_text = join_snippet_field(snippets, "cjk_text")
        english_text = join_snippet_field(snippets, "english_text", english=True)
        if chinese_text and english_text:
            text = f"{chinese_text}\n{english_text}"
        else:
            text = chinese_text or english_text
    else:
        text = " ".join(snippet["display_text"] for snippet in snippets).strip()
        text = format_block_text(text)
    return {
        "timestamp": format_timestamp(block_start),
        "start": block_start,
        "text": text,
    }


def render_markdown(blocks: Iterable[dict]) -> str:
    rendered_blocks = []
    for block in blocks:
        rendered_blocks.append(f"`{block['timestamp']}`\n{block['text']}")
    return "\n\n".join(rendered_blocks).strip()


def render_raw(snippets: Iterable[dict]) -> str:
    lines = []
    for snippet in snippets:
        text = normalize_text(snippet.get("text", snippet.get("original_text", "")))
        if not text:
            continue
        lines.append(f"[{format_timestamp(float(snippet['start']))}] {text}")
    return "\n".join(lines)


def fetch_transcript(source: str, language: str | None = None, preserve_formatting: bool = False):
    video_id = parse_video_id(source)
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
        if language:
            transcript = transcript_list.find_transcript([language])
        else:
            transcript = pick_default_transcript(list(transcript_list))
        fetched = transcript.fetch(preserve_formatting=preserve_formatting)
    except NoTranscriptFound as exc:
        if language:
            raise TranscriptToolError(
                f"No original YouTube transcript is available for language '{language}'."
            ) from exc
        raise TranscriptToolError("No original YouTube transcript is available for this video.") from exc
    except TranscriptsDisabled as exc:
        raise TranscriptToolError("Transcripts are disabled for this video.") from exc
    except VideoUnavailable as exc:
        raise TranscriptToolError("This video is unavailable.") from exc
    except Exception as exc:
        if isinstance(exc, TranscriptToolError):
            raise
        raise TranscriptToolError(str(exc)) from exc

    return {
        "video_id": video_id,
        "language": fetched.language,
        "language_code": fetched.language_code,
        "is_generated": fetched.is_generated,
        "snippets": fetched.to_raw_data(),
    }


def build_output(
    source: str,
    *,
    language: str | None = None,
    output_format: str = "merged-markdown",
    target_window: float = DEFAULT_TARGET_WINDOW,
    preserve_formatting: bool = False,
    language_mode: str = "original",
) -> str:
    payload = fetch_transcript(source, language=language, preserve_formatting=preserve_formatting)
    normalized_snippets = normalize_snippets(payload["snippets"])
    analysis = analyze_snippets(normalized_snippets)

    if output_format == "raw":
        return render_raw(payload["snippets"])
    if output_format == "inspect":
        return json.dumps(analysis, ensure_ascii=False, indent=2)

    blocks = merge_snippets(
        normalized_snippets,
        target_window=target_window,
        analysis=analysis,
        language_mode=language_mode,
    )
    return render_markdown(blocks)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a YouTube transcript and render merged timestamped blocks."
    )
    parser.add_argument("source", help="YouTube video URL or bare video ID")
    parser.add_argument("--lang", help="Existing transcript language code to request")
    parser.add_argument(
        "--format",
        choices=("merged-markdown", "raw", "inspect"),
        default="merged-markdown",
        help="Output format",
    )
    parser.add_argument(
        "--language-mode",
        choices=("original", "english-only", "bilingual-lines"),
        default="original",
        help="How to handle mixed bilingual transcript lines",
    )
    parser.add_argument(
        "--target-window",
        type=float,
        default=DEFAULT_TARGET_WINDOW,
        help="Approximate merge window in seconds",
    )
    parser.add_argument(
        "--preserve-formatting",
        action="store_true",
        help="Preserve supported transcript formatting returned by YouTube",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        output = build_output(
            args.source,
            language=args.lang,
            output_format=args.format,
            target_window=args.target_window,
            preserve_formatting=args.preserve_formatting,
            language_mode=args.language_mode,
        )
    except TranscriptToolError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
