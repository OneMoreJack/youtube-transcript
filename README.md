# youtube-transcript

`youtube-transcript` is a skill for Claude Code, Codex, and OpenClaw that fetches the original YouTube transcript for a video URL or ID and returns it as readable Markdown blocks with timestamps.

It only uses transcript data that YouTube already provides. It does not summarize, rewrite, translate, infer speakers, or fall back to ASR.

By default, it returns the transcript directly in chat. It only saves to Notion when you explicitly ask it to.

## What This Skill Does

- fetches the original YouTube transcript for a video URL or bare video ID
- returns faithful transcript text in merged timestamped blocks
- preserves speaker-switch behavior when YouTube exposes `>>` markers
- supports mixed bilingual subtitles with either bilingual output or English-only output
- can save the transcript into Notion with the video title, channel, source URL, and transcript body, but only when you explicitly ask for that
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

If you only ask for the transcript, the skill should return it in the conversation and should not save it anywhere else.

### 3. Choose a language mode if needed

If the transcript is mixed bilingual, ask for either bilingual output or English-only output.

```text
Use youtube-transcript to fetch the transcript for <youtube-url> and keep both Chinese and English.
```

```text
Use youtube-transcript to fetch the transcript for <youtube-url> and keep English only.
```

### 4. Save it to Notion if needed

If you want the transcript stored in Notion, ask the agent to save it there after fetching. Notion saving is opt-in only.

```text
Use youtube-transcript to fetch the transcript for <youtube-url> and save it into Notion.
```

### 5. Set up Notion the first time

If this is your first time saving to Notion, create your local config file before asking the agent to save anything:

```bash
cp setup_notion_config.example.json .youtube-transcript-notion.json
```

Then open `.youtube-transcript-notion.json` and fill in:

- your Notion integration token
- your target Notion database ID
- the database property names for title, channel, and source URL
- an optional status property and default status

This is safer than pasting secrets into chat. The token stays in your local terminal and is written to `.youtube-transcript-notion.json` in the skill root.

If the target database is missing the configured channel or source URL property, the script will create those properties automatically. If the title property is missing, or if you want to use a status property, create those manually in Notion first.

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

```text
Use youtube-transcript to fetch the transcript for https://www.youtube.com/watch?v=uu1T5JSy32U and save it into Notion.
```

## Behavior And Limits

- uses YouTube transcript data only
- does not summarize, rewrite, translate, or infer speakers
- does not fall back to ASR when YouTube has no transcript
- returns transcript output in chat by default
- only saves to Notion when you explicitly ask it to
- preserves existing speaker markers instead of inventing speaker names
- uses speaker-mode output for the whole transcript if any snippet starts with `>>`
- prefers sentence-ending boundaries near 30 seconds when no speaker markers exist
- splits by time when the transcript has neither meaningful punctuation nor speaker markers
- asks the user to choose bilingual or English-only output when mixed bilingual lines are detected and no preference was given
- renders bilingual lines on adjacent lines with no blank line between them
- saves to Notion through `scripts/save_youtube_transcript_to_notion.py` using `.youtube-transcript-notion.json` in the skill root
- prompts you to copy `setup_notion_config.example.json` first if the Notion config does not exist yet
- automatically creates missing channel and source URL properties in the target Notion database
- still expects the configured title property and any configured status property to already exist

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

Save directly to Notion:

```bash
python3 scripts/save_youtube_transcript_to_notion.py "<youtube-url-or-id>"
```

Create local Notion config from the example file:

```bash
cp setup_notion_config.example.json .youtube-transcript-notion.json
```

### Run Tests

```bash
python3 -m unittest discover -s tests -p 'test_fetch_youtube_transcript.py' -v
```

## Repository Layout

- [`SKILL.md`](SKILL.md): skill instructions
- [`setup_notion_config.example.json`](setup_notion_config.example.json): example Notion config template
- [`scripts/fetch_youtube_transcript.py`](scripts/fetch_youtube_transcript.py): bundled CLI
- [`scripts/save_youtube_transcript_to_notion.py`](scripts/save_youtube_transcript_to_notion.py): Notion export CLI
- [`agents/openai.yaml`](agents/openai.yaml): Codex/OpenAI interface metadata
- [`tests/test_fetch_youtube_transcript.py`](tests/test_fetch_youtube_transcript.py): unit tests
