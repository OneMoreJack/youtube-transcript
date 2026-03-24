# youtube-transcript

`youtube-transcript` is a skill for Claude Code, Codex, and OpenClaw that fetches the original YouTube transcript for a video URL or ID and returns it as readable Markdown blocks with timestamps.

It only uses transcript data that YouTube already provides. It does not summarize, rewrite, translate, infer speakers, or fall back to ASR.

## What This Skill Does

- fetches the original YouTube transcript for a video URL or bare video ID
- returns faithful transcript text in merged timestamped blocks
- preserves speaker-switch behavior when YouTube exposes `>>` markers
- supports mixed bilingual subtitles with either bilingual output or English-only output
- fails clearly when YouTube does not provide a usable transcript

## How To Use

### 1. Install the skill

Ask your agent to install this repository as the `youtube-transcript` skill from the repository root.

```text
Install this GitHub repository as the `youtube-transcript` skill from the repository root.
```

### 2. Ask for a transcript

Once installed, ask your agent to use `youtube-transcript` with a YouTube URL or video ID.

```text
Use youtube-transcript to fetch the transcript for https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### 3. Choose a language mode if needed

If the transcript is mixed bilingual, ask for either bilingual output or English-only output.

```text
Use youtube-transcript to fetch the transcript for <youtube-url> and keep both Chinese and English.
```

```text
Use youtube-transcript to fetch the transcript for <youtube-url> and keep English only.
```

## Examples

```text
Use youtube-transcript to fetch the original transcript for https://www.youtube.com/watch?v=uu1T5JSy32U
```

```text
Use youtube-transcript to fetch the transcript for uu1T5JSy32U and return it in Markdown.
```

```text
Use youtube-transcript to inspect the transcript metadata for https://www.youtube.com/watch?v=uu1T5JSy32U before rendering it.
```

## Behavior And Limits

- uses YouTube transcript data only
- does not summarize, rewrite, translate, or infer speakers
- does not fall back to ASR when YouTube has no transcript
- preserves existing speaker markers instead of inventing speaker names
- uses speaker-mode output for the whole transcript if any snippet starts with `>>`
- prefers sentence-ending boundaries near 30 seconds when no speaker markers exist
- splits by time when the transcript has neither meaningful punctuation nor speaker markers
- asks the user to choose bilingual or English-only output when mixed bilingual lines are detected and no preference was given
- renders bilingual lines on adjacent lines with no blank line between them

## Local Development

### Requirements

- Python 3.11+
- `youtube-transcript-api`

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

### Run The CLI

Fetch a transcript:

```bash
python3 scripts/fetch_youtube_transcript.py "<youtube-url-or-id>"
```

Inspect transcript metadata:

```bash
python3 scripts/fetch_youtube_transcript.py "<youtube-url-or-id>" --format inspect
```

Render English-only output:

```bash
python3 scripts/fetch_youtube_transcript.py "<youtube-url-or-id>" --language-mode english-only
```

### Run Tests

```bash
python3 -m unittest discover -s tests -p 'test_fetch_youtube_transcript.py' -v
```

## Repository Layout

- [`SKILL.md`](SKILL.md): skill instructions
- [`scripts/fetch_youtube_transcript.py`](scripts/fetch_youtube_transcript.py): bundled CLI
- [`agents/openai.yaml`](agents/openai.yaml): Codex/OpenAI interface metadata
- [`tests/test_fetch_youtube_transcript.py`](tests/test_fetch_youtube_transcript.py): unit tests
