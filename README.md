# youtube-transcript

An agent skill for Claude Code, Codex, and OpenClaw that fetches the original YouTube transcript for a video URL or ID and renders it as merged Markdown blocks with timestamps.

## What It Does

- uses YouTube transcript data only
- does not summarize, rewrite, translate, or infer speakers
- preserves `>>` speaker-switch behavior when YouTube provides it
- merges transcript snippets into larger blocks for easier reading
- can keep bilingual mixed subtitles or reduce them to English only

## Repository Layout

- [`SKILL.md`](SKILL.md): skill instructions
- [`scripts/fetch_youtube_transcript.py`](scripts/fetch_youtube_transcript.py): bundled CLI
- [`agents/openai.yaml`](agents/openai.yaml): Codex/OpenAI interface metadata
- [`tests/test_fetch_youtube_transcript.py`](tests/test_fetch_youtube_transcript.py): unit tests

## Behavior

- If any transcript snippet starts with `>>`, the whole transcript uses speaker-mode output.
- If a transcript has neither punctuation nor `>>`, the script splits blocks by about 30 seconds.
- If punctuation exists and `>>` does not, the script prefers sentence-ending boundaries near 30 seconds.
- If transcript lines mix Chinese and English and the caller has not expressed a preference, the skill should ask whether to keep both languages or keep English only.
- In bilingual mode, Chinese and English are rendered on adjacent lines with no blank line between them.

## Requirements

- Python 3.11+
- `youtube-transcript-api`

Install the Python dependency with:

```bash
python3 -m pip install -r requirements.txt
```

## Run Tests

```bash
python3 -m unittest discover -s tests -p 'test_fetch_youtube_transcript.py' -v
```

## Local CLI Usage

```bash
python3 scripts/fetch_youtube_transcript.py "<youtube-url-or-id>"
```

Inspect transcript metadata before rendering:

```bash
python3 scripts/fetch_youtube_transcript.py "<youtube-url-or-id>" --format inspect
```

Render English-only output for mixed bilingual subtitles:

```bash
python3 scripts/fetch_youtube_transcript.py "<youtube-url-or-id>" --language-mode english-only
```

## Install As A Skill

This repository is packaged so the repository root is the skill directory. Install the whole repository as `youtube-transcript/` in the target agent's skills folder.

### Claude Code

Copy this repository to `~/.claude/skills/youtube-transcript/`.

### Codex

Copy this repository to `~/.codex/skills/youtube-transcript/`, or install from a GitHub URL that points at this repository root.

### OpenClaw

Install this repository as a single skill directory named `youtube-transcript/` in your OpenClaw skills location. The root-level `SKILL.md` and bundled `scripts/` layout are intended to be directly consumable without an extra wrapper folder.

## Notes

- This project intentionally does not fall back to ASR when YouTube does not expose a transcript.
- The merge step only changes block boundaries and line breaks. It does not paraphrase transcript content.
