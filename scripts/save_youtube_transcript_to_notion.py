#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from fetch_youtube_transcript import build_output, parse_video_id

NOTION_VERSION = "2022-06-28"
SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = str(SKILL_ROOT / ".youtube-transcript-notion.json")
EXAMPLE_CONFIG_PATH = str(SKILL_ROOT / "setup_notion_config.example.json")
RICH_TEXT_LIMIT = 1900


class NotionSaveError(Exception):
    pass


def load_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise NotionSaveError(
            f"Notion config not found. Copy `{EXAMPLE_CONFIG_PATH}` to"
            f" `{DEFAULT_CONFIG_PATH}` and fill in your local Notion settings."
        ) from exc
    required = [
        "notion_token",
        "database_id",
        "title_property",
        "channel_property",
    ]
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise NotionSaveError(f"Config missing required keys: {', '.join(missing)}")

    if not data.get("link_property") and data.get("audio_url_property"):
        data["link_property"] = data["audio_url_property"]
    if not data.get("link_property"):
        raise NotionSaveError("Config missing required key: link_property")
    return data


def notion_request(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise NotionSaveError(f"Notion API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise NotionSaveError(f"Network error talking to Notion: {exc}") from exc


def fetch_video_metadata(url: str, video_id: str) -> dict:
    oembed_url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({"url": url, "format": "json"})
    try:
        with urllib.request.urlopen(oembed_url, timeout=20) as r:
            data = json.load(r)
    except Exception as exc:
        raise NotionSaveError(f"Failed to fetch YouTube metadata: {exc}") from exc

    return {
        "title": data.get("title") or f"YouTube {video_id}",
        "channel": data.get("author_name") or "",
        "url": url,
        "video_id": video_id,
    }


TIMESTAMP_BLOCK_RE = re.compile(r"^`(?P<ts>\d+:\d{2}(?::\d{2})?)`\n(?P<body>[\s\S]+)$")


def text_chunks(text: str, size: int = RICH_TEXT_LIMIT) -> list[str]:
    return [text[i:i+size] for i in range(0, len(text), size)] or [""]


def timestamp_to_seconds(timestamp: str) -> int:
    parts = [int(p) for p in timestamp.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    raise NotionSaveError(f"Invalid timestamp format: {timestamp}")


def build_text_item(content: str, *, code: bool = False, link: str | None = None) -> dict:
    item = {
        "type": "text",
        "text": {
            "content": content,
        },
        "annotations": {
            "bold": False,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": code,
            "color": "default",
        },
    }
    if link:
        item["text"]["link"] = {"url": link}
    return item


def split_plain_rich_text(text: str) -> list[dict]:
    return [build_text_item(chunk) for chunk in text_chunks(text)]


def transcript_blocks(transcript_md: str, video_url: str) -> list[dict]:
    blocks = []
    for para in re.split(r"\n\n+", transcript_md.strip()):
        para = para.strip()
        if not para:
            continue

        match = TIMESTAMP_BLOCK_RE.match(para)
        if match:
            ts = match.group("ts")
            body = match.group("body").strip()
            ts_link = f"{video_url}&t={timestamp_to_seconds(ts)}s"
            rich_text = [
                build_text_item(ts, code=True, link=ts_link),
                build_text_item("\n"),
            ]
            first = True
            for line in body.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if not first:
                    rich_text.append(build_text_item("\n"))
                for chunk in split_plain_rich_text(line):
                    rich_text.append(chunk)
                first = False

            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": rich_text}
            })
            continue

        for chunk in text_chunks(para):
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": split_plain_rich_text(chunk)}
            })
    return blocks


def append_blocks_in_batches(page_id: str, blocks: list[dict], token: str, batch_size: int = 100) -> None:
    for i in range(0, len(blocks), batch_size):
        notion_request(
            "PATCH",
            f"/blocks/{page_id}/children",
            token,
            {"children": blocks[i:i+batch_size]},
        )


def fetch_database_schema(database_id: str, token: str) -> dict:
    return notion_request("GET", f"/databases/{database_id}", token)


def sanitize_select_name(value: str) -> str:
    cleaned = value.replace(",", " ·")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:100]


def build_property_value(prop_name: str, prop_type: str, value: str | None) -> dict:
    if prop_type == "title":
        return {
            "title": [{"type": "text", "text": {"content": (value or "")[:2000]}}]
        }
    if prop_type == "rich_text":
        return {
            "rich_text": [{"type": "text", "text": {"content": (value or "")[:2000]}}]
        }
    if prop_type == "url":
        return {"url": value or None}
    if prop_type == "select":
        return {"select": {"name": sanitize_select_name(value)} if value else None}
    if prop_type == "status":
        return {"status": {"name": value}} if value else {"status": None}
    raise NotionSaveError(f"Property '{prop_name}' has unsupported type '{prop_type}'.")


def create_page(config: dict, metadata: dict, token: str) -> dict:
    schema = fetch_database_schema(config["database_id"], token)
    schema_props = schema.get("properties", {})

    title_name = config["title_property"]
    channel_name = config["channel_property"]
    link_name = config["link_property"]

    for required_name in (title_name, channel_name, link_name):
        if required_name not in schema_props:
            raise NotionSaveError(f"Database is missing property '{required_name}'.")

    props = {
        title_name: build_property_value(title_name, schema_props[title_name]["type"], metadata["title"]),
        channel_name: build_property_value(channel_name, schema_props[channel_name]["type"], metadata["channel"]),
        link_name: build_property_value(link_name, schema_props[link_name]["type"], metadata["url"]),
    }

    status_property = config.get("status_property")
    default_status = config.get("default_status")
    if status_property and default_status:
        if status_property not in schema_props:
            raise NotionSaveError(f"Database is missing property '{status_property}'.")
        props[status_property] = build_property_value(
            status_property,
            schema_props[status_property]["type"],
            default_status,
        )

    payload = {
        "parent": {"database_id": config["database_id"]},
        "properties": props,
    }
    return notion_request("POST", "/pages", token, payload)


def save_to_notion(source: str, language_mode: str, config_path: str) -> dict:
    config = load_config(config_path)
    token = config["notion_token"]
    video_id = parse_video_id(source)
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    metadata = fetch_video_metadata(canonical_url, video_id)
    transcript_md = build_output(canonical_url, language_mode=language_mode)

    page = create_page(config, metadata, token)
    blocks = transcript_blocks(transcript_md, canonical_url)
    append_blocks_in_batches(page["id"], blocks, token)

    return {
        "page_id": page["id"],
        "page_url": page.get("url", ""),
        "title": metadata["title"],
        "channel": metadata["channel"],
        "video_url": metadata["url"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a YouTube transcript and save it into a Notion database page.")
    parser.add_argument("source", help="YouTube URL or video ID")
    parser.add_argument("--language-mode", choices=("original", "english-only", "bilingual-lines"), default="original")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to Notion config JSON")
    args = parser.parse_args(argv or sys.argv[1:])

    try:
        result = save_to_notion(args.source, args.language_mode, args.config)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
