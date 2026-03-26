---
name: youtube-transcript
description: Use when you need the original YouTube transcript for a video URL or ID, with faithful timestamped output and no summarization, translation, or ASR fallback. Also use when the user explicitly asks to save that transcript into Notion as a page with the video title, channel, source URL, and transcript body.
---

# YouTube Transcript

## Overview

Fetch the transcript that YouTube already provides for a video and return it in larger timestamped blocks. Keep the wording transcript-faithful: do not rewrite, summarize, translate, infer speakers, or fall back to speech recognition.

## When To Use

Use this skill when the user wants:

- the transcript for a YouTube video URL or bare video ID
- timestamps in merged paragraph blocks instead of one subtitle line per snippet
- transcript text that matches YouTube's transcript content
- the video's original transcript language by default
- the transcript saved into Notion, but only when they explicitly ask for that destination

Do not use this skill when the user wants:

- audio transcription for a video that has no YouTube transcript
- translated text when the translated transcript does not already exist on YouTube
- inferred speaker diarization

## Workflow

1. Accept a YouTube URL or video ID.
2. Run `python3 scripts/fetch_youtube_transcript.py "<url-or-id>" --format inspect`.
3. Check whether the transcript needs a language choice before output.
4. If the user already expressed a preference by meaning, honor it even if they did not use the exact mode names.
5. If the user did not express a preference and the transcript is mixed bilingual, ask before returning the transcript.
6. Default behavior is to return the transcript directly in the conversation. Do not save to Notion unless the user explicitly asked to save it there.
7. If the user explicitly wants the transcript stored in Notion, run `python3 scripts/save_youtube_transcript_to_notion.py "<url-or-id>"` from the skill root. This script uses the local config at `.youtube-transcript-notion.json` in the skill root.
8. If the configured Notion database is missing the configured channel or source URL property, the script can create those automatically. Do not assume it can create a missing title property or status property.
9. If the user explicitly wants Notion saving but the config is missing, tell them to copy `setup_notion_config.example.json` to `.youtube-transcript-notion.json` and fill it in locally. Do not ask them to paste their Notion token into chat.

Useful flags:

- `--lang <code>`: Request an existing transcript language without auto-translation.
- `--format raw`: Return the original snippet stream for verification.
- `--format inspect`: Return transcript metadata so you can decide whether to ask the user a follow-up question.
- `--language-mode original|english-only|bilingual-lines`: Control how mixed bilingual transcript lines should be handled.
- `--target-window 30`: Adjust the approximate merge window in seconds.

## Preference Matching

Treat user intent semantically, not only by exact keywords.

- Map requests like `只保留英文`, `去掉中文`, `English only` to `--language-mode english-only`.
- Map requests like `保留双语`, `中英都要`, `bilingual` to `--language-mode bilingual-lines`.

If the transcript is mixed bilingual and the user did not clearly express `english-only` or `bilingual-lines`, ask which one they want.

## Output Rules

- Default output format is Markdown:

```md
`0:00`
Transcript block...

`0:33`
Next block...
```

- Keep transcript wording faithful to the YouTube transcript.
- If any transcript snippet starts with `>>`, treat the whole transcript as speaker-mode output.
- In speaker mode, only `>>` starts a new timestamped block.
- Remove the leading `>>` from rendered text so Markdown does not turn it into a quote block.
- Within a long block, only add extra line breaks at sentence boundaries.
- If a transcript has neither sentence punctuation nor `>>` speaker markers, split it into new blocks about every 30 seconds.
- If `--language-mode bilingual-lines` is selected, render Chinese and English on adjacent lines with no blank line between them.
- Preserve other speaker labeling only when it already exists in the transcript text.
- If no YouTube transcript exists, fail clearly instead of generating one.
- If a requested language is unavailable, fail clearly instead of translating.
- Return transcript output in chat by default.
- Save to Notion only on explicit user request.

## Notes

- The bundled script uses `youtube_transcript_api`.
- Use `--format inspect` before the final output command whenever you have not yet determined whether a bilingual choice is required.
- For first-time Notion setup, copy `setup_notion_config.example.json` to `.youtube-transcript-notion.json` and fill it in locally so the Notion token never needs to appear in the chat transcript.
- The default config file lives at `.youtube-transcript-notion.json` in the skill root and should stay local to each installed copy of the skill.
- When no `>>` markers exist and punctuation is present, blocks use sentence-ending boundaries near 30 seconds.
- When neither punctuation nor `>>` markers exist, blocks split by time windows near 30 seconds.
- The merge step only changes block boundaries and line breaks. It does not paraphrase transcript content.
